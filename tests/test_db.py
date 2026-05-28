"""数据层单元测试。"""
from __future__ import annotations

import pytest

import db


def test_create_session_and_get(db_sess):
    s = db.Session(
        id="abc12345", title="t",
        persona_json='{"role":"r","goal":"g"}', plan_json="[]",
        mode="study", core_self="我怕被否定但讨厌空洞安慰",
    )
    db_sess.add(s); db_sess.commit()
    got = db.get_session(db_sess, "abc12345")
    assert got is not None and got.title == "t"
    assert got.persona()["role"] == "r"
    assert got.mode == "study"
    assert got.core_self == "我怕被否定但讨厌空洞安慰"


def test_add_anchor_and_list_orders_by_weight(db_sess):
    sid = "s1"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db.add_anchor(db_sess, sid, "initial", "init", weight=3.0)
    db.add_anchor(db_sess, sid, "requirement", "low", weight=1.0)
    db.add_anchor(db_sess, sid, "requirement", "mid", weight=2.0)
    db_sess.commit()
    anchors = db.list_anchors(db_sess, sid)
    assert [a.weight for a in anchors] == [3.0, 2.0, 1.0]


def test_upsert_mastery_requires_evidence_before_score_increases(db_sess):
    sid = "s2"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()

    # 没有学习证据：记录尝试和错因，但不提高掌握度
    m = db.upsert_mastery(db_sess, sid, "kp1", correctness=1.0, depth=1.0)
    db_sess.commit()
    assert m.attempts == 1
    assert m.level == 0.0
    assert m.mastery_score == 0.0
    assert m.last_evidence_type == "none"

    # 通过解释验证：使用 evidence_score=35 的 EMA，level 是兼容字段
    m = db.upsert_mastery(
        db_sess, sid, "kp1",
        correctness=1.0, depth=1.0,
        evidence_type="explanation",
        verification_status="passed",
        evidence_episode_id=12,
    )
    db_sess.commit()
    assert m.attempts == 2
    assert 12.0 <= m.mastery_score <= 13.0
    assert 0.12 <= m.level <= 0.13
    assert m.evidence_ids() == [12]
    assert m.last_evidence_type == "explanation"
    assert m.last_verification_status == "passed"


def test_mastery_failed_verification_records_error_without_increase(db_sess):
    sid = "s2b"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()

    m = db.upsert_mastery(
        db_sess, sid, "kp1",
        correctness=1.0, depth=1.0,
        evidence_type="retrieval",
        verification_status="passed",
        evidence_episode_id=20,
    )
    before = m.mastery_score
    m = db.upsert_mastery(
        db_sess, sid, "kp1",
        correctness=0.1, depth=0.1,
        evidence_type="retrieval",
        verification_status="failed",
        evidence_episode_id=21,
        error_type="适用条件混淆",
    )
    db_sess.commit()

    assert m.mastery_score <= before
    assert m.error_type == "适用条件混淆"
    assert m.evidence_ids() == [20, 21]
    assert m.last_verification_status == "failed"


def test_add_episode_stores_append_only_system_message(db_sess):
    sid = "episode-test"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()

    ep = db.add_episode(
        db_sess, sid,
        kind="image_ocr",
        content="题干：已识别出的文字",
        meta={"source": "upload"},
    )
    db_sess.commit()

    msgs = db.list_messages(db_sess, sid)
    assert msgs[-1].id == ep.id
    assert msgs[-1].role == "system"
    assert msgs[-1].meta()["kind"] == "image_ocr"
    assert msgs[-1].meta()["source"] == "upload"


def test_binding_unique_constraint(db_sess):
    db.create_binding(db_sess, "feishu", "user-1")
    with pytest.raises(Exception):
        db.create_binding(db_sess, "feishu", "user-1")
        db_sess.commit()


def test_delete_session_cascades(db_sess):
    sid = "del-test"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db.add_anchor(db_sess, sid, "initial", "x", weight=1.0)
    db.add_message(db_sess, sid, "user", "hi")
    db.upsert_mastery(
        db_sess, sid, "kp", 0.5, 0.5,
        evidence_type="explanation",
        verification_status="passed",
    )
    b = db.create_binding(db_sess, "hermes", "ext-x")
    db.update_binding(db_sess, b, session_id=sid)
    db_sess.commit()

    assert db.delete_session(db_sess, sid) is True
    assert db.get_session(db_sess, sid) is None
    assert db.list_anchors(db_sess, sid) == []
    assert db.list_messages(db_sess, sid) == []
    assert db.list_mastery(db_sess, sid) == []
    # binding 的 session_id 应被清，但 binding 本身（按当前实现）被一同删除
    remaining = [x for x in db.list_bindings(db_sess) if x.session_id == sid]
    assert remaining == []


def test_message_meta_roundtrip(db_sess):
    sid = "m1"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()
    db.add_message(db_sess, sid, "assistant", "hi", meta={"action": {"type": "ask"}})
    db_sess.commit()
    msgs = db.list_messages(db_sess, sid)
    assert msgs[0].meta()["action"]["type"] == "ask"
