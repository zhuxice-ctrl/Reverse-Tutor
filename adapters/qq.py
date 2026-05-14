"""QQ Bot 适配器（MVP stub）。

兼容主流 QQ Bot 框架的 webhook 入站结构（如 go-cqhttp / onebot-v11，QQ 官方 Bot Open Platform）：
  body = {
    "post_type": "message",
    "message_type": "private" | "group",
    "user_id": 123,
    "group_id": 456,
    "raw_message": "你好"
  }

发送回复通过 OneBot API（/send_private_msg 或 /send_group_msg），此处仅产出 payload。
"""
from __future__ import annotations

from typing import Any

from .base import BasePlatformAdapter


class QQBotAdapter(BasePlatformAdapter):
    name = "qq"

    def parse_incoming(self, body: dict) -> tuple[str, str] | None:
        if body.get("post_type") not in (None, "message"):
            return None
        text = (body.get("raw_message") or body.get("message") or "").strip()
        if not text:
            return None
        user_id = body.get("user_id") or body.get("sender", {}).get("user_id") or "anon"
        group_id = body.get("group_id")
        external = f"qq:{group_id}:{user_id}" if group_id else f"qq:{user_id}"
        return external, str(text)

    def format_outgoing(self, reply: str) -> dict[str, Any]:
        return {"reply": reply, "auto_escape": False}
