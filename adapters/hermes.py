"""Hermes 适配器 —— 作为 Hermes 等 Agent 编排框架的"子模块"暴露。

Hermes（或任意 Agent 框架）可以把本服务当成一个工具/技能：
  POST /api/adapters/hermes/webhook
  {
    "session_id": "可选；不传则用 external_id",
    "external_id": "调用方的会话标识",
    "text": "用户输入"
  }

返回：
  {
    "ok": true,
    "reply": "...",
    "action": {...},
    "platform_payload": {"text": "..."}
  }

这样 Hermes 调用方只需 HTTP POST，无须关心引擎细节，且本服务对所有外部 Agent 框架表现一致。
"""
from __future__ import annotations

from typing import Any

from .base import BasePlatformAdapter


class HermesAdapter(BasePlatformAdapter):
    name = "hermes"

    def parse_incoming(self, body: dict) -> tuple[str, str] | None:
        text = (body.get("text") or body.get("message") or "").strip()
        if not text:
            return None
        external = body.get("external_id") or body.get("user_id") or "hermes-anon"
        return str(external), text

    def format_outgoing(self, reply: str) -> dict[str, Any]:
        return {"text": reply}
