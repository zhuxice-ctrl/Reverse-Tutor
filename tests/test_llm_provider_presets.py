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


def test_mobile_llm_accepts_plain_text_when_json_parse_fails():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "fallback_json" in html
    assert "plain_text_after_json_retry" in html
    assert "native_plain_text_fallback" in html
    assert "downloadApkInApp(info.apkUrls || info.apkUrl" in html


def test_mobile_llm_ping_uses_plain_text_connectivity_probe():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "连通性检测。请简短回复 ok。" in html
    assert "const raw = await chat_text" in html
    assert "btn.disabled = true" in html


def test_mobile_chat_turns_are_bound_and_rendered_safely():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function shapeReplyBubbles" in html
    assert "function normalizeAction" in html
    assert "function safeChatHtml" in html
    assert "turn_id" in html
    assert "client_msg_id" in html
    assert "reply_to_message_id" in html
    assert "message_index" in html
    assert "message_total" in html
    assert "source:'foreground_llm'" in html
    assert "source:'native_background'" in html
    assert "native_background_job_id: jobId" in html
    assert "pending.turn_id" in html
    assert "safeChatHtml(m.content)" in html
    assert "md(m.content)" not in html


def test_mobile_prompt_adapts_when_goal_is_not_learning():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function inferConversationMode" in html
    assert "goal_support" in html
    assert "如果当前目标不是学习" in html
    assert "不要强行要求用户讲知识点" in html
    assert "本回合相关主题" in html
