"""引擎单测（全部在 mock LLM 模式下跑）。"""
from __future__ import annotations

import pytest

import db
import engine


def test_create_session_writes_initial_anchor(db_sess):
    s = engine.create_session(
        db_sess, title="", role="高三生", goal="数学130",
        deadline="2026", initial_requirements=["重点函数", "循序渐进"],
    )
    assert len(s.id) == 12
    anchors = db.list_anchors(db_sess, s.id)
    kinds = [a.kind for a in anchors]
    assert "initial" in kinds
    # 两条初始 requirement
    reqs = [a for a in anchors if a.kind == "requirement"]
    assert len(reqs) == 2
    # initial 权重最高
    initial = next(a for a in anchors if a.kind == "initial")
    assert initial.weight >= max(r.weight for r in reqs)


async def test_run_opening_turn_produces_assistant_message(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    # create_session 不会自动 opening，这里手动跑
    before = len(db.list_messages(db_sess, s.id))
    result = await engine.run_opening_turn(db_sess, s.id)
    assert result.reply
    msgs = db.list_messages(db_sess, s.id)
    assert len(msgs) == before + 1
    assert msgs[-1].role == "assistant"
    assert msgs[-1].meta().get("opening") is True


async def test_run_turn_persists_user_and_assistant_and_updates_mastery(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    r1 = await engine.run_turn(db_sess, s.id, "对称轴是 x=-b/(2a)")
    assert r1.reply
    assert r1.action.get("type") in engine.ACTION_TYPES

    msgs = db.list_messages(db_sess, s.id)
    roles = [m.role for m in msgs]
    assert "user" in roles and "assistant" in roles

    # mock 引擎会把 kp 设为"二次函数对称轴"，mastery 应该有一条
    masteries = db.list_mastery(db_sess, s.id)
    assert len(masteries) >= 1
    assert masteries[0].attempts >= 1


async def test_anchor_updates_persist_when_user_mentions_requirement(db_sess):
    """mock 引擎检测到关键字 '重点' 会把它放进 anchor_updates。"""
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    before = len(db.list_anchors(db_sess, s.id))
    await engine.run_turn(db_sess, s.id, "我想重点搞函数和导数")
    after = db.list_anchors(db_sess, s.id)
    assert len(after) > before
    # 最新一条应包含触发关键字
    assert any("重点" in a.content for a in after)


async def test_summarize_below_threshold_returns_none(db_sess):
    s = engine.create_session(db_sess, title="", role="r", goal="g")
    # 只灌几条，远不到 30
    for i in range(3):
        await engine.run_turn(db_sess, s.id, f"answer {i}")
    info = await engine.maybe_summarize(db_sess, s.id)
    assert info is None


async def test_summarize_force_compresses_even_below_threshold(db_sess):
    s = engine.create_session(db_sess, title="", role="r", goal="g")
    await engine.run_turn(db_sess, s.id, "msg1")
    await engine.run_turn(db_sess, s.id, "msg2")
    info = await engine.maybe_summarize(db_sess, s.id, force=True)
    assert info is not None
    assert info["summarized_count"] >= 1
    # summary 写入了 messages 表
    msgs = db.list_messages(db_sess, s.id)
    summaries = [m for m in msgs if m.role == "system" and m.meta().get("kind") == "summary"]
    assert len(summaries) == 1
    meta = summaries[0].meta()
    assert "summarized_until_id" in meta and "summarized_count" in meta


async def test_summarize_auto_triggers_above_threshold(db_sess):
    s = engine.create_session(db_sess, title="", role="r", goal="g")
    # SUMMARY_THRESHOLD = 30，每轮产生 2 条 (user+assistant)，跑 16 轮 = 32 条
    for i in range(16):
        await engine.run_turn(db_sess, s.id, f"answer {i}")
    msgs = db.list_messages(db_sess, s.id)
    summaries = [m for m in msgs if m.role == "system" and m.meta().get("kind") == "summary"]
    assert len(summaries) >= 1


async def test_build_messages_skips_compressed_history(db_sess):
    s = engine.create_session(db_sess, title="", role="r", goal="g")
    await engine.run_turn(db_sess, s.id, "old1")
    await engine.run_turn(db_sess, s.id, "old2")
    await engine.maybe_summarize(db_sess, s.id, force=True)
    # 再发两条新消息
    await engine.run_turn(db_sess, s.id, "new1")
    msgs = db.list_messages(db_sess, s.id)
    summary = engine._latest_summary(msgs)
    assert summary is not None
    cutoff = summary.meta()["summarized_until_id"]
    rendered = engine.build_messages(msgs, None, skip_until_id=cutoff)
    # old1/old2 的内容不应在 rendered 里
    contents = [m["content"] for m in rendered]
    assert not any("old1" in c for c in contents)
    assert any("new1" in c for c in contents)
