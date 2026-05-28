from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import db
import engine
import kg_extractor as kg
import kg_retriever as kr


def _session(db_sess, sid: str = "kg-retrieve") -> db.Session:
    s = engine.create_session(db_sess, title="", role="student", goal="local test")
    s.id = sid
    db_sess.commit()
    return s


def _user(db_sess, sid: str):
    return db.upsert_kg_node(db_sess, sid, "person", "用户")


def test_retrieve_empty_context_without_graph_data(db_sess):
    _session(db_sess)

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.is_empty()


def test_retrieve_related_concepts_from_direct_edges(db_sess):
    _session(db_sess)
    a = db.upsert_kg_node(db_sess, "kg-retrieve", "concept", "极值点偏移")
    b = db.upsert_kg_node(db_sess, "kg-retrieve", "concept", "对称轴")
    db.upsert_kg_edge(db_sess, "kg-retrieve", a.id, b.id, "相关")

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert "对称轴" in ctx.related_concepts


def test_retrieve_prereq_relation_marks_related_concept(db_sess):
    _session(db_sess)
    prereq = db.upsert_kg_node(db_sess, "kg-retrieve", "concept", "对称轴")
    current = db.upsert_kg_node(db_sess, "kg-retrieve", "concept", "极值点偏移")
    db.upsert_kg_edge(db_sess, "kg-retrieve", prereq.id, current.id, "前置于")

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert "[前置] 对称轴" in ctx.related_concepts


def test_retrieve_historical_errors_for_current_kp(db_sess):
    _session(db_sess)
    user = _user(db_sess, "kg-retrieve")
    err = db.upsert_kg_node(db_sess, "kg-retrieve", kg.KIND_ERROR, "符号错")
    db.upsert_kg_edge(db_sess, "kg-retrieve", user.id, err.id, kg.REL_ERROR_ON, properties={"kp": "极值点偏移"})

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.historical_errors == ["符号错"]


def test_retrieve_misunderstandings_for_current_kp(db_sess):
    _session(db_sess)
    user = _user(db_sess, "kg-retrieve")
    concept = db.upsert_kg_node(db_sess, "kg-retrieve", "concept", "极值点偏移")
    db.upsert_kg_edge(db_sess, "kg-retrieve", user.id, concept.id, kg.REL_MISUNDERSTOOD, properties={"reason": "recall_decay"})

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.misunderstandings == ["极值点偏移: recall_decay"]


def test_retrieve_preferences(db_sess):
    _session(db_sess)
    user = _user(db_sess, "kg-retrieve")
    pref = db.upsert_kg_node(db_sess, "kg-retrieve", kg.KIND_PREFERENCE, "图像直观优先")
    db.upsert_kg_edge(db_sess, "kg-retrieve", user.id, pref.id, kg.REL_PREFERENCE)

    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.preferences == ["图像直观优先"]


def test_mark_review_pending_is_retrieved(db_sess):
    _session(db_sess)

    kr.mark_review_pending(db_sess, "kg-retrieve", "判别式", episode_id=7)
    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.pending_review_kps == ["判别式"]


def test_clear_review_pending_hides_pending_kp(db_sess):
    _session(db_sess)
    kr.mark_review_pending(db_sess, "kg-retrieve", "判别式")

    kr.clear_review_pending(db_sess, "kg-retrieve", "判别式")
    ctx = kr.retrieve_kg_context(db_sess, "kg-retrieve", "极值点偏移")

    assert ctx.pending_review_kps == []


def test_format_for_prompt_includes_sections():
    ctx = kr.KGContext(
        related_concepts=["对称轴"],
        historical_errors=["符号错"],
        preferences=["图像直观优先"],
        pending_review_kps=["判别式"],
    )

    text = ctx.format_for_prompt()

    assert "# 知识图谱上下文" in text
    assert "## 相关/前置概念" in text
    assert "## 用户历史错因" in text
    assert "## 用户学习偏好" in text
    assert "## 挂起待复习" in text


def test_kg_context_is_empty_reflects_content():
    assert kr.KGContext().is_empty()
    assert not kr.KGContext(related_concepts=["对称轴"]).is_empty()


async def test_run_turn_system_prompt_includes_kg_context(db_sess, monkeypatch):
    s = _session(db_sess)
    user = _user(db_sess, s.id)
    err = db.upsert_kg_node(db_sess, s.id, kg.KIND_ERROR, "符号错")
    db.upsert_kg_edge(db_sess, s.id, user.id, err.id, kg.REL_ERROR_ON, properties={"kp": "极值点偏移"})
    captured = {}

    async def fake_chat_json(system, messages, **kwargs):
        captured["system"] = system
        return {
            "evaluation": {
                "correctness": 0.4,
                "depth": 0.3,
                "entry_status": "has_entry",
                "error_pattern": "",
                "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
                "user_emotion": "neutral",
                "new_requirements": [],
            },
            "action": {"type": "probe", "student_role": "probing_student", "knowledge_point": "极值点偏移", "difficulty": 0.5, "note": ""},
            "reply": "老师，我想继续追问。",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)
    await engine.run_turn(db_sess, s.id, "极值点偏移这里我又符号错了")

    assert "知识图谱上下文" in captured["system"]
    assert "符号错" in captured["system"]


def test_retrieve_context_is_session_isolated(db_sess):
    _session(db_sess, "A")
    _session(db_sess, "B")
    user = _user(db_sess, "A")
    err = db.upsert_kg_node(db_sess, "A", kg.KIND_ERROR, "符号错")
    db.upsert_kg_edge(db_sess, "A", user.id, err.id, kg.REL_ERROR_ON, properties={"kp": "极值点偏移"})

    assert kr.retrieve_kg_context(db_sess, "B", "极值点偏移").historical_errors == []


async def test_retrieval_exception_does_not_block_run_turn(db_sess, monkeypatch):
    s = _session(db_sess)
    db.upsert_mastery(
        db_sess,
        s.id,
        "旧知识",
        correctness=0.8,
        depth=0.8,
        evidence_type="retrieval",
        verification_status="passed",
    ).next_review_at = datetime.utcnow() - timedelta(days=1)
    db_sess.commit()

    def boom(*args, **kwargs):
        raise RuntimeError("retriever down")

    monkeypatch.setattr(engine, "retrieve_kg_context", boom)
    result = await engine.run_turn(db_sess, s.id, "先不管这个复习，继续")

    assert result.reply
    assert kr.retrieve_kg_context(db_sess, s.id, "当前方法").pending_review_kps == ["旧知识"]
