"""适配器单测：onboarding 状态机、握手、未知平台。"""
from __future__ import annotations

import pytest

import db
import engine
from adapters import dispatch_webhook


async def _send(platform, external_id, text, db_sess):
    return await dispatch_webhook(
        platform,
        {"external_id": external_id, "text": text},
        db_sess, engine,
    )


async def test_first_message_returns_welcome_and_creates_binding(db_sess):
    r = await _send("hermes", "alice", "hi", db_sess)
    assert r["ok"] is True
    assert r["stage"] == "welcome"
    assert "反转家教" in r["reply"]
    bindings = db.list_bindings(db_sess)
    assert len(bindings) == 1
    assert bindings[0].onboarding_state == "asking_role"


async def test_onboarding_full_flow_three_steps_then_active(db_sess):
    await _send("hermes", "bob", "hi", db_sess)
    r1 = await _send("hermes", "bob", "高三数学生", db_sess)
    assert r1["stage"] == "asking_goal"

    r2 = await _send("hermes", "bob", "数学 130 分", db_sess)
    assert r2["stage"] == "asking_deadline"

    r3 = await _send("hermes", "bob", "/skip", db_sess)
    assert r3["stage"] == "active"
    assert r3["session_id"]

    # binding 应包含完整 data
    b = db.get_binding(db_sess, "hermes", "bob")
    assert b.onboarding_state == "active"
    assert b.session_id is not None
    data = b.onboarding()
    assert data["role"] == "高三数学生"
    assert data["goal"] == "数学 130 分"


async def test_active_user_normal_turn_returns_action(db_sess):
    # 走完 onboarding
    for t in ["hi", "学生", "目标", "/skip"]:
        await _send("hermes", "carol", t, db_sess)
    r = await _send("hermes", "carol", "对称轴是 -b/2a", db_sess)
    assert r["stage"] == "active"
    assert r["action"]["type"] in engine.ACTION_TYPES


async def test_reset_command_in_active_state(db_sess):
    for t in ["hi", "学生", "目标", "/skip"]:
        await _send("hermes", "dan", t, db_sess)
    b = db.get_binding(db_sess, "hermes", "dan")
    assert b.onboarding_state == "active"

    r = await _send("hermes", "dan", "/reset", db_sess)
    assert r["stage"] == "reset"
    b = db.get_binding(db_sess, "hermes", "dan")
    assert b.onboarding_state == "asking_role"
    assert b.session_id is None


async def test_unknown_platform_returns_error(db_sess):
    r = await dispatch_webhook("wechat", {"text": "hi"}, db_sess, engine)
    assert r["ok"] is False
    assert "unknown" in r["error"].lower()


async def test_feishu_url_verification_handshake(db_sess):
    r = await dispatch_webhook(
        "feishu",
        {"type": "url_verification", "challenge": "xyz"},
        db_sess, engine,
    )
    assert r == {"challenge": "xyz"}


async def test_orphaned_binding_triggers_rebind(db_sess):
    """如果 binding 指向一个不存在的 session（例如 session 在外部被删），
    下次消息应自动重置 binding 进入 onboarding。"""
    b = db.create_binding(db_sess, "hermes", "ghost-user")
    db.update_binding(db_sess, b,
                      session_id="nonexistent-sid",
                      onboarding_state="active",
                      onboarding_data={"role": "x"})
    r = await _send("hermes", "ghost-user", "hello?", db_sess)
    assert r["stage"] == "reset"
    b_after = db.get_binding(db_sess, "hermes", "ghost-user")
    assert b_after.onboarding_state == "asking_role"
    assert b_after.session_id is None
