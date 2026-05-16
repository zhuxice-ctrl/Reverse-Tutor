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


def test_mobile_llm_settings_use_custom_picker_ui_instead_of_visible_native_selects():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "native-config-select" in html
    assert 'id="cfg-provider-trigger"' in html
    assert 'id="cfg-provider-summary"' in html
    assert 'id="cfg-api-type-segments"' in html
    assert 'id="cfg-capability-segments"' in html
    assert 'id="cfg-model-presets"' in html
    assert 'id="choice-sheet"' in html
    assert "function openChoiceSheet" in html
    assert "function renderConfigPickerUi" in html
    assert "function renderModelPresetChips" in html
    assert "models:[" in html


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


def test_mobile_proactive_conversation_has_three_modes_and_local_dispatch():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "PROACTIVE_CONFIG_KEY" in html
    assert "PROACTIVE_MODES" in html
    assert "online" in html
    assert "offline" in html
    assert "sleep" in html
    assert "minIntervalMs: 30 * 60 * 1000" in html
    assert "maxIntervalMs: 60 * 60 * 1000" in html
    assert "offline: { label: '离线', disabled: true }" in html
    assert "mode_disabled" in html
    assert "proactiveIntervalMs" in html
    assert "function proactiveConfig" in html
    assert "async function maybeRunProactiveTurn" in html
    assert "run_proactive_turn" in html
    assert "source:'proactive'" in html
    assert "is_system_trigger" in html
    assert "主动对话引导" in html


def test_mobile_message_popup_shows_actual_reply_content_without_covering_active_chat():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function messagePopupPreview" in html
    assert "function shouldShowMessagePopup" in html
    assert "slice(0, 360)" in html
    assert "messagePopupPreview(text)" in html
    assert "document.visibilityState === 'visible' && state.currentTab === 'chat'" in html
    assert "source === 'foreground_llm'" in html
    assert "showMessagePopup('学生 AI 回复'" not in html
    assert "showMessagePopup('后台 LLM 回复', r.lastReply, 4200, { source: 'native_background' })" in html
    assert "showMessagePopup('主动对话', result.reply, 4200, { source: 'proactive' })" in html
    assert 'id="message-popup-body" class="text-sm leading-snug max-h-28 overflow-y-auto whitespace-pre-wrap break-words"' in html


def test_mobile_prompt_uses_post_history_instruction_for_better_role_replies():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function finalReplyInstruction" in html
    assert "Post-History Instructions" in html
    assert "只写学生 AI 的下一次回复" in html
    assert "尊重用户自主权" in html
    assert "不要把非学习目标强行改成教学/知识点讲解" in html
    assert "messages.push({ role: 'system', content: finalReplyInstruction" in html
    assert "shapeReplyBubbles(reply, 1)" in html
