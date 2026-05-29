from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import db
import engine
from server import app


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _turn_payload(
    *,
    action_type: str = "challenge",
    role: str = "confused_student",
    kp: str = "函数单调性",
    misconception: str = "正值递增",
    correctness: float = 0.2,
    evidence: dict | None = None,
    error_pattern: str = "",
) -> dict:
    return {
        "evaluation": {
            "correctness": correctness,
            "depth": 0.25,
            "entry_status": "has_entry",
            "error_pattern": error_pattern,
            "misconception": misconception,
            "evidence_for_mastery": evidence
            or {"type": "none", "status": "none", "error_type": "", "reason": ""},
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": kp,
            "difficulty": 0.6,
            "note": "发现用户把错规则当成结论",
        },
        "reply": "老师，我拿一个小例子套了下，好像和这个说法对不上。",
        "anchor_updates": [],
    }


async def test_misconception_challenge_action_and_role_are_preserved(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    async def fake_chat_json(system, messages, **kwargs):
        assert "misconception" in system
        assert "challenge" in system
        assert "confused_student" in system
        return _turn_payload()

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "函数值是正的，所以函数就在递增")

    assert result.action["type"] == "challenge"
    assert result.action["student_role"] == "confused_student"
    assert result.evaluation["misconception"] == "正值递增"


def test_challenge_action_is_study_only():
    assert "challenge" in engine._action_types_for_mode("study")
    assert "challenge" not in engine._action_types_for_mode("goal")
    assert "challenge" not in engine._action_types_for_mode("companion")
    assert engine._student_role_for_action("challenge") == "confused_student"


def test_correction_persistence_settings_are_formatted_and_clamped(db_sess):
    expected = {
        "gentle": "gentle：只用 L1 反例，绝不使用 L3 求证提示",
        "balanced": "balanced：L1 反例 → L2 指矛盾 → L3 求证提示",
        "persistent": "persistent：更快升级到 L3/L4，但仍保持学生口吻",
    }
    for level, text in expected.items():
        s = engine.create_session(
            db_sess,
            title="",
            role="高三生",
            goal="数学130",
            settings={"correction_persistence": level},
        )
        settings = engine._strategy_settings(s)
        block = engine._format_strategy_settings(settings)
        assert settings["correction_persistence"] == level
        assert f"纠错坚持度：{level}" in block
        assert text in block

    s = engine.create_session(
        db_sess,
        title="",
        role="高三生",
        goal="数学130",
        settings={"correction_persistence": "loud"},
    )
    assert engine._strategy_settings(s)["correction_persistence"] == "balanced"


async def test_misconception_writes_active_error_log(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    async def fake_chat_json(system, messages, **kwargs):
        return _turn_payload()

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "正值就说明函数递增")

    rows = db.list_error_logs(db_sess, s.id)
    assert len(rows) == 1
    assert rows[0].kp == "函数单调性"
    assert rows[0].error_pattern == "正值递增"
    assert rows[0].status == "active"


async def test_correction_pass_resolves_matching_error_log_and_records_evidence(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    row = db.upsert_error_log(db_sess, s.id, "函数单调性", "正值递增", evidence_episode_id=None)
    db_sess.commit()

    async def fake_chat_json(system, messages, **kwargs):
        return _turn_payload(
            action_type="probe",
            role="probing_student",
            misconception="",
            correctness=0.9,
            evidence={
                "type": "correction",
                "status": "passed",
                "error_type": "正值递增",
                "reason": "用户改口为看导数符号判断增减",
            },
            error_pattern="正值递增",
        )

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "哦，应该看导数符号，不是看函数值正负")
    refreshed = db.get_error_log(db_sess, s.id, row.id)
    assistant = [m for m in db.list_messages(db_sess, s.id) if m.role == "assistant"][-1]
    meta = assistant.meta()

    assert refreshed.status == "resolved"
    assert meta["evaluation"]["evidence_for_mastery"]["type"] == "correction"
    assert meta["evidence_episode_ids"] == [assistant.id]


async def test_low_correctness_without_misconception_does_not_force_challenge(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    async def fake_chat_json(system, messages, **kwargs):
        return _turn_payload(
            action_type="probe",
            role="probing_student",
            misconception="",
            correctness=0.25,
        )

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "我只记得它好像和图像上下有关")

    assert result.action["type"] in {"ask", "probe"}
    assert result.action["type"] != "challenge"
    assert db.list_error_logs(db_sess, s.id) == []


async def test_backward_compatibility_server_defaults_and_pwa_tokens(db_sess, client):
    assert engine.DEFAULT_STRATEGY_SETTINGS["correction_persistence"] == "balanced"

    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130", settings={})
    assert engine._strategy_settings(s)["correction_persistence"] == "balanced"

    r = await client.post(
        "/api/sessions",
        json={"role": "高三生", "goal": "数学130", "auto_opening": False},
    )
    assert r.status_code == 200
    assert r.json()["settings"]["correction_persistence"] == "balanced"

    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    for token in [
        "challenge",
        "confused_student",
        "correction_persistence",
        "setting-correction-persistence",
        "温和（只给反例）",
        "平衡（反例+求证提示）",
        "较真（紧盯改对）",
        "misconception",
    ]:
        assert token in html
