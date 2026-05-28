from __future__ import annotations

import random

import db
import engine


def test_system_prompt_contains_clue_student_expression_contract(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    prompt = engine.build_system_prompt(s, [], [])

    assert "student_role=clue_student" in prompt
    assert "老师，据说" in prompt
    assert "老师，我听说" in prompt
    assert "我来教你" in prompt
    assert "一次最多给一个例子或一个第一步线索" in prompt


async def test_clue_student_reply_uses_student_opening_and_no_teacher_phrases(
    db_sess, monkeypatch
):
    s = engine.create_session(db_sess, title="", role="高三生", goal="方法学习")
    monkeypatch.setattr(random, "choice", lambda pool: pool[-1])

    result = await engine.run_turn(db_sess, s.id, "老师我完全没听过极值点偏移，这是什么")

    assert result.action["student_role"] == "clue_student"
    assert result.reply.startswith(("老师，据说", "老师，我听说"))
    for banned in ("我来教你", "步骤如下", "根据定义"):
        assert banned not in result.reply


async def test_observation_after_clue_forces_probe(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="方法学习")
    first = await engine.run_turn(db_sess, s.id, "老师我完全没听过极值点偏移，这是什么")
    assert first.action["student_role"] == "clue_student"

    result = await engine.run_turn(db_sess, s.id, "我觉得是不是先看普通方法为什么卡住")

    assert result.action["type"] == "probe"
    assert result.action["student_role"] == "probing_student"
    assert result.evaluation["entry_status"] == "has_entry"


async def test_learning_state_record_blocks_no_entry_when_recent_steps_exist(
    db_sess, monkeypatch
):
    s = engine.create_session(db_sess, title="", role="高三生", goal="方法学习")
    db.upsert_mastery(
        db_sess,
        s.id,
        "二次函数对称轴",
        correctness=0.6,
        depth=0.5,
        evidence_type="explanation",
        verification_status="passed",
    )
    db_sess.commit()

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "evaluation": {
                "correctness": 0.0,
                "depth": 0.0,
                "entry_status": "no_entry",
                "evidence_for_mastery": {
                    "type": "none",
                    "status": "none",
                    "error_type": "",
                    "reason": "",
                },
                "user_emotion": "neutral",
                "new_requirements": [],
            },
            "action": {
                "type": "clue",
                "student_role": "clue_student",
                "knowledge_point": "二次函数对称轴",
                "difficulty": 0.5,
                "note": "mocked no_entry despite existing state",
            },
            "reply": "老师，据说先看对称轴就行？",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "先找对称轴，再代入顶点公式判断最值")

    assert result.evaluation["entry_status"] == "has_entry"
    assert result.action["type"] != "clue"
    assert result.action["student_role"] == "probing_student"
