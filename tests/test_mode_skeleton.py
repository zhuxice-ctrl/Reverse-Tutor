from __future__ import annotations

from sqlalchemy import inspect, select

import db
import engine


def test_goal_prompt_uses_goal_action_set_without_study_residue(db_sess):
    s = engine.create_session(
        db_sess,
        title="",
        role="项目推进伙伴",
        goal="两周内完成作品集",
        mode="goal",
    )

    prompt = engine.build_system_prompt(s, [], [])

    assert "核心指标：完成度" in prompt
    assert "拆解 → 推进 → 验收 → 下一步" in prompt
    assert "decompose" in prompt
    assert "advance" in prompt
    assert "verify_done" in prompt
    assert "unblock" in prompt
    assert "examiner_verify" not in prompt
    assert "用户掌握度" not in prompt


async def test_goal_mode_does_not_emit_examiner_verify_or_write_mastery(db_sess, monkeypatch):
    s = engine.create_session(
        db_sess,
        title="",
        role="项目推进伙伴",
        goal="两周内完成作品集",
        mode="goal",
    )

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "evaluation": {
                "correctness": 0.9,
                "depth": 0.8,
                "entry_status": "has_entry",
                "evidence_for_mastery": {"type": "explanation", "status": "passed", "error_type": "", "reason": ""},
                "user_emotion": "engaged",
                "new_requirements": [],
            },
            "action": {
                "type": "examiner_verify",
                "student_role": "examiner",
                "knowledge_point": "作品集首页",
                "difficulty": 0.4,
                "note": "study residue",
            },
            "reply": "那我来考考你。",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "懂了，首页已经改完")

    assert result.action["type"] == "verify_done"
    assert result.action["type"] != "examiner_verify"
    assert db.list_mastery(db_sess, s.id) == []


async def test_companion_mode_does_not_emit_correction_or_write_mastery(db_sess, monkeypatch):
    s = engine.create_session(
        db_sess,
        title="",
        role="陪伴型朋友",
        goal="稳定记录最近的心情",
        mode="companion",
    )

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "evaluation": {
                "correctness": 0.1,
                "depth": 0.1,
                "entry_status": "has_entry",
                "evidence_for_mastery": {
                    "type": "correction",
                    "status": "failed",
                    "error_type": "表达不清",
                    "reason": "companion should not correct",
                },
                "user_emotion": "frustrated",
                "new_requirements": [],
            },
            "action": {
                "type": "examiner_verify",
                "student_role": "examiner",
                "knowledge_point": "情绪记录",
                "difficulty": 0.3,
                "note": "study residue",
            },
            "reply": "你这里说得不对。",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "今天有点烦，不想被纠正")

    assert result.action["type"] in {"empathize", "observe", "soft_guide"}
    assert result.action["type"] != "correction"
    assert result.evaluation["evidence_for_mastery"]["type"] != "correction"
    assert db.list_mastery(db_sess, s.id) == []


def test_goal_and_companion_state_tables_exist_and_are_initialized(db_sess):
    tables = set(inspect(db.engine).get_table_names())

    assert "goal_state" in tables
    assert "companion_state" in tables

    goal = engine.create_session(db_sess, title="", role="推进伙伴", goal="完成作品集", mode="goal")
    companion = engine.create_session(db_sess, title="", role="陪伴朋友", goal="记录心情", mode="companion")

    assert db_sess.scalar(select(db.GoalState).where(db.GoalState.session_id == goal.id)) is not None
    assert db_sess.scalar(select(db.CompanionState).where(db.CompanionState.session_id == companion.id)) is not None
