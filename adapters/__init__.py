"""平台适配器：把 Reverse Tutor 接到任意聊天平台。

每个适配器实现 BasePlatformAdapter 协议：
  - parse_incoming(body) -> (external_user_id, text)
  - format_outgoing(reply) -> dict（平台 SDK 的发送负载）
  - handshake(body)        -> dict | None   可选，平台首次接入握手（如飞书 url_verification）
  - verify(body, headers)  -> bool          可选，签名校验

会话映射通过持久化的 `bindings` 表（db.Binding）：
  (platform, external_id) -> session_id, onboarding_state

外部用户首次出现时，自动进入 3 步 onboarding（角色→目标→截止），完成后创建 session、
绑定、并跑开场。后续消息直接走核心引擎。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DbSession

from .base import BasePlatformAdapter
from .feishu import FeishuAdapter
from .qq import QQBotAdapter
from .hermes import HermesAdapter
from . import onboarding as _onb

REGISTRY: dict[str, BasePlatformAdapter] = {
    "feishu": FeishuAdapter(),
    "qq":     QQBotAdapter(),
    "hermes": HermesAdapter(),
}


async def dispatch_webhook(
    platform: str, body: dict, db_sess: DbSession, engine_mod
) -> dict[str, Any]:
    """把平台 webhook 派发到核心引擎，含自动绑定 + onboarding。"""
    adapter = REGISTRY.get(platform)
    if adapter is None:
        return {"ok": False, "error": f"unknown platform: {platform}"}

    # 1. 平台首次接入握手（如飞书 url_verification）
    handshake = adapter.handshake(body)
    if handshake is not None:
        return handshake

    # 2. 解析消息
    parsed = adapter.parse_incoming(body)
    if parsed is None:
        return {"ok": True, "skipped": "no message extractable"}
    external_id, text = parsed

    import db as db_mod

    # 3. 查 / 建绑定
    binding = db_mod.get_binding(db_sess, platform, external_id)
    if binding is None:
        binding = db_mod.create_binding(db_sess, platform, external_id)
        reply = _onb.WELCOME
        return _wrap(adapter, platform, external_id, None, reply,
                     action={"type": "onboarding", "knowledge_point": "setup"},
                     stage="welcome")

    # 4. 全局命令（任何状态可用）
    if text.strip() in ("/reset", "/help"):
        reply, stage = await _onb.handle(db_sess, binding, text, engine_mod)
        return _wrap(adapter, platform, external_id, binding.session_id, reply,
                     action={"type": "onboarding", "knowledge_point": stage},
                     stage=stage)

    # 5. 仍在 onboarding 中 → 走状态机
    if binding.onboarding_state != "active":
        reply, stage = await _onb.handle(db_sess, binding, text, engine_mod)
        sid = binding.session_id
        action = {"type": "onboarding", "knowledge_point": stage}
        return _wrap(adapter, platform, external_id, sid, reply, action, stage=stage)

    # 6. 已激活 → 走正常引擎
    sid = binding.session_id
    if not sid or not db_mod.get_session(db_sess, sid):
        # 会话被外部删了 → 重置 binding 重新引导
        db_mod.update_binding(
            db_sess, binding,
            session_id=None, onboarding_state="asking_role", onboarding_data={},
        )
        return _wrap(adapter, platform, external_id, None,
                     "（会话已不存在，让我们重新设定吧）\n\n" + _onb.WELCOME,
                     action={"type": "onboarding", "knowledge_point": "reset"},
                     stage="reset")

    result = await engine_mod.run_turn(db_sess, sid, text)
    return _wrap(adapter, platform, external_id, sid, result.reply,
                 action=result.action, evaluation=result.evaluation,
                 stage="active")


def _wrap(adapter, platform, external_id, sid, reply, action=None,
          evaluation=None, stage="active") -> dict[str, Any]:
    return {
        "ok": True,
        "platform": platform,
        "external_id": external_id,
        "session_id": sid,
        "stage": stage,
        "reply": reply,
        "action": action or {},
        "evaluation": evaluation or {},
        "platform_payload": adapter.format_outgoing(reply),
    }
