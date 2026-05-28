from __future__ import annotations

from datetime import datetime, timedelta

import db
import engine


def _due_mastery(db_sess, sid: str, kp: str, *, days_ago: int = 1) -> db.Mastery:
    m = db.upsert_mastery(
        db_sess,
        sid,
        kp,
        correctness=0.7,
        depth=0.6,
        evidence_type="explanation",
        verification_status="passed",
    )
    m.next_review_at = datetime.utcnow() - timedelta(days=days_ago)
    db_sess.commit()
    return m


def test_list_due_reviews_returns_due_items_only(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    due = _due_mastery(db_sess, s.id, "二次函数对称轴")
    future = db.upsert_mastery(
        db_sess,
        s.id,
        "判别式",
        correctness=0.7,
        depth=0.6,
        evidence_type="explanation",
        verification_status="passed",
    )
    future.next_review_at = datetime.utcnow() + timedelta(days=2)
    db_sess.commit()

    reviews = db.list_due_reviews(db_sess, s.id, datetime.utcnow())

    assert [m.knowledge_point for m in reviews] == [due.knowledge_point]


def test_review_interval_advances_on_passed_evidence(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    intervals = []
    for _ in range(4):
        m = db.upsert_mastery(
            db_sess,
            s.id,
            "二次函数对称轴",
            correctness=0.8,
            depth=0.7,
            evidence_type="delayed_retrieval",
            verification_status="passed",
        )
        intervals.append(m.review_interval)
        assert m.next_review_at is not None

    assert intervals == [1, 3, 7, 14]


def test_failed_review_resets_interval_to_one_day(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    m = db.upsert_mastery(
        db_sess,
        s.id,
        "二次函数对称轴",
        correctness=0.8,
        depth=0.7,
        evidence_type="delayed_retrieval",
        verification_status="passed",
    )
    m.review_interval = 14
    m.next_review_at = datetime.utcnow() - timedelta(days=1)
    db_sess.commit()

    m = db.upsert_mastery(
        db_sess,
        s.id,
        "二次函数对称轴",
        correctness=0.1,
        depth=0.1,
        evidence_type="delayed_retrieval",
        verification_status="failed",
    )

    assert m.review_interval == 1
    assert m.next_review_at is not None
    assert timedelta(hours=20) <= (m.next_review_at - datetime.utcnow()) <= timedelta(hours=28)


async def test_due_review_does_not_interrupt_user_progress(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    _due_mastery(db_sess, s.id, "二次函数对称轴")

    result = await engine.run_turn(db_sess, s.id, "懂了，继续下一个")

    assert result.action["type"] in {"examiner_verify", "next"}
    assert "系统检测到 1 个旧知识点到期" in result.process_summary
    assert "是否带回视用户回复决定" in result.process_summary


async def test_due_review_prompt_contains_soft_interleaving_instruction(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    _due_mastery(db_sess, s.id, "二次函数对称轴")
    captured = {}

    async def fake_chat_json(system, messages, **kwargs):
        captured["system"] = system
        return {
            "evaluation": {
                "correctness": 0.4,
                "depth": 0.3,
                "entry_status": "has_entry",
                "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
                "user_emotion": "neutral",
                "new_requirements": [],
            },
            "action": {
                "type": "probe",
                "student_role": "probing_student",
                "knowledge_point": "判别式",
                "difficulty": 0.5,
                "note": "soft review prompt test",
            },
            "reply": "老师，这里我想追问一下为什么。",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "因为这里可以先判断条件")

    assert "到期复习软提示" in captured["system"]
    assert "二次函数对称轴" in captured["system"]
    assert "不强制打断" in captured["system"]
    assert "顺带把" in captured["system"]
