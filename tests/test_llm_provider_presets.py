from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_llm_settings_include_provider_api_type_and_capability_presets():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LLM_PROVIDERS" in html
    assert "cfg-provider" in html
    assert "cfg-api-type" in html
    assert "cfg-capability" in html
    assert "applyLlmProviderPreset" in html
    assert "https://api.openai.com/v1" in html
    assert "https://api.deepseek.com/v1" in html
    assert "https://dashscope.aliyuncs.com/compatible-mode/v1" in html
    assert "https://api.moonshot.ai/v1" in html
    assert "https://api.groq.com/openai/v1" in html
    assert "https://openrouter.ai/api/v1" in html
    assert "http://localhost:11434/v1" in html


def test_mobile_llm_payload_sanitizes_multimodal_messages_by_capability():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "sanitizeMessagesForCapability" in html
    assert "normalizeContentParts" in html
    assert "当前模型不支持识别图片" in html
    assert "image_url" in html
    assert "openai_responses" in html
    assert "responses_chat" in html


def test_android_background_job_carries_api_type_and_capability():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "api_type: cfg.api_type" in html
    assert "capability: cfg.capability" in html
    assert "supportsBackgroundChat" in html
