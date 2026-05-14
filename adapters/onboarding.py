"""引导式 Onboarding 状态机。

当外部平台用户首次出现（无 binding），bot 通过 3 轮反问收集 role / goal / deadline，
然后自动创建 session、绑定、并跑开场。

状态流：
  asking_role  --(用户答)--> asking_goal --(用户答)--> asking_deadline --(用户答)--> active

特殊命令：
  /reset   清空当前 binding（重新引导）
  /help    显示帮助
  /skip    在 asking_deadline 阶段可跳过截止时间
"""
from __future__ import annotations

from typing import Any

import db as db_mod


WELCOME = (
    "👋 你好！我是 **反转家教 AI**。\n"
    "我会扮演一名**学生**，你来当我的老师。我会主动向你请教问题——你"
    "在教我的过程中，自己的理解就会变深。\n\n"
    "先告诉我：**你希望我扮演什么角色？**\n"
    "例如：高三数学生 / 考研英语党 / Python 编程小白 / 雅思考生"
)

ASK_GOAL_TPL = (
    "好的，{role}！\n\n那这个 {role} 想达成什么**目标**？\n"
    "例如：一年内数学考 130 分 / 雅思口语稳定 7.0 / 3 个月内能独立写 Python 小工具"
)

ASK_DEADLINE_TPL = (
    "目标记下了：「{goal}」\n\n**截止时间**呢？（回复 /skip 跳过）\n"
    "例如：2026 年 6 月高考 / 3 个月内"
)

HELP = (
    "可用命令：\n"
    "  /help   显示帮助\n"
    "  /reset  重置会话，重新设定角色\n"
    "  /skip   在被问截止时间时跳过\n"
    "  /anchors 查看当前主线锚\n"
)


async def handle(
    db_sess, binding: db_mod.Binding, text: str, engine_mod
) -> tuple[str, str]:
    """处理 onboarding 阶段的一条消息。

    返回 (reply_text, next_state_label) 用于上层日志/响应。
    """
    text = text.strip()

    # 全局命令
    if text in ("/reset",):
        db_mod.update_binding(
            db_sess, binding,
            session_id=None, onboarding_state="asking_role", onboarding_data={},
        )
        return WELCOME, "reset"

    if text in ("/help",):
        return HELP, "help"

    state = binding.onboarding_state
    data: dict[str, Any] = binding.onboarding()
    return await _step(db_sess, binding, text, engine_mod, state, data)


async def _step(db_sess, binding, text: str, engine_mod, state: str, data: dict) -> tuple[str, str]:
    if state == "asking_role":
        data["role"] = text
        db_mod.update_binding(
            db_sess, binding,
            onboarding_state="asking_goal", onboarding_data=data,
        )
        return ASK_GOAL_TPL.format(role=text), "asking_goal"

    if state == "asking_goal":
        data["goal"] = text
        db_mod.update_binding(
            db_sess, binding,
            onboarding_state="asking_deadline", onboarding_data=data,
        )
        return ASK_DEADLINE_TPL.format(goal=text), "asking_deadline"

    if state == "asking_deadline":
        deadline = "" if text in ("/skip", "skip", "无", "暂无", "no") else text
        data["deadline"] = deadline
        # 创建 session
        s = engine_mod.create_session(
            db_sess,
            title=f"{data['role']} · {data['goal']}",
            role=data["role"],
            goal=data["goal"],
            deadline=deadline,
        )
        db_mod.update_binding(
            db_sess, binding,
            session_id=s.id, onboarding_state="active", onboarding_data=data,
        )
        # 跑开场
        try:
            result = await engine_mod.run_opening_turn(db_sess, s.id)
            opening = result.reply
        except Exception as e:
            opening = "（嗯……老师在吗？我们什么时候开始？）"
        prelude = f"✅ 设定完成，会话已创建（id `{s.id}`）。\n开始上课～\n\n🎓 "
        return prelude + opening, "active"

    # 未知状态，重置
    db_mod.update_binding(
        db_sess, binding,
        session_id=None, onboarding_state="asking_role", onboarding_data={},
    )
    return WELCOME, "reset_unknown"
