"""平台适配器抽象基类。"""
from __future__ import annotations

from typing import Any


class BasePlatformAdapter:
    name: str = "base"

    def handshake(self, body: dict) -> dict[str, Any] | None:
        """平台首次接入握手（如飞书的 url_verification）。返回非 None 即为响应。"""
        return None

    def parse_incoming(self, body: dict) -> tuple[str, str] | None:
        """解析消息：返回 (external_user_id, text)，不可解析返回 None。"""
        raise NotImplementedError

    def format_outgoing(self, reply: str) -> dict[str, Any]:
        """把回复包装成平台 SDK 发送负载。"""
        return {"text": reply}

    def verify(self, body: dict, headers: dict | None = None) -> bool:
        return True
