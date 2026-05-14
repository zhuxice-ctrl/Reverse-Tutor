"""飞书（Feishu / Lark）开放平台适配器（MVP stub）。

实际接入需在飞书开放平台：
  1. 创建企业自建应用，开启"机器人"能力
  2. 配置事件订阅：im.message.receive_v1
  3. 把 URL 配为 https://<your>/api/adapters/feishu/webhook
  4. 校验时飞书会发送 challenge → 本适配器在 handshake() 返回 {challenge: ...}

发送回复需调用飞书 IM OpenAPI（POST /open-apis/im/v1/messages）+ tenant_access_token，
此处仅返回结构化 payload，由上层调度真正发送（生产环境单独跑 sender worker）。
"""
from __future__ import annotations

import json
from typing import Any

from .base import BasePlatformAdapter


class FeishuAdapter(BasePlatformAdapter):
    name = "feishu"

    def handshake(self, body: dict) -> dict[str, Any] | None:
        # 飞书 URL 验证
        if body.get("type") == "url_verification" and "challenge" in body:
            return {"challenge": body["challenge"]}
        return None

    def parse_incoming(self, body: dict) -> tuple[str, str] | None:
        # 飞书 v2 事件结构：{ "header": {...}, "event": { "message": { "content": "{\"text\": \"..\"}" }, "sender": {...} } }
        event = body.get("event") or {}
        msg = event.get("message") or {}
        sender = event.get("sender") or {}
        sender_id = (
            (sender.get("sender_id") or {}).get("user_id")
            or (sender.get("sender_id") or {}).get("open_id")
            or sender.get("sender_id")
            or "unknown"
        )

        raw_content = msg.get("content") or ""
        text = ""
        try:
            parsed = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            text = (parsed or {}).get("text", "").strip()
        except Exception:
            text = str(raw_content).strip()

        if not text:
            return None
        return str(sender_id), text

    def format_outgoing(self, reply: str) -> dict[str, Any]:
        # 飞书发送消息接口的 content 字段需要 JSON 字符串
        return {
            "msg_type": "text",
            "content": json.dumps({"text": reply}, ensure_ascii=False),
        }
