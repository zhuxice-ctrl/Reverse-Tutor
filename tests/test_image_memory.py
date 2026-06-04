from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

import db
import vision
from server import app
import server


ROOT = Path(__file__).resolve().parent.parent
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
IMAGE_CARD_KEYS = {
    "id",
    "image_id",
    "session_id",
    "mime",
    "extracted_text",
    "structure",
    "detected_kps",
    "episode_id",
    "original_retained_until",
    "original_url",
    "created_at",
}


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "IMAGE_DATA_DIR", tmp_path / "images")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_vision(monkeypatch, *, kps: list[str] | None = None, text: str = "题干：求极值点偏移"):
    result = vision.ExtractResult(
        extracted_text=text,
        structure={"kind": "question", "stem": text, "options": [], "hints": ["先找对称关系"]},
        detected_kps=kps or ["极值点偏移"],
    )
    monkeypatch.setattr(vision, "extract_from_image", lambda path: result)
    return result


async def _session(client, *, settings=None) -> str:
    r = await client.post("/api/sessions", json={"role": "高三学生", "goal": "数学130", "auto_opening": False})
    sid = r.json()["id"]
    if settings:
        await client.patch(f"/api/sessions/{sid}/settings", json={"settings": settings})
    return sid


async def _upload(client, sid: str, *, name="q.png", mime="image/png", body=PNG_BYTES):
    return await client.post(f"/api/sessions/{sid}/images", files={"file": (name, body, mime)})


def _assert_card_ready_image(
    card: dict,
    *,
    sid: str,
    mime: str,
    text: str,
    kps: list[str],
    retained: bool,
) -> None:
    assert set(card) == IMAGE_CARD_KEYS
    assert card["id"] > 0
    assert card["image_id"] > 0
    assert card["session_id"] == sid
    assert card["mime"] == mime
    assert card["extracted_text"] == text
    assert card["structure"]["kind"] == "question"
    assert card["structure"]["stem"] == text
    assert isinstance(card["structure"]["options"], list)
    assert isinstance(card["structure"]["hints"], list)
    assert card["detected_kps"] == kps
    assert card["episode_id"] > 0
    assert card["created_at"].endswith("Z")
    if retained:
        assert card["original_retained_until"].endswith("Z")
        assert card["original_url"] == f"/api/sessions/{sid}/images/{card['image_id']}/original"
    else:
        assert card["original_retained_until"] is None
        assert card["original_url"] is None


async def test_upload_image_default_deletes_original_immediately(client, db_sess, monkeypatch):
    _patch_vision(monkeypatch)
    sid = await _session(client)

    r = await _upload(client, sid)

    assert r.status_code == 200
    body = r.json()
    assert body["original_retained_until"] is None
    row = db.get_image_extract(db_sess, sid, body["image_id"])
    assert row is not None
    assert row.original_path is None
    assert not any((server.IMAGE_DATA_DIR / sid).glob("*"))
    assert row.extracted_text == "题干：求极值点偏移"
    assert row.structure()["kind"] == "question"
    episode = db_sess.get(db.Message, body["episode_id"])
    assert episode.role == "system"
    assert episode.meta()["kind"] == "image_extract"


async def test_upload_list_and_detail_return_card_ready_image_contract(client, monkeypatch):
    text = "card-ready extraction"
    kps = ["extrema", "translation"]
    _patch_vision(monkeypatch, kps=kps, text=text)
    sid = await _session(client, settings={"image_retention_days": 7})

    upload = await _upload(client, sid, name="q.webp", mime="image/webp")

    assert upload.status_code == 200
    uploaded = upload.json()
    _assert_card_ready_image(uploaded, sid=sid, mime="image/webp", text=text, kps=kps, retained=True)
    assert "original_path" not in uploaded

    listed_response = await client.get(f"/api/sessions/{sid}/images")
    assert listed_response.status_code == 200
    listed = listed_response.json()
    assert listed == [uploaded]
    _assert_card_ready_image(listed[0], sid=sid, mime="image/webp", text=text, kps=kps, retained=True)
    assert "original_path" not in listed[0]

    detail_response = await client.get(f"/api/sessions/{sid}/images/{uploaded['image_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert set(detail) == IMAGE_CARD_KEYS | {"original_path"}
    assert {key: detail[key] for key in IMAGE_CARD_KEYS} == uploaded
    assert detail["original_path"]
    assert Path(detail["original_path"]).exists()


async def test_memory_images_use_card_ready_shape_without_original_path(client, monkeypatch):
    text = "memory card extraction"
    kps = ["image kp"]
    _patch_vision(monkeypatch, kps=kps, text=text)
    sid = await _session(client)
    uploaded = (await _upload(client, sid)).json()

    r = await client.get(f"/api/sessions/{sid}/memory")

    assert r.status_code == 200
    images = r.json()["images"]
    assert images == [uploaded]
    card = images[0]
    _assert_card_ready_image(card, sid=sid, mime="image/png", text=text, kps=kps, retained=False)
    assert "original_path" not in card


async def test_upload_image_with_retention_keeps_until_expiry(client, db_sess, monkeypatch):
    _patch_vision(monkeypatch)
    sid = await _session(client, settings={"image_retention_days": 7})

    before = datetime.utcnow()
    r = await _upload(client, sid)

    row = db.get_image_extract(db_sess, sid, r.json()["image_id"])
    assert row.retained_until is not None
    assert before + timedelta(days=6, hours=23) <= row.retained_until <= before + timedelta(days=7, minutes=1)
    assert row.original_path and Path(row.original_path).exists()


def test_purge_expired_images_removes_only_expired(db_sess, tmp_path):
    old = tmp_path / "old.png"; old.write_bytes(PNG_BYTES)
    fresh = tmp_path / "fresh.png"; fresh.write_bytes(PNG_BYTES)
    db.add_image_extract(db_sess, "s1", image_id=1, mime="image/png", extracted_text="old", structure={}, detected_kps=[], episode_id=None, original_path=str(old), retained_until=datetime.utcnow() - timedelta(seconds=1))
    db.add_image_extract(db_sess, "s1", image_id=2, mime="image/png", extracted_text="fresh", structure={}, detected_kps=[], episode_id=None, original_path=str(fresh), retained_until=datetime.utcnow() + timedelta(days=1))
    db_sess.commit()

    assert db.purge_expired_images(db_sess, datetime.utcnow()) == 1
    db_sess.commit()

    assert not old.exists()
    assert fresh.exists()
    assert db.get_image_extract(db_sess, "s1", 1).original_path is None
    assert db.get_image_extract(db_sess, "s1", 2).original_path == str(fresh)


async def test_learning_state_references_episode_not_image_path(client, db_sess, monkeypatch):
    _patch_vision(monkeypatch, kps=["极值点偏移"])
    sid = await _session(client)

    body = (await _upload(client, sid)).json()

    mastery = db.list_mastery(db_sess, sid)[0]
    assert body["episode_id"] in mastery.evidence_ids()
    evidence_json = mastery.evidence_episode_ids
    assert str(body["image_id"]) not in evidence_json
    assert "data/images" not in evidence_json.replace("\\", "/")


async def test_delete_image_cascade_removes_disk_and_db(client, db_sess, monkeypatch):
    _patch_vision(monkeypatch)
    sid = await _session(client, settings={"image_retention_days": 7})
    body = (await _upload(client, sid)).json()
    row = db.get_image_extract(db_sess, sid, body["image_id"])
    path = Path(row.original_path)
    assert path.exists()

    r = await client.delete(f"/api/sessions/{sid}/images/{body['image_id']}")

    assert r.status_code == 200
    assert not path.exists()
    assert db.get_image_extract(db_sess, sid, body["image_id"]) is None


async def test_delete_session_cascades_images(client, db_sess, monkeypatch):
    _patch_vision(monkeypatch)
    sid_a = await _session(client, settings={"image_retention_days": 7})
    sid_b = await _session(client, settings={"image_retention_days": 7})
    image_a = (await _upload(client, sid_a)).json()["image_id"]
    image_b = (await _upload(client, sid_b)).json()["image_id"]
    path_a = Path(db.get_image_extract(db_sess, sid_a, image_a).original_path)
    path_b = Path(db.get_image_extract(db_sess, sid_b, image_b).original_path)

    await client.delete(f"/api/sessions/{sid_a}")

    assert db.get_image_extract(db_sess, sid_a, image_a) is None
    assert not path_a.exists()
    assert db.get_image_extract(db_sess, sid_b, image_b) is not None
    assert path_b.exists()


async def test_oversize_or_unsupported_mime_rejected(client, monkeypatch):
    _patch_vision(monkeypatch)
    sid = await _session(client)

    bad_type = await _upload(client, sid, name="q.gif", mime="image/gif")
    too_big = await _upload(client, sid, body=b"x" * (5 * 1024 * 1024 + 1))

    assert bad_type.status_code == 422
    assert too_big.status_code == 422


def test_pwa_context_images_are_imported_through_anchors():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    context_anchors_fn = html.split("async function renderContextAnchors", 1)[1].split("async function renderContextNotes", 1)[0]

    assert 'data-context-tab="images"' not in html
    assert "renderContextImages" not in html
    assert 'id="context-anchor-image-file"' in context_anchors_fn
    assert "importAnchorImages" in html
    assert "source_type: 'image'" in html
    assert "image_extracts" not in html
