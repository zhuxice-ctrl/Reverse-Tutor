"""数据层单元测试。"""
from __future__ import annotations

import pytest

import db


def test_create_session_and_get(db_sess):
    s = db.Session(
        id="abc12345", title="t",
        persona_json='{"role":"r","goal":"g"}', plan_json="[]",
    )
    db_sess.add(s); db_sess.commit()
    got = db.get_session(db_sess, "abc12345")
    assert got is not None and got.title == "t"
    assert got.persona()["role"] == "r"


def test_add_anchor_and_list_orders_by_weight(db_sess):
    sid = "s1"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db.add_anchor(db_sess, sid, "initial", "init", weight=3.0)
    db.add_anchor(db_sess, sid, "requirement", "low", weight=1.0)
    db.add_anchor(db_sess, sid, "requirement", "mid", weight=2.0)
    db_sess.commit()
    anchors = db.list_anchors(db_sess, sid)
    assert [a.weight for a in anchors] == [3.0, 2.0, 1.0]


def test_upsert_mastery_ema_increases_and_caps(db_sess):
    sid = "s2"
    db_sess.add(db.Session(id=sid, title="t", persona_json="{}", plan_json="[]"))
    db_sess.commit()
    # 第一次：alpha=0.35, level ≈ 0.35 * (0.5*1 + 0.5*1) = 0.35
    m = db.upsert_mastery(db_sess, sid, "kp1", correctness=1.0, depth=1.0)
    db_sess.commit()
    assert m.attempts == 1
    assert 0.30 < m.level < 0.40

    # 多次累积应单调提高，但永远 <= 1
    for _ in range(20):
        m = db.upsert_mastery(db_sess, sid, "kp1", correctness=1.0, depth=1.0)
        db_sess.commit()
    assert m.attempts == 21
    assert 0.95 < m.level <= 1.0


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
    db.upsert_mastery(db_sess, sid, "kp", 0.5, 0.5)
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
