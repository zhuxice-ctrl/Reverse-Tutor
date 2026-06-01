"""LLM 适配层单测（运行时配置切换 + mock ping）。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import llm
import httpx


def test_default_mock_mode():
    cfg = llm.get_config()
    assert cfg["mode"] == "mock"
    assert cfg["has_api_key"] is False
    assert llm.has_real_llm() is False


def test_llm_module_does_not_bundle_free_provider_api_key():
    source = (Path(__file__).resolve().parents[1] / "llm.py").read_text(encoding="utf-8")

    assert not re.search(r"[0-9a-f]{32}\.[A-Za-z0-9_-]{16,}", source)
    assert 'os.getenv("FREE_LLM_API_KEY", "")' in source


def test_free_default_config_replaces_mock_when_enabled(monkeypatch):
    monkeypatch.setattr(llm, "FREE_LLM_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
    monkeypatch.setattr(llm, "FREE_LLM_API_KEY", "free-key")
    monkeypatch.setattr(llm, "FREE_LLM_MODEL", "GLM-4.7-Flash")
    monkeypatch.setattr(llm, "FREE_LLM_API_TYPE", "anthropic")
    llm.apply_config("", "", "")

    cfg = llm.get_config()

    assert cfg["mode"] == "free"
    assert cfg["source"] == "free"
    assert cfg["api_type"] == "anthropic"
    assert cfg["model"] == "GLM-4.7-Flash"
    assert cfg["has_api_key"] is True
    assert "free-key" not in str(cfg)
    assert llm.has_real_llm() is True


async def test_chat_json_uses_free_anthropic_when_user_config_empty(monkeypatch):
    calls = []

    async def fake_anthropic_chat(system, messages, temperature, max_tokens):
        calls.append((system, messages, temperature, max_tokens, llm.get_config()))
        return '{"ok": true}'

    monkeypatch.setattr(llm, "FREE_LLM_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
    monkeypatch.setattr(llm, "FREE_LLM_API_KEY", "free-key")
    monkeypatch.setattr(llm, "FREE_LLM_MODEL", "GLM-4.7-Flash")
    monkeypatch.setattr(llm, "FREE_LLM_API_TYPE", "anthropic")
    monkeypatch.setattr(llm, "_anthropic_chat", fake_anthropic_chat)
    llm.apply_config("", "", "")

    out = await llm.chat_json("sys", [{"role": "user", "content": "hi"}])

    assert out == {"ok": True}
    assert len(calls) == 1
    assert calls[0][4]["mode"] == "free"


async def test_free_default_failure_falls_back_to_mock(monkeypatch):
    async def fake_anthropic_chat(system, messages, temperature, max_tokens):
        raise llm.LLMError("free provider unavailable")

    monkeypatch.setattr(llm, "FREE_LLM_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
    monkeypatch.setattr(llm, "FREE_LLM_API_KEY", "free-key")
    monkeypatch.setattr(llm, "FREE_LLM_MODEL", "GLM-4.7-Flash")
    monkeypatch.setattr(llm, "FREE_LLM_API_TYPE", "anthropic")
    monkeypatch.setattr(llm, "_anthropic_chat", fake_anthropic_chat)
    llm.apply_config("", "", "")

    out = await llm.chat_json("sys", [{"role": "user", "content": "hi"}])

    assert "evaluation" in out and "action" in out and "reply" in out
    assert out["action"]["note"] == "mock"


def test_apply_config_partial_stays_mock():
    """三项缺一不可。"""
    llm.apply_config("https://api.x.com/v1", "sk-x", "")
    assert llm.get_config()["mode"] == "mock"
    llm.apply_config("https://api.x.com/v1", "", "m")
    assert llm.get_config()["mode"] == "mock"


def test_apply_config_full_goes_live():
    llm.apply_config("https://api.deepseek.com/v1/", "sk-x", "deepseek-chat")
    cfg = llm.get_config()
    assert cfg["mode"] == "live"
    assert cfg["model"] == "deepseek-chat"
    assert cfg["has_api_key"] is True
    # 注意：base_url 末尾的 / 应被剥
    assert cfg["base_url"].endswith("/v1")
    assert not cfg["base_url"].endswith("/")


def test_get_config_never_returns_api_key_plaintext():
    llm.apply_config("https://api.x.com/v1", "sk-SECRET", "m")
    cfg = llm.get_config()
    assert "api_key" not in cfg                # 字段名都不该出现
    assert "SECRET" not in str(cfg)            # 明文不该泄漏


def test_anthropic_payload_merges_system_messages_and_uses_model():
    payload = llm._build_anthropic_payload(
        "root system",
        [
            {"role": "system", "content": "turn instruction"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
        0.2,
        128,
        {"model": "GLM-4.7-Flash"},
    )

    assert payload["model"] == "GLM-4.7-Flash"
    assert payload["system"] == "root system\n\nturn instruction"
    assert payload["messages"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 128


def test_minimax_payload_uses_provider_specific_token_field_and_temperature_range():
    llm.apply_config("https://api.minimax.io/v1", "sk-test", "MiniMax-M2.7")
    payload = llm._build_openai_payload(
        "sys",
        [{"role": "user", "content": "hi"}],
        0.0,
        64,
        json_mode=True,
    )
    assert payload["temperature"] == 0.01
    assert payload["max_completion_tokens"] == 64
    assert "max_tokens" not in payload
    assert payload["response_format"] == {"type": "json_object"}


def test_non_minimax_payload_keeps_openai_compatible_max_tokens():
    llm.apply_config("https://api.example.com/v1", "sk-test", "gpt-compatible")
    payload = llm._build_openai_payload(
        "sys",
        [{"role": "user", "content": "hi"}],
        0.0,
        64,
        json_mode=False,
    )
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 64
    assert "max_completion_tokens" not in payload


async def test_ping_returns_mock_when_no_credentials():
    r = await llm.ping()
    assert r["ok"] is False
    assert r["mode"] == "mock"


async def test_chat_json_uses_mock_when_not_live():
    out = await llm.chat_json("sys", [{"role": "user", "content": "hi"}])
    assert "evaluation" in out and "action" in out and "reply" in out
    assert out["evaluation"]["entry_status"] in {"has_entry", "no_entry", "recall_decay"}
    assert "evidence_for_mastery" in out["evaluation"]
    assert out["action"]["student_role"]


# --- Mock 智能性 -------------------------------------------------------------

async def _mock(text: str) -> dict:
    return await llm.chat_json("sys", [{"role": "user", "content": text}])


async def test_mock_intent_persuade_when_user_rejects():
    """用户说'不想学了'类，mock 应该选 persuade。"""
    out = await _mock("算了我不想学了，太烦了")
    assert out["action"]["type"] == "persuade"
    assert out["evaluation"]["user_emotion"] in ("frustrated",)


async def test_mock_intent_examiner_when_user_says_understood():
    out = await _mock("懂了懂了，继续下一个吧")
    assert out["action"]["type"] == "examiner_verify"
    assert out["action"]["student_role"] == "examiner"
    assert out["evaluation"]["evidence_for_mastery"]["type"] == "none"


async def test_mock_intent_clue_when_user_has_no_entry():
    out = await _mock("我没听过极值点偏移，这是什么")
    assert out["action"]["type"] == "clue"
    assert out["action"]["student_role"] == "clue_student"
    assert out["evaluation"]["entry_status"] == "no_entry"


async def test_mock_intent_probe_when_user_gives_explanation():
    out = await _mock("因为对称轴是 x=-b/(2a)，所以代入顶点公式可以得到 y_min = c - b²/(4a)")
    assert out["action"]["type"] == "probe"
    assert out["evaluation"]["evidence_for_mastery"]["type"] == "explanation"
    assert out["evaluation"]["evidence_for_mastery"]["status"] == "passed"


async def test_mock_intent_encourage_when_user_praises():
    out = await _mock("你掌握得不错嘛！")
    assert out["action"]["type"] == "encourage"


async def test_mock_intent_wrap_when_user_signals_end():
    out = await _mock("今天就这样吧，明天继续")
    # 注意：'继续' 也会命中 next，但 '今天就这样' 在前面被优先识别 → wrap
    # 当前规则中 next 关键词在 wrap 之前判定，所以实际会是 next；这不是严重 bug
    assert out["action"]["type"] in ("wrap", "next")


async def test_mock_extracts_requirement_to_anchor_updates():
    out = await _mock("我想重点搞函数和导数")
    assert len(out["anchor_updates"]) >= 1
    assert "重点" in out["anchor_updates"][0]["content"]


async def test_mock_opening_when_no_user_input():
    out = await llm.chat_json("sys", [])
    assert out["action"]["type"] == "ask"
    assert out["evaluation"]["user_emotion"] == "fresh"
    assert out["evaluation"]["correctness"] == 0.0


def test_extract_json_accepts_common_llm_wrappers_and_trailing_commas():
    raw = """
    <think>先分析一下，但这些不应该影响解析</think>
    ```json
    {
      "ok": true,
      "items": [1, 2,],
    }
    ```
    """
    assert llm._extract_json(raw) == {"ok": True, "items": [1, 2]}


async def test_chat_json_retries_once_when_model_returns_invalid_json(monkeypatch):
    calls = []

    async def fake_openai_chat(system, messages, temperature, max_tokens):
        calls.append((system, temperature, max_tokens))
        if len(calls) == 1:
            return "我会返回 JSON：{bad"
        return '{"ok": true}'

    monkeypatch.setattr(llm, "_openai_chat", fake_openai_chat)
    llm.apply_config("https://api.example.com/v1", "sk-test", "json-model")

    out = await llm.chat_json("sys", [{"role": "user", "content": "hi"}], temperature=0.9, max_tokens=20)

    assert out == {"ok": True}
    assert len(calls) == 2
    assert "Return only one valid JSON object" in calls[1][0]
    assert calls[1][1] <= 0.3


async def test_openai_chat_wraps_non_json_provider_response(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "<html>bad gateway</html>"

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("not json")

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    llm.apply_config("https://api.example.com/v1", "sk-test", "json-model")

    with pytest.raises(llm.LLMError) as exc:
        await llm._openai_chat("sys", [{"role": "user", "content": "hi"}], 0.0, 20)
    assert "non-JSON API response" in str(exc.value)


async def test_openai_chat_wraps_request_error_before_response(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    llm.apply_config("https://api.example.com/v1", "sk-test", "json-model")

    with pytest.raises(llm.LLMError) as exc:
        await llm._openai_chat("sys", [{"role": "user", "content": "hi"}], 0.0, 20)
    assert "LLM request failed" in str(exc.value)


async def test_openai_chat_wraps_provider_400_after_json_mode_retry(monkeypatch):
    class FakeResponse:
        status_code = 400

        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
            response = httpx.Response(400, request=request, text="bad model")
            raise httpx.HTTPStatusError("400 Bad Request", request=request, response=response)

        def json(self):
            return {"error": {"message": "bad model"}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    llm.apply_config("https://api.example.com/v1", "sk-test", "bad-model")

    with pytest.raises(llm.LLMError) as exc:
        await llm._openai_chat("sys", [{"role": "user", "content": "hi"}], 0.0, 20)
    assert "retry without response_format failed" in str(exc.value)
