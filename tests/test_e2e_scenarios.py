from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

import db
import engine
import server
import vision
from server import app


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "IMAGE_DATA_DIR", tmp_path / "images")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_session(client) -> str:
    r = await client.post("/api/sessions", json={
        "role": "高三学生",
        "goal": "数学 130",
        "auto_opening": False,
    })
    assert r.status_code == 200
    return r.json()["id"]


def _make_sequence_mock(payloads: list[dict]):
    it = iter(payloads)

    async def mock_chat_json(system, messages, **kwargs):
        return next(it)

    return mock_chat_json


def _p(
    *,
    action_type: str = "ask",
    role: str = "probing_student",
    entry: str = "has_entry",
    correctness: float = 0.5,
    depth: float = 0.3,
    evidence_type: str = "none",
    evidence_status: str = "none",
    error_type: str = "",
    error_pattern: str = "",
    emotion: str = "neutral",
    kp: str = "极值点偏移",
    reply: str = "mock reply",
    cited: list[int] | None = None,
) -> dict:
    return {
        "evaluation": {
            "correctness": correctness,
            "depth": depth,
            "entry_status": entry,
            "error_pattern": error_pattern,
            "evidence_for_mastery": {
                "type": evidence_type,
                "status": evidence_status,
                "error_type": error_type,
                "reason": "e2e mock",
            },
            "user_emotion": emotion,
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": kp,
            "difficulty": 0.5,
            "note": "e2e mock",
        },
        "reply": reply,
        "cited_chunk_ids": cited or [],
        "anchor_updates": [],
    }


def _mastery_for(db_sess, sid: str, kp: str):
    db_sess.expire_all()
    for row in db.list_mastery(db_sess, sid):
        if row.knowledge_point == kp:
            return row
    return None


async def test_e2e_user_totally_unfamiliar(client, db_sess, monkeypatch):
    sid = await _create_session(client)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _p(
            action_type="clue",
            role="clue_student",
            entry="no_entry",
            correctness=0.0,
            depth=0.0,
            reply="老师，我听说极值点偏移可以先看一个具体例子的第一步，你能先讲这个吗？",
        ),
        _p(
            action_type="probe",
            role="probing_student",
            entry="has_entry",
            correctness=0.4,
            depth=0.4,
            evidence_type="explanation",
            evidence_status="partial",
            reply="那你先说说这个第一步为什么能帮上忙？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我完全不知道极值点偏移是啥"})
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "哦我好像有点印象，先比较左右变化"})

    assert first.status_code == 200
    assert first.json()["evaluation"]["entry_status"] == "no_entry"
    assert first.json()["action"]["type"] in {"clue", "scaffold_example"}
    assert first.json()["action"]["student_role"] == "clue_student"
    assert second.status_code == 200
    assert second.json()["evaluation"]["entry_status"] == "has_entry"
    assert second.json()["action"]["type"] == "probe"
    mastery = _mastery_for(db_sess, sid, "极值点偏移")
    assert mastery is not None
    assert mastery.mastery_score > 0


async def test_e2e_user_partial_explanation(client, db_sess, monkeypatch):
    sid = await _create_session(client)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _p(
            action_type="probe",
            role="probing_student",
            correctness=0.4,
            depth=0.2,
            evidence_type="explanation",
            evidence_status="partial",
            reply="你说到了对称轴，但为什么它和极值点有关？",
        ),
        _p(
            action_type="probe",
            role="probing_student",
            correctness=0.7,
            depth=0.5,
            evidence_type="explanation",
            evidence_status="passed",
            reply="那边界条件还能怎么检查？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "对称轴是 -b/2a 但是为什么呢"})
    score_after_first = _mastery_for(db_sess, sid, "极值点偏移").mastery_score
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "因为它能帮我定位左右变化的平衡点"})
    score_after_second = _mastery_for(db_sess, sid, "极值点偏移").mastery_score

    assert first.json()["action"]["type"] == "probe"
    assert second.json()["action"]["type"] == "probe"
    assert score_after_second > score_after_first
    assert second.json()["process_summary"]


async def test_e2e_user_claims_understood_but_fails_verification(client, db_sess, monkeypatch):
    sid = await _create_session(client)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _p(
            action_type="examiner_verify",
            role="examiner",
            correctness=0.0,
            depth=0.0,
            reply="那我出一道验证题，你只说第一步怎么做。",
        ),
        _p(
            action_type="examiner_verify",
            role="examiner",
            correctness=0.2,
            depth=0.2,
            evidence_type="correction",
            evidence_status="failed",
            error_type="条件错",
            error_pattern="符号错",
            reply="这里符号方向错了，我们先回到条件。",
        ),
        _p(
            action_type="probe",
            role="probing_student",
            correctness=0.6,
            depth=0.5,
            evidence_type="correction",
            evidence_status="passed",
            reply="这次你改对了，为什么要这样处理符号？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我懂了"})
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我把符号反过来代入"})
    failed_score = _mastery_for(db_sess, sid, "极值点偏移").mastery_score
    logs = db.list_error_logs(db_sess, sid)
    third = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我应该先看条件再决定符号方向"})
    passed_score = _mastery_for(db_sess, sid, "极值点偏移").mastery_score

    assert first.json()["action"]["student_role"] == "examiner"
    assert second.json()["action"]["type"] == "examiner_verify"
    assert logs
    assert logs[0].error_pattern == "符号错"
    assert third.json()["action"]["type"] == "probe"
    assert passed_score > failed_score


async def test_e2e_user_uploads_question_image(client, db_sess, monkeypatch):
    sid = await _create_session(client)
    monkeypatch.setattr(vision, "extract_from_image", lambda path: vision.ExtractResult(
        extracted_text="求函数 f(x)=x^3-3x 的极值",
        structure={"kind": "question", "stem": "求函数 f(x)=x^3-3x 的极值", "options": [], "hints": []},
        detected_kps=["极值点"],
    ))
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _p(
            action_type="clue",
            role="clue_student",
            entry="no_entry",
            kp="极值点",
            reply="老师，我听说极值点可以先看导数为零的位置，你能先讲这个线索吗？",
        )
    ]))

    upload = await client.post(
        f"/api/sessions/{sid}/images",
        files={"file": ("q.png", PNG_BYTES, "image/png")},
    )
    chat = await client.post(f"/api/sessions/{sid}/chat", json={"message": "这道题我不太会"})

    assert upload.status_code == 200
    body = upload.json()
    assert body["extracted_text"] == "求函数 f(x)=x^3-3x 的极值"
    assert body["detected_kps"] == ["极值点"]
    assert _mastery_for(db_sess, sid, "极值点") is not None
    assert chat.status_code == 200
    assert chat.json()["evaluation"]["entry_status"] == "no_entry"
    assert chat.json()["action"]["type"] in {"clue", "scaffold_example"}


async def test_e2e_review_due_but_user_continues(client, db_sess, monkeypatch):
    sid = await _create_session(client)
    m = db.upsert_mastery(
        db_sess,
        sid,
        "旧知识点",
        correctness=0.9,
        depth=0.7,
        evidence_type="retrieval",
        verification_status="passed",
    )
    m.next_review_at = datetime.utcnow() - timedelta(days=1)
    db_sess.commit()
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _p(
            action_type="ask",
            role="probing_student",
            kp="链式法则",
            reply="那你想先从链式法则的哪一步开始？",
        ),
        _p(
            action_type="probe",
            role="probing_student",
            kp="链式法则",
            correctness=0.5,
            depth=0.4,
            evidence_type="explanation",
            evidence_status="partial",
            reply="为什么外层函数要最后处理？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我要继续学导数的链式法则"})
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我想先看复合函数怎么拆"})

    assert first.status_code == 200
    assert "到期" in first.json()["process_summary"] or "复习" in first.json()["process_summary"]
    assert first.json()["action"]["type"] == "ask"
    assert second.status_code == 200
    assert second.json()["action"]["type"] == "probe"
