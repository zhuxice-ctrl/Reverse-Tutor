from __future__ import annotations

import httpx
import pytest

import db
import engine
import llm
from server import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_sequence_mock(payloads: list[dict]):
    it = iter(payloads)

    async def mock_chat_json(system, messages, **kwargs):
        return next(it)

    return mock_chat_json


def _payload(
    *,
    action_type: str = "probe",
    role: str = "probing_student",
    kp: str = "极值点偏移",
    correctness: float = 0.3,
    depth: float = 0.2,
    evidence_type: str = "explanation",
    evidence_status: str = "partial",
    error_pattern: str = "",
    reply: str = "mock reply",
) -> dict:
    return {
        "evaluation": {
            "correctness": correctness,
            "depth": depth,
            "entry_status": "has_entry",
            "error_pattern": error_pattern,
            "evidence_for_mastery": {
                "type": evidence_type,
                "status": evidence_status,
                "error_type": "条件错" if error_pattern else "",
                "reason": "small lecture test",
            },
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": kp,
            "difficulty": 0.5,
            "note": "small lecture test",
        },
        "reply": reply,
        "anchor_updates": [],
        "cited_chunk_ids": [],
    }


def _session(db_sess, *, settings=None):
    s = engine.create_session(
        db_sess,
        title="",
        role="高三学生",
        goal="数学 130",
        settings=settings or {},
    )
    return s


def test_has_active_errors_for_kp_ignores_resolved(db_sess):
    s = _session(db_sess)
    active = db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    resolved = db.upsert_error_log(db_sess, s.id, "对称轴", "步骤跳跃", evidence_episode_id=None)
    db.resolve_error_log(db_sess, s.id, resolved.id)
    db_sess.commit()

    assert engine._has_active_errors_for_kp([active, resolved], "极值点偏移") is True
    assert engine._has_active_errors_for_kp([active, resolved], "对称轴") is False


async def test_active_error_and_low_correctness_triggers_small_lecture(db_sess, monkeypatch):
    s = _session(db_sess)
    db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    db_sess.commit()
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="先把符号方向说清楚，再请你复述。"),
    ]))

    result = await engine.run_turn(db_sess, s.id, "我还是把符号方向弄反")

    assert result.action["type"] == "small_lecture"
    assert result.action["student_role"] == "probing_student"


async def test_probing_intensity_five_blocks_small_lecture(db_sess, monkeypatch):
    s = _session(db_sess, settings={"probing_intensity": 5})
    db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    db_sess.commit()
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="我继续追问你为什么符号会反。"),
    ]))

    result = await engine.run_turn(db_sess, s.id, "我还是把符号方向弄反")

    assert result.action["type"] == "probe"


async def test_no_error_log_does_not_trigger_small_lecture(db_sess, monkeypatch):
    s = _session(db_sess)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="那你先解释为什么要这样判断。"),
    ]))

    result = await engine.run_turn(db_sess, s.id, "我这里说不完整")

    assert result.action["type"] == "probe"


async def test_e2e_failure_then_small_lecture_then_probe(client, db_sess, monkeypatch):
    r = await client.post("/api/sessions", json={
        "role": "高三学生",
        "goal": "数学 130",
        "auto_opening": False,
    })
    sid = r.json()["id"]
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(
            action_type="examiner_verify",
            role="examiner",
            correctness=0.2,
            depth=0.2,
            evidence_type="correction",
            evidence_status="failed",
            error_pattern="符号错",
            reply="这里符号方向错了。",
        ),
        _payload(
            action_type="probe",
            role="probing_student",
            correctness=0.3,
            depth=0.2,
            evidence_type="explanation",
            evidence_status="partial",
            reply="这个漏洞要先看条件方向。你能复述吗？",
        ),
        _payload(
            action_type="probe",
            role="probing_student",
            correctness=0.7,
            depth=0.5,
            evidence_type="explanation",
            evidence_status="passed",
            reply="那你再解释边界为什么也要检查？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我懂了但这题答错了"})
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我又把符号方向弄反"})
    third = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我复述一下，先看条件再看符号"})

    assert first.json()["action"]["type"] == "examiner_verify"
    assert db.list_error_logs(db_sess, sid)[0].error_pattern == "符号错"
    assert second.json()["action"]["type"] == "small_lecture"
    assert third.json()["action"]["type"] == "probe"


async def test_resolved_error_log_does_not_trigger_small_lecture(db_sess, monkeypatch):
    s = _session(db_sess)
    row = db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    db.resolve_error_log(db_sess, s.id, row.id)
    db_sess.commit()
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="我继续追问，不做小讲解。"),
    ]))

    result = await engine.run_turn(db_sess, s.id, "我还是把符号方向弄反")

    assert result.action["type"] == "probe"


async def test_system_prompt_includes_error_patterns(db_sess, monkeypatch):
    s = _session(db_sess)
    db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    db_sess.commit()
    prompts = []

    async def fake_chat_json(system, messages, **kwargs):
        prompts.append(system)
        return _payload(reply="我先针对符号错补一个小洞。")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "我还是把符号方向弄反")

    assert "已知错误模式" in prompts[0]
    assert "符号错" in prompts[0]
    assert "small_lecture" in prompts[0]


async def test_small_lecture_process_summary_mentions_micro_explanation(db_sess, monkeypatch):
    s = _session(db_sess)
    db.upsert_error_log(db_sess, s.id, "极值点偏移", "符号错", evidence_episode_id=None)
    db_sess.commit()
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="我先用三句话把符号错补上。"),
    ]))

    result = await engine.run_turn(db_sess, s.id, "我还是把符号方向弄反")

    assert result.action["type"] == "small_lecture"
    assert "微讲解" in result.process_summary


def test_mock_pack_supports_small_lecture():
    raw = llm._pack(
        "small_lecture",
        "极值点偏移",
        "neutral",
        correctness=0.3,
        depth=0.2,
        reqs=[],
    )

    assert raw["action"]["type"] == "small_lecture"
    assert raw["action"]["student_role"] == "probing_student"
    assert raw["reply"]
