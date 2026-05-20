"""Trial-code backed LLM proxy.

The client receives only a short-lived trial token. The real provider API key
stays on the server and every request is checked against per-code quotas.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

import db


DEFAULT_TOTAL_QUOTA_MICRO_CNY = 500_000     # 0.5 CNY
DEFAULT_DAILY_QUOTA_MICRO_CNY = 0           # 0 means no daily cap


def provider_base_url() -> str:
    return os.getenv("TRIAL_LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")


def provider_api_key() -> str:
    return os.getenv("TRIAL_LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")).strip()


def provider_model() -> str:
    return os.getenv("TRIAL_LLM_MODEL", "deepseek-v4-flash").strip()


def max_output_tokens() -> int:
    return _int_env("TRIAL_MAX_OUTPUT_TOKENS", 700)


def token_ttl_days() -> int:
    return _int_env("TRIAL_TOKEN_TTL_DAYS", 30)


def prompt_price_micro_cny_per_million() -> int:
    return _int_env("TRIAL_PROMPT_PRICE_MICRO_CNY_PER_MILLION", 2_000_000)


def completion_price_micro_cny_per_million() -> int:
    return _int_env("TRIAL_COMPLETION_PRICE_MICRO_CNY_PER_MILLION", 8_000_000)


def min_charge_micro_cny() -> int:
    return _int_env("TRIAL_MIN_CHARGE_MICRO_CNY", 100)


def estimated_request_safety_factor() -> int:
    return max(1, _int_env("TRIAL_ESTIMATE_SAFETY_FACTOR", 2))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def normalize_code(code: str) -> str:
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum() or ch == "-").strip("-")


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def today_key() -> str:
    return datetime.utcnow().date().isoformat()


def yuan(micro_cny: int) -> float:
    return round(max(0, int(micro_cny)) / 1_000_000, 4)


def reset_daily_if_needed(row: db.TrialCode) -> None:
    today = today_key()
    if row.used_today_date != today:
        row.used_today_date = today
        row.used_today_micro_cny = 0


def quota_status(row: db.TrialCode) -> dict[str, Any]:
    reset_daily_if_needed(row)
    total_remaining = max(0, (row.total_quota_micro_cny or 0) - (row.used_total_micro_cny or 0))
    daily_limit_enabled = bool((row.daily_quota_micro_cny or 0) > 0)
    daily_remaining = (
        max(0, (row.daily_quota_micro_cny or 0) - (row.used_today_micro_cny or 0))
        if daily_limit_enabled
        else total_remaining
    )
    remaining = min(daily_remaining, total_remaining)
    return {
        "code": row.code,
        "device_bound": bool(row.device_id),
        "active": bool(row.active),
        "model": provider_model(),
        "daily_limit_enabled": daily_limit_enabled,
        "daily_remaining_micro_cny": daily_remaining,
        "total_remaining_micro_cny": total_remaining,
        "remaining_micro_cny": remaining,
        "daily_remaining_yuan": yuan(daily_remaining),
        "total_remaining_yuan": yuan(total_remaining),
        "remaining_yuan": yuan(remaining),
        "request_count": row.request_count or 0,
        "token_expires_at": row.token_expires_at.isoformat() + "Z" if row.token_expires_at else "",
    }


def redeem_code(d: DbSession, code: str, device_id: str) -> dict[str, Any]:
    normalized = normalize_code(code)
    clean_device = str(device_id or "").strip()
    if len(normalized) < 4:
        raise TrialError("兑换码格式不正确", status_code=400)
    if len(clean_device) < 8:
        raise TrialError("设备标识无效", status_code=400)

    row = d.get(db.TrialCode, normalized)
    if row is None or not row.active:
        raise TrialError("兑换码不存在或已停用", status_code=404)
    reset_daily_if_needed(row)
    if row.device_id and row.device_id != clean_device:
        raise TrialError("该兑换码已绑定其他设备", status_code=403)
    if not row.device_id:
        row.device_id = clean_device

    token = secrets.token_urlsafe(32)
    row.token_hash = token_hash(token)
    row.token_expires_at = datetime.utcnow() + timedelta(days=token_ttl_days())
    d.commit()
    d.refresh(row)
    return {"trial_token": token, **quota_status(row)}


def get_code_by_token(d: DbSession, token: str) -> db.TrialCode:
    digest = token_hash(token)
    row = d.scalar(select(db.TrialCode).where(db.TrialCode.token_hash == digest))
    if row is None or not row.active:
        raise TrialError("体验 token 无效", status_code=401)
    if row.token_expires_at and row.token_expires_at < datetime.utcnow():
        raise TrialError("体验 token 已过期，请重新兑换", status_code=401)
    reset_daily_if_needed(row)
    if row.used_total_micro_cny >= row.total_quota_micro_cny:
        raise TrialError("该兑换码总额度已用完", status_code=402)
    if (row.daily_quota_micro_cny or 0) > 0 and row.used_today_micro_cny >= row.daily_quota_micro_cny:
        raise TrialError("今日体验额度已用完", status_code=402)
    return row


def ensure_quota_available(row: db.TrialCode, payload: dict[str, Any]) -> None:
    status = quota_status(row)
    estimate = estimate_request_cost_micro_cny(payload)
    if status["remaining_micro_cny"] < estimate:
        raise TrialError(
            f"体验额度不足，本次请求预计至少需要约 {yuan(estimate)} 元，当前剩余约 {status['remaining_yuan']} 元",
            status_code=402,
        )


def charge_usage(d: DbSession, row: db.TrialCode, payload: dict[str, Any], response: dict[str, Any]) -> int:
    usage = response.get("usage") if isinstance(response, dict) else {}
    prompt_tokens = int((usage or {}).get("prompt_tokens") or 0)
    completion_tokens = int((usage or {}).get("completion_tokens") or 0)
    total_tokens = int((usage or {}).get("total_tokens") or (prompt_tokens + completion_tokens))
    if total_tokens <= 0:
        prompt_tokens, completion_tokens, total_tokens = estimate_tokens(payload, response)

    cost = cost_micro_cny(prompt_tokens, completion_tokens)

    row.used_total_micro_cny = (row.used_total_micro_cny or 0) + cost
    row.used_today_micro_cny = (row.used_today_micro_cny or 0) + cost
    row.request_count = (row.request_count or 0) + 1
    d.add(db.TrialUsage(
        code=row.code,
        device_id=row.device_id or "",
        model=provider_model(),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_micro_cny=cost,
    ))
    d.commit()
    return cost


def cost_micro_cny(prompt_tokens: int, completion_tokens: int) -> int:
    cost = (
        max(0, int(prompt_tokens)) * prompt_price_micro_cny_per_million()
        + max(0, int(completion_tokens)) * completion_price_micro_cny_per_million()
    ) // 1_000_000
    return max(min_charge_micro_cny(), int(cost))


def estimate_request_cost_micro_cny(payload: dict[str, Any]) -> int:
    prompt_text = ""
    for msg in payload.get("messages") or []:
        content = msg.get("content") if isinstance(msg, dict) else msg
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    prompt_text += str(part.get("text") or part.get("content") or "") + "\n"
                else:
                    prompt_text += str(part) + "\n"
        else:
            prompt_text += str(content or "") + "\n"
    prompt_tokens = max(1, len(prompt_text) // 4)
    completion_tokens = max(1, int(payload.get("max_tokens") or max_output_tokens()))
    return cost_micro_cny(prompt_tokens, completion_tokens) * estimated_request_safety_factor()


def estimate_tokens(payload: dict[str, Any], response: dict[str, Any]) -> tuple[int, int, int]:
    prompt_text = ""
    for msg in payload.get("messages") or []:
        prompt_text += str(msg.get("content") or "") + "\n"
    reply_text = ""
    try:
        reply_text = str(response["choices"][0]["message"].get("content") or "")
    except Exception:
        reply_text = str(response)[:1000]
    prompt = max(1, len(prompt_text) // 4)
    completion = max(1, len(reply_text) // 4)
    return prompt, completion, prompt + completion


def build_provider_payload(body: dict[str, Any]) -> dict[str, Any]:
    mt = int(body.get("max_tokens") or body.get("max_completion_tokens") or max_output_tokens())
    mt = max(32, min(max_output_tokens(), mt))
    temperature = body.get("temperature", 0.7)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0, min(2, temperature))
    payload = {
        "model": provider_model(),
        "messages": body.get("messages") or [],
        "temperature": temperature,
        "max_tokens": mt,
    }
    if body.get("response_format"):
        payload["response_format"] = body["response_format"]
    return payload


async def call_provider(payload: dict[str, Any]) -> dict[str, Any]:
    key = provider_api_key()
    if not key:
        raise TrialError("服务器未配置体验 API Key", status_code=503)
    url = provider_base_url() + "/chat/completions"
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=80.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code in (400, 422) and "response_format" in payload:
            retry_payload = dict(payload)
            retry_payload.pop("response_format", None)
            r = await client.post(url, headers=headers, json=retry_payload)
    if r.status_code < 200 or r.status_code >= 300:
        raise TrialError(f"体验模型请求失败：HTTP {r.status_code} {r.text[:300]}", status_code=502)
    try:
        data = r.json()
    except Exception as exc:
        raise TrialError("体验模型返回了非 JSON 响应", status_code=502) from exc
    if not isinstance(data, dict):
        raise TrialError("体验模型响应格式异常", status_code=502)
    return data


class TrialError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
