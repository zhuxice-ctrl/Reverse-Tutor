from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select, text

import db
import engine
import server
from server import app


ROOT = Path(__file__).resolve().parent.parent
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "IMAGE_DATA_DIR", tmp_path / "images")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _fts_count(db_sess, doc_id: int) -> int:
    return int(db_sess.execute(
        text("SELECT count(*) FROM doc_chunks_fts WHERE doc_id = :doc_id"),
        {"doc_id": doc_id},
    ).scalar() or 0)


def _session(db_sess, *, role: str = "student") -> db.Session:
    s = engine.create_session(db_sess, title="", role=role, goal="local test")
    db_sess.commit()
    return s


def _image_row(db_sess, sid: str, tmp_path: Path):
    path = tmp_path / f"{sid}-image.png"
    path.write_bytes(PNG_BYTES)
    episode = db.add_episode(db_sess, sid, kind="image_extract", content="image text", meta={"image_id": 12345})
    db_sess.flush()
    row = db.add_image_extract(
        db_sess,
        sid,
        image_id=12345,
        mime="image/png",
        extracted_text="image text",
        structure={"kind": "question", "stem": "image text", "options": [], "hints": []},
        detected_kps=["image kp"],
        episode_id=episode.id,
        original_path=str(path),
        retained_until=datetime.utcnow() + timedelta(days=1),
    )
    db_sess.flush()
    return row, path, episode


def _seed_all_categories(db_sess, sid: str, tmp_path: Path):
    anchor = db.add_anchor(db_sess, sid, "requirement", "remember this constraint")
    study_episode = db.add_episode(db_sess, sid, kind="examiner_verify", content="episode content", meta={"source": "test"})
    db_sess.flush()
    mastery = db.upsert_mastery(
        db_sess,
        sid,
        "private kp",
        correctness=0.9,
        depth=0.7,
        evidence_type="retrieval",
        verification_status="passed",
        evidence_episode_id=study_episode.id,
    )
    error = db.upsert_error_log(db_sess, sid, "private kp", "same_error", evidence_episode_id=study_episode.id)
    image, image_path, _ = _image_row(db_sess, sid, tmp_path)
    doc = db.add_document(
        db_sess,
        session_id=sid,
        title="private doc",
        source_type="txt",
        source_uri="",
        content="private retrieval material " * 20,
    )
    global_doc = db.add_document(
        db_sess,
        session_id=None,
        title="global doc",
        source_type="txt",
        source_uri="",
        content="global retrieval material " * 20,
    )
    db_sess.commit()
    return {
        "anchor": anchor,
        "mastery": mastery,
        "error": error,
        "image": image,
        "image_path": image_path,
        "episode": study_episode,
        "doc": doc,
        "global_doc": global_doc,
    }


async def test_memory_overview_returns_all_categories(client, db_sess, tmp_path):
    s = _session(db_sess)
    seeded = _seed_all_categories(db_sess, s.id, tmp_path)

    r = await client.get(f"/api/sessions/{s.id}/memory")

    assert r.status_code == 200
    body = r.json()
    assert body["anchors"]
    assert body["mastery"]
    assert body["error_logs"]
    assert body["images"]
    assert body["recent_episodes"]
    assert [d["id"] for d in body["documents"]] == [seeded["doc"].id]
    assert seeded["global_doc"].id not in [d["id"] for d in body["documents"]]


async def test_delete_anchor_removes_from_memory_and_respects_session(client, db_sess):
    s = _session(db_sess)
    other = _session(db_sess, role="other")
    mine = db.add_anchor(db_sess, s.id, "requirement", "mine")
    theirs = db.add_anchor(db_sess, other.id, "requirement", "theirs")
    db_sess.commit()

    assert (await client.delete(f"/api/sessions/{s.id}/memory/anchor/{theirs.id}")).status_code == 404
    r = await client.delete(f"/api/sessions/{s.id}/memory/anchor/{mine.id}")

    assert r.status_code == 200
    body = (await client.get(f"/api/sessions/{s.id}/memory")).json()
    assert mine.id not in [a["id"] for a in body["anchors"]]
    assert db_sess.get(db.Anchor, theirs.id) is not None


async def test_delete_mastery_removes_from_memory(client, db_sess):
    s = _session(db_sess)
    m = db.upsert_mastery(db_sess, s.id, "kp", 1.0, 1.0, evidence_type="retrieval", verification_status="passed")
    db_sess.commit()

    r = await client.delete(f"/api/sessions/{s.id}/memory/mastery/{m.id}")

    assert r.status_code == 200
    body = (await client.get(f"/api/sessions/{s.id}/memory")).json()
    assert m.id not in [row["id"] for row in body["mastery"]]


async def test_delete_error_log_removes_from_memory(client, db_sess):
    s = _session(db_sess)
    e = db.upsert_error_log(db_sess, s.id, "kp", "pattern", evidence_episode_id=None)
    db_sess.commit()

    r = await client.delete(f"/api/sessions/{s.id}/memory/error_log/{e.id}")

    assert r.status_code == 200
    body = (await client.get(f"/api/sessions/{s.id}/memory")).json()
    assert e.id not in [row["id"] for row in body["error_logs"]]


async def test_delete_image_removes_from_memory_disk_and_episode_refs(client, db_sess, tmp_path):
    s = _session(db_sess)
    row, path, episode = _image_row(db_sess, s.id, tmp_path)
    db.upsert_mastery(
        db_sess,
        s.id,
        "image kp",
        0.1,
        0.1,
        evidence_type="retrieval",
        verification_status="partial",
        evidence_episode_id=episode.id,
    )
    db_sess.commit()
    image_id = row.image_id
    episode_id = episode.id

    r = await client.delete(f"/api/sessions/{s.id}/memory/image/{row.id}")

    assert r.status_code == 200
    db_sess.expire_all()
    assert not path.exists()
    assert db.get_image_extract(db_sess, s.id, image_id) is None
    assert all(episode_id not in m.evidence_ids() for m in db.list_mastery(db_sess, s.id))


async def test_delete_document_removes_from_memory_and_fts(client, db_sess):
    s = _session(db_sess)
    doc = db.add_document(db_sess, session_id=s.id, title="private", source_type="txt", source_uri="", content="memory doc " * 20)
    global_doc = db.add_document(db_sess, session_id=None, title="global", source_type="txt", source_uri="", content="global doc " * 20)
    db_sess.commit()

    r = await client.delete(f"/api/sessions/{s.id}/memory/document/{doc.id}")

    assert r.status_code == 200
    body = (await client.get(f"/api/sessions/{s.id}/memory")).json()
    assert doc.id not in [d["id"] for d in body["documents"]]
    assert db_sess.scalar(select(func.count(db.DocChunk.id)).where(db.DocChunk.doc_id == doc.id)) == 0
    assert _fts_count(db_sess, doc.id) == 0
    assert (await client.delete(f"/api/sessions/{s.id}/memory/document/{global_doc.id}")).status_code == 404


async def test_delete_episode_cleans_mastery_evidence_refs(client, db_sess):
    s = _session(db_sess)
    episode = db.add_episode(db_sess, s.id, kind="examiner_verify", content="verify", meta={})
    db_sess.flush()
    m = db.upsert_mastery(
        db_sess,
        s.id,
        "kp",
        1.0,
        1.0,
        evidence_type="retrieval",
        verification_status="passed",
        evidence_episode_id=episode.id,
    )
    db_sess.commit()
    episode_id = episode.id
    mastery_id = m.id

    assert episode_id in m.evidence_ids()
    r = await client.delete(f"/api/sessions/{s.id}/memory/episode/{episode_id}")

    assert r.status_code == 200
    db_sess.expire_all()
    assert db_sess.get(db.Message, episode_id) is None
    assert episode_id not in db_sess.get(db.Mastery, mastery_id).evidence_ids()


async def test_delete_episode_cleans_error_log_linked_refs(client, db_sess):
    s = _session(db_sess)
    episode = db.add_episode(db_sess, s.id, kind="examiner_verify", content="verify", meta={})
    db_sess.flush()
    e = db.upsert_error_log(db_sess, s.id, "kp", "pattern", evidence_episode_id=episode.id)
    db_sess.commit()
    episode_id = episode.id
    error_id = e.id

    r = await client.delete(f"/api/sessions/{s.id}/memory/episode/{episode_id}")

    assert r.status_code == 200
    db_sess.expire_all()
    assert episode_id not in db.get_error_log(db_sess, s.id, error_id).linked_ids()


async def test_delete_invalid_kind_returns_422(client, db_sess):
    s = _session(db_sess)

    r = await client.delete(f"/api/sessions/{s.id}/memory/invalid/1")

    assert r.status_code == 422


async def test_delete_nonexistent_id_returns_404(client, db_sess):
    s = _session(db_sess)

    r = await client.delete(f"/api/sessions/{s.id}/memory/anchor/99999")

    assert r.status_code == 404


def test_pwa_memory_tab_surfaces_semantic_kg_nodes():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    render_fn = html.split("async function renderContextMemory", 1)[1].split("function bindLearningContextActions", 1)[0]
    kg_filter = html.split("function normalizeMemoryPanelKgKind", 1)[1].split("async function renderContextMemory", 1)[0]

    assert "isMemoryPanelSemanticKgNode" in html
    assert "normalizeMemoryPanelKgKind" in html
    assert "replace(/[_-]+/g, '_').toLowerCase()" in kg_filter
    assert "['kg_nodes'," in render_fn
    assert "memory.kg_nodes" in render_fn
    assert "PROCESS_KG_KINDS" in html
    assert "memoryRowHtml('kg_node'" in render_fn


def test_pwa_memory_tab_exists():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'data-context-tab="memory"' in html
    assert "renderContextMemory" in html
    assert "确定删除这条" in html
