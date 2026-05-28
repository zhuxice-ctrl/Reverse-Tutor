"""LLM 适配层 —— OpenAI 兼容协议，离线时使用 mock。

任何 OpenAI 兼容端点都能直接接入（DeepSeek/Qwen/Moonshot/Hermes proxy 等）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_TYPE = os.getenv("LLM_API_TYPE", "").strip().lower()

FREE_LLM_BASE_URL = os.getenv("FREE_LLM_BASE_URL", "https://open.bigmodel.cn/api/anthropic").rstrip("/")
FREE_LLM_API_KEY = os.getenv(
    "FREE_LLM_API_KEY",
    "f16f94275d5842d0a63d5713f679c9d2.RdFfzGeayrffjyoL",
).strip()
FREE_LLM_MODEL = os.getenv("FREE_LLM_MODEL", "GLM-4.7-Flash").strip()
FREE_LLM_API_TYPE = os.getenv("FREE_LLM_API_TYPE", "anthropic").strip().lower()

_HAS_REAL = bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)


class LLMError(RuntimeError):
    pass


# --- 运行时热切换配置 ---------------------------------------------------------

def apply_config(base_url: str, api_key, model: str) -> bool:
    """运行时设置 LLM 凭据，返回是否进入 live 模式。

    api_key 语义：
        - None      → 保留原 key 不变（前端"留空 = 不变"）
        - 空字符串  → 清空 key（用于切回 mock）
        - 非空字符串 → 覆盖为新 key
    """
    global LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, _HAS_REAL
    LLM_BASE_URL = (base_url or "").rstrip("/")
    if api_key is not None:
        LLM_API_KEY = (api_key or "").strip()
    LLM_MODEL = (model or "").strip()
    _HAS_REAL = bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)
    return _HAS_REAL


def _detect_api_type(base_url: str, explicit: str = "") -> str:
    explicit = (explicit or "").strip().lower()
    if explicit in {"openai", "anthropic"}:
        return explicit
    url = (base_url or "").lower()
    if "/anthropic" in url or url.endswith("/v1/messages"):
        return "anthropic"
    return "openai"


def _has_free_llm() -> bool:
    return bool(FREE_LLM_BASE_URL and FREE_LLM_API_KEY and FREE_LLM_MODEL)


def _active_config() -> dict[str, str] | None:
    if _HAS_REAL:
        return {
            "source": "user",
            "mode": "live",
            "base_url": LLM_BASE_URL,
            "api_key": LLM_API_KEY,
            "model": LLM_MODEL,
            "api_type": _detect_api_type(LLM_BASE_URL, LLM_API_TYPE),
        }
    if _has_free_llm():
        return {
            "source": "free",
            "mode": "free",
            "base_url": FREE_LLM_BASE_URL,
            "api_key": FREE_LLM_API_KEY,
            "model": FREE_LLM_MODEL,
            "api_type": _detect_api_type(FREE_LLM_BASE_URL, FREE_LLM_API_TYPE),
        }
    return None


def get_config() -> dict[str, Any]:
    """返回当前 LLM 配置状态（不返回明文 api_key）。"""
    active = _active_config()
    if active:
        return {
            "base_url": active["base_url"],
            "model": active["model"],
            "has_api_key": bool(active["api_key"]),
            "mode": active["mode"],
            "api_type": active["api_type"],
            "source": active["source"],
        }
    return {
        "base_url": "",
        "model": "",
        "has_api_key": False,
        "mode": "mock",
        "api_type": "mock",
        "source": "mock",
    }


def _is_minimax_config(config: dict[str, str] | None = None) -> bool:
    config = config or _active_config() or {}
    base_url = config.get("base_url", "")
    model = config.get("model", "")
    return "api.minimax.io" in base_url.lower() or model.lower().startswith("minimax-")


def _provider_temperature(temperature: float) -> float:
    if not _is_minimax_config():
        return temperature
    return min(1.0, max(0.01, float(temperature)))


async def ping() -> dict[str, Any]:
    """发送一个最小请求验证 LLM 联通性。"""
    active = _active_config()
    if not active:
        return {"ok": False, "mode": "mock", "reason": "no credentials"}
    try:
        raw = await _provider_chat(
            "You are a connectivity check. Respond with JSON {\"ok\":true}.",
            [{"role": "user", "content": "ping"}],
            temperature=0.0, max_tokens=20,
        )
        parsed = _extract_json(raw)
        return {"ok": True, "mode": active["mode"], "model": active["model"], "sample": parsed}
    except Exception as e:
        return {"ok": False, "mode": active["mode"], "error": str(e)}


# --- 公共接口 -----------------------------------------------------------------

async def chat_json(
    system: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """要求 LLM 输出 JSON。若未配置 LLM 凭据则走 mock。"""
    active = _active_config()
    if not active:
        return _mock_response(system, messages)
    try:
        raw = await _provider_chat(system, messages, temperature, max_tokens)
    except Exception:
        if active["source"] == "free":
            return _mock_response(system, messages)
        raise
    try:
        return _extract_json(raw)
    except LLMError as first_error:
        retry_system = (
            system
            + "\n\nIMPORTANT: Return only one valid JSON object. Do not use markdown, "
            + "comments, <think> tags, or explanations before/after the JSON. "
            + "Start with { and end with }."
        )
        try:
            retry_raw = await _provider_chat(
                retry_system,
                messages,
                min(temperature, 0.3),
                max_tokens,
            )
        except Exception:
            if active["source"] == "free":
                return _mock_response(system, messages)
            raise
        try:
            return _extract_json(retry_raw)
        except LLMError as retry_error:
            if active["source"] == "free":
                return _mock_response(system, messages)
            raise LLMError(
                f"{retry_error}; first invalid response preview={raw[:200]!r}"
            ) from first_error


def has_real_llm() -> bool:
    return _active_config() is not None


async def _provider_chat(
    system: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    active = _active_config()
    if not active:
        raise LLMError("no LLM credentials configured")
    if active["api_type"] == "anthropic":
        return await _anthropic_chat(system, messages, temperature, max_tokens)
    return await _openai_chat(system, messages, temperature, max_tokens)


# --- OpenAI 兼容调用 ----------------------------------------------------------

async def _openai_chat(
    system: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    config: dict[str, str] | None = None,
) -> str:
    config = config or _active_config()
    if not config:
        raise LLMError("no OpenAI-compatible credentials configured")
    base_url = config["base_url"].rstrip("/")
    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = _build_openai_payload(system, messages, temperature, max_tokens, json_mode=True, config=config)
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # 某些 provider 不支持 response_format，去掉重试一次
            status = e.response.status_code
            body_preview = (e.response.text or "")[:300]
            if "response_format" in str(e) or "response_format" in body_preview or status in (400, 422):
                payload.pop("response_format", None)
                try:
                    r = await client.post(url, json=payload, headers=headers)
                    r.raise_for_status()
                except httpx.HTTPError as retry_e:
                    raise LLMError(
                        f"LLM retry without response_format failed: {retry_e}"
                    ) from retry_e
            else:
                raise LLMError(f"LLM request failed: {e}; body={body_preview}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"LLM request failed: {e}") from e
    data = _response_json(r, "LLM")
    content = _content_from_openai_data(data)
    if content.strip():
        return content

    retry_system = (
        system
        + "\n\nIMPORTANT: Return only one valid JSON object. Do not use markdown. "
        + "Do not output explanations before or after the JSON."
    )
    retry_payload = _build_openai_payload(retry_system, messages, temperature, max_tokens, json_mode=False, config=config)
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(url, json=retry_payload, headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"LLM request failed after empty-content retry: {e}") from e
    retry_data = _response_json(r, "LLM retry")
    retry_content = _content_from_openai_data(retry_data)
    if retry_content.strip():
        return retry_content

    return _raise_empty_content(retry_data)


def _build_openai_payload(
    system: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    json_mode: bool,
    config: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = config or _active_config() or {"model": LLM_MODEL}
    payload = {
        "model": config.get("model", LLM_MODEL),
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": _provider_temperature(temperature),
    }
    if _is_minimax_config(config):
        payload["max_completion_tokens"] = max_tokens
    else:
        payload["max_tokens"] = max_tokens
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


async def _anthropic_chat(
    system: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    config: dict[str, str] | None = None,
) -> str:
    config = config or _active_config()
    if not config:
        raise LLMError("no Anthropic-compatible credentials configured")
    base_url = config["base_url"].rstrip("/")
    url = base_url if base_url.endswith("/v1/messages") else f"{base_url}/v1/messages"
    payload = _build_anthropic_payload(system, messages, temperature, max_tokens, config)
    headers = {
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"LLM request failed: {e}") from e
    data = _response_json(r, "LLM")
    content = _content_from_anthropic_data(data)
    if content.strip():
        return content
    raise LLMError(f"LLM returned empty anthropic content: {str(data)[:300]}")


def _build_anthropic_payload(
    system: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    config: dict[str, str] | None = None,
) -> dict[str, Any]:
    config = config or _active_config() or {"model": LLM_MODEL}
    system_parts = [str(system or "").strip()]
    out = []
    for msg in messages or []:
        role = msg.get("role", "user")
        content = _message_text(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            out.append({"role": "assistant", "content": content})
        elif role == "system":
            system_parts.append(content)
        else:
            out.append({"role": "user", "content": content})
    if not out:
        out.append({"role": "user", "content": "ping"})
    return {
        "model": config.get("model", LLM_MODEL),
        "system": "\n\n".join(part for part in system_parts if part),
        "messages": out,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _content_from_openai_data(data: dict[str, Any]) -> str:
    try:
        choice = data["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"LLM response shape unexpected: {str(data)[:300]}") from e
    content = msg.get("content") or ""
    # DeepSeek-R1 / Reasoner 把答案放在 reasoning_content；fallback 取它
    if not content.strip():
        content = msg.get("reasoning_content") or ""
    if not content.strip():
        return ""
    return content


def _content_from_anthropic_data(data: dict[str, Any]) -> str:
    if isinstance(data.get("completion"), str):
        return data["completion"]
    if isinstance(data.get("content"), str):
        return data["content"]
    chunks = []
    for item in data.get("content") or []:
        if isinstance(item, dict):
            if isinstance(item.get("text"), str):
                chunks.append(item["text"])
            elif isinstance(item.get("content"), str):
                chunks.append(item["content"])
    return "\n".join(chunks)


def _response_json(response: httpx.Response, label: str) -> dict[str, Any]:
    try:
        data = response.json()
    except Exception as e:
        text = getattr(response, "text", "") or ""
        raise LLMError(f"{label} returned non-JSON API response: {text[:300]}") from e
    if not isinstance(data, dict):
        raise LLMError(f"{label} response shape unexpected: {str(data)[:300]}")
    return data


def _raise_empty_content(data: dict[str, Any]) -> str:
    choice = (data.get("choices") or [{}])[0]
    finish = choice.get("finish_reason")
    usage = data.get("usage", {})
    hint = ""
    if finish == "length":
        hint = "（被 max_tokens 截断，增大 max_tokens 重试）"
    elif "reasoner" in (LLM_MODEL or "").lower() or "r1" in (LLM_MODEL or "").lower():
        hint = "（reasoner 模型建议改用 deepseek-chat；reasoner 不适合强 JSON 输出）"
    else:
        hint = "（provider 在 JSON mode/当前 prompt 下返回空白，已无 JSON mode 重试仍为空）"
    raise LLMError(
        f"LLM returned empty content. finish_reason={finish} usage={usage} {hint}"
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def _extract_json(raw: str) -> dict[str, Any]:
    original = raw or ""
    s = _normalize_json_text(original)

    for candidate in _json_candidates(s):
        parsed = _loads_json_lenient(candidate)
        if parsed is not None:
            return parsed

    raise LLMError(f"LLM did not return valid JSON: {original.strip()[:300]}")


def _normalize_json_text(raw: str) -> str:
    s = (raw or "").strip()
    s = _THINK_RE.sub("", s).strip()
    fence = _FENCE_RE.search(s)
    if fence:
        s = fence.group(1).strip()
    return s


def _json_candidates(s: str) -> list[str]:
    candidates = [s]
    first = s.find("{")
    last = s.rfind("}")
    if first >= 0 and last > first:
        candidates.append(s[first:last + 1])

    balanced = _first_balanced_json_object(s, first)
    if balanced:
        candidates.append(balanced)

    deduped = []
    seen = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _first_balanced_json_object(s: str, first: int) -> str | None:
    if first < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(first, len(s)):
        ch = s[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[first:i + 1]
    return None


def _loads_json_lenient(s: str) -> dict[str, Any] | None:
    for candidate in (s, _TRAILING_COMMA_RE.sub(r"\1", s)):
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# --- Mock：离线 demo 模式 -----------------------------------------------------
#
# 设计目标：无 LLM 凭据时也能展示完整的"评估-决策-行动"循环。
# 策略：
#   1. 关键词意图识别 → 选 action 类型
#   2. 维护一个 KP 进度池，每个 next 推到下一个 kp
#   3. 句池按 (action, kp_index) 选回话
#   4. anchor_updates 自动从用户输入抽取
#
_MOCK_KP_SEQUENCE = [
    "二次函数对称轴",
    "二次函数顶点",
    "判别式",
    "韦达定理",
    "复合函数",
    "导数定义",
]

# (action, idx_in_kp_seq) -> 回话模板（{kp} 占位）
_MOCK_LINES = {
    "ask": [
        "（挠头）老师我想先问：**{kp}** 怎么搞？我连定义都有点蒙……",
        "好嘛！那 **{kp}** 这个东西到底咋用啊？给我讲讲呗？",
        "诶老师我突然想到——**{kp}** 是不是上节课说过的那个？我又忘了 QAQ",
    ],
    "probe": [
        "你说的我大概懂，但是**为什么**是这样？能再深一点不？关于 **{kp}**？",
        "嗯……可如果题目里改一个条件，**{kp}** 这个结论还成立吗？",
        "我有点疑惑：**{kp}** 在什么情况下会失效？老师能举个反例吗？",
    ],
    "clue": [
        "老师，据说这种题有一种方法叫 **{kp}**。好像第一步要先找它解决不了的旧方法，你能不能给我讲讲为什么？",
        "老师我好像没入口……我只听说 **{kp}** 是先看一个具体例子。我们能不能从例子里第一步开始？",
    ],
    "scaffold_example": [
        "老师，我先拿一个 **{kp}** 的小例子看：它好像不是先背定义，而是先观察哪里卡住。你能顺着这个例子讲第一步吗？",
    ],
    "examiner_verify": [
        "老师你说懂了，那我想考考自己：如果题目换个条件，**{kp}** 第一步还一样吗？你能验证我这个想法吗？",
        "那我先不算自己真会了。老师你能不用资料，把 **{kp}** 的第一步和适用条件再问我一遍吗？",
    ],
    "persuade": [
        "诶老师别走啊……我就剩 **{kp}** 这一节没搞懂了，你陪我弄完好不好，我请你喝奶茶 QAQ",
        "（小声）我知道我笨……但你刚才那个思路对我帮助超大，能再讲下 **{kp}** 不？",
        "哎呀别嫌我烦嘛！再坚持五分钟就把 **{kp}** 搞定！(￣y▽,￣)╭ ",
    ],
    "encourage": [
        "（眼睛一亮）真的吗？我有进步？那 **{kp}** 我应该没问题了对吧！",
        "诶嘿其实我自己都没意识到。那下一题——咱继续？",
        "（窃喜）那我把这个总结写到本子上，以后看到 **{kp}** 就不慌啦。",
    ],
    "next": [
        "好的好的我懂了！那我们继续——**{kp}** 是啥？我猜跟前面那个有关系？",
        "OK 这个 kp 我打卡了。接下来想了解 **{kp}**，老师从哪入手好？",
        "（合上书）好了，我准备好挑战 **{kp}** 了！来题吧！",
    ],
    "wrap": [
        "今天就到这吧老师，我先把 **{kp}** 复盘一下，明天接着来！",
        "差不多了！我感觉脑子充电了，今天的 **{kp}** 我会再做两题巩固。",
    ],
}


def _detect_intent(user_text: str) -> str:
    """根据用户输入选择最合适的 mock action 类型。"""
    t = (user_text or "").strip()
    if not t:
        return "ask"

    # 没有方法入口 → clue
    if any(k in t for k in ("不知道", "没听过", "没学过", "不会", "这是什么", "完全没")):
        return "clue"
    # 拒绝 / 撤退 / 烦躁 → persuade
    if any(k in t for k in ("不想", "算了", "放弃", "没意思", "烦", "够了", "退出", "拜拜", "再见", "晚安")):
        return "persuade"
    # 答案/解释优先（"因为...""所以..."）→ probe（追问深度）
    if len(t) > 25 and any(k in t for k in ("因为", "所以", "由于", "推出", "证明", "推导", "推论", "证")):
        return "probe"
    # 包含数学/代码符号或公式 → probe
    if any(c in t for c in ("=", "→", "²", "^", "∫", "代码", "函数")):
        return "probe"
    # 鼓励反馈 → encourage（用更明确的指向"你"的称赞）
    if any(k in t for k in ("你真棒", "你不错", "你厉害", "你掌握", "你学得快", "你懂了", "你做得", "做得好", "学得不错")):
        return "encourage"
    # 收尾意图 → wrap（在 next 之前，因为"明天继续"会同时含"继续"）
    if any(k in t for k in ("今天就这样", "今天就到", "明天", "下次再", "下次见", "结束", "总结一下", "总结今天")):
        return "wrap"
    # 明确推进 → next
    if any(k in t for k in ("懂了", "明白了", "会了", "理解了")):
        return "examiner_verify"
    if any(k in t for k in ("继续", "下一", "next", "再来")):
        return "next"
    # 默认 ask（继续提问）
    return "ask"


def _detect_emotion(user_text: str) -> str:
    t = (user_text or "")
    if any(k in t for k in ("不想", "烦", "放弃", "没意思", "够了", "晕")):
        return "frustrated"
    if any(k in t for k in ("好的", "明白", "懂", "可以")):
        return "engaged"
    if any(k in t for k in ("？", "?", "为什么", "怎么")):
        return "curious"
    return "neutral" if t else "fresh"


def _extract_requirements(user_text: str) -> list[str]:
    """从用户输入抽取潜在的诉求（→ anchor_updates）。"""
    t = (user_text or "").strip()
    triggers = ("重点", "想搞", "想学", "想多练", "尤其", "目标", "要考", "希望多", "希望少", "不要", "别给")
    if any(k in t for k in triggers):
        return [t[:80]]
    return []


def _mock_response(system: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """无 LLM 凭据时的可玩 fallback。

    - 基于用户输入做意图识别（关键词），选择最贴近的 action 类型
    - 维护一个 KP 进度池，next 时推进
    - 仍输出完整的 evaluation / action / reply / anchor_updates 结构
    """
    n_user = sum(1 for m in messages if m.get("role") == "user")
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )

    # 开场（无 user 输入）→ ask 第一个 kp
    if not last_user:
        kp = _MOCK_KP_SEQUENCE[0]
        return _pack("ask", kp, "fresh", correctness=0.0, depth=0.0,
                     reqs=[], extra_note="mock-opening")

    intent = _detect_intent(last_user)
    emotion = _detect_emotion(last_user)
    new_reqs = _extract_requirements(last_user)

    # KP 进度：每次 next 推进，否则停在当前 kp（用历史中已发生的 next 数推算）
    n_next = 0
    for m in messages:
        if m.get("role") == "assistant":
            c = m.get("content", "")
            # 粗略：mock 回话 next 模板里有 "继续" 或 "下一个"
            if "（合上书）" in c or "我准备好挑战" in c or "下一题" in c:
                n_next += 1
    kp_idx = min(n_next + (1 if intent == "next" else 0), len(_MOCK_KP_SEQUENCE) - 1)
    kp = _MOCK_KP_SEQUENCE[kp_idx]

    # 估算 correctness/depth：probe 类输入认为答得不错；persuade 类是负反馈
    if intent in ("probe", "next", "encourage"):
        correctness = min(0.85, 0.35 + 0.1 * n_user)
        depth = 0.6
    elif intent == "persuade":
        correctness = 0.1
        depth = 0.1
    elif intent in ("clue", "scaffold_example", "examiner_verify"):
        correctness = 0.0
        depth = 0.0
    else:
        correctness = 0.4
        depth = 0.3

    return _pack(intent, kp, emotion,
                 correctness=correctness, depth=depth,
                 reqs=new_reqs)


def _pack(
    action_type: str, kp: str, emotion: str,
    *, correctness: float, depth: float,
    reqs: list[str], extra_note: str = "mock",
) -> dict[str, Any]:
    import random
    pool = _MOCK_LINES.get(action_type, _MOCK_LINES["ask"])
    reply = random.choice(pool).format(kp=kp)
    entry_status = "no_entry" if action_type in ("clue", "scaffold_example") else "has_entry"
    student_role = {
        "clue": "clue_student",
        "scaffold_example": "scaffold_student",
        "examiner_verify": "examiner",
        "recap": "review_student",
        "next": "review_student",
        "wrap": "review_student",
    }.get(action_type, "probing_student")
    if action_type == "probe":
        evidence = {
            "type": "explanation",
            "status": "passed",
            "error_type": "",
            "reason": "用户给出了可追问的解释",
        }
    else:
        evidence = {
            "type": "none",
            "status": "none",
            "error_type": "",
            "reason": "mock 本轮不提供掌握度进位证据",
        }
    return {
        "evaluation": {
            "correctness": round(correctness, 2),
            "depth": round(depth, 2),
            "entry_status": entry_status,
            "evidence_for_mastery": evidence,
            "user_emotion": emotion,
            "new_requirements": reqs,
        },
        "action": {
            "type": action_type,
            "student_role": student_role,
            "knowledge_point": kp,
            "difficulty": 0.4 if action_type == "ask" else 0.6,
            "note": extra_note,
        },
        "reply": reply,
        "anchor_updates": [
            {"kind": "requirement", "content": r, "weight": 1.2} for r in reqs
        ],
    }
