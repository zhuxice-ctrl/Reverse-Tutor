from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_llm_settings_include_provider_api_type_and_capability_presets():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LLM_PROVIDERS" in html
    assert "cfg-provider" in html
    assert "cfg-api-type" in html
    assert "cfg-capability" in html
    assert "cfg-profile-save" in html
    assert "cfg-profile-toggle" in html
    assert "cfg-profile-list" in html
    assert "FREE_DEFAULT_LLM_CONFIG" in html
    assert "free-glm" in html
    assert "GLM-4.7-Flash" in html
    assert "applyLlmProviderPreset" in html
    assert "https://api.openai.com/v1" in html
    assert "https://open.bigmodel.cn/api/paas/v4" in html
    assert "https://open.bigmodel.cn/api/anthropic" in html
    assert "https://api.deepseek.com" in html
    assert "https://api.deepseek.com/anthropic" in html
    assert "https://api.minimax.io/v1" in html
    assert "https://api.minimax.io/anthropic" in html
    assert "MiniMax-M2.7" in html
    assert "https://dashscope.aliyuncs.com/compatible-mode/v1" in html
    assert "https://api.moonshot.cn/v1" in html
    assert "https://api.moonshot.ai/v1" in html
    assert "https://api.groq.com/openai/v1" in html
    assert "https://openrouter.ai/api/v1" in html
    assert "http://localhost:11434/v1" in html


def test_mobile_llm_api_type_is_protocol_family_and_deepseek_uses_current_models():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    provider_block = html.split("const LLM_PROVIDERS", 1)[1].split("const API_TYPE_OPTIONS", 1)[0]
    api_options = html.split("const API_TYPE_OPTIONS", 1)[1].split("const CAPABILITY_OPTIONS", 1)[0]
    api_select = html.split('id="cfg-api-type"', 1)[1].split('id="cfg-api-type-segments"', 1)[0]

    assert "{ value:'openai', label:'OpenAI'" in api_options
    assert "{ value:'anthropic', label:'Anthropic'" in api_options
    assert "openai_compatible" not in api_select
    assert "openai_chat" not in api_select
    assert "openai_responses" not in api_select
    assert "https://api.deepseek.com/anthropic" in provider_block
    assert "deepseek-v4-flash" in provider_block
    assert "deepseek-v4-pro" in provider_block
    assert "id:'minimax'" in provider_block
    assert "id:'minimax-anthropic'" in provider_block
    assert "id:'glm'" in provider_block
    assert "id:'glm-anthropic'" in provider_block
    assert "id:'qwen'" in provider_block
    assert "id:'kimi'" in provider_block
    assert "id:'trial'" not in provider_block
    assert "max_completion_tokens" in html
    assert "providerTemperature" in html
    assert "appendOpenAiDelta" in html
    assert "deepseek-chat" not in provider_block
    assert "deepseek-reasoner" not in provider_block


def test_mobile_llm_supports_anthropic_protocol_family():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function normalizeApiType" in html
    assert "effective_config" in html
    assert "user_has_real" in html
    assert "function anthropic_text" in html
    assert "function anthropicMessagesUrl" in html
    assert "function detectedApiTypeFromBaseUrl" in html
    assert "function applyEndpointDetectionFromBaseUrl" in html
    assert "/v1/messages" in html
    assert "/\\/v1\\/messages$/i.test(baseUrl)" in html
    assert "Claude / Anthropic 格式" in html
    assert "x-api-key" in html
    assert "anthropic-version" in html
    assert "c.api_type === 'anthropic'" in html


def test_mobile_llm_settings_use_custom_picker_ui_instead_of_visible_native_selects():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    llm_section = html.split('id="cfg-provider-trigger"', 1)[1].split('id="cfg-base"', 1)[0]

    assert "llm-config-card" in html
    assert "llm-help" in html
    assert "config-section" in html
    assert "segmented-scroll" in html
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
    assert '<div class="grid grid-cols-2 gap-2">' not in llm_section


def test_mobile_llm_config_profiles_can_be_saved_and_switched():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LLM_CONFIG_PROFILES_KEY" in html
    assert "LLM_CONFIG_PROFILES_OPEN_KEY" in html
    assert "rt-mobile-llm-config-profiles" in html
    assert "rt-mobile-llm-config-profiles-open" in html
    assert "function normalizeLlmProfile" in html
    assert "function restoreLlmProfiles" in html
    assert "function persistLlmProfiles" in html
    assert "function saveCurrentLlmProfile" in html
    assert "function switchLlmProfile" in html
    assert "function deleteLlmProfile" in html
    assert "function llmProfilesOpen" in html
    assert "function setLlmProfilesOpen" in html
    assert "collectLlmConfigFromForm" in html
    assert "DB.kvSet('llm_config_profiles', next)" in html
    assert "profiles.length} / 16" in html
    assert "$('#cfg-profile-save').addEventListener('click', saveCurrentLlmProfile)" in html
    assert "$('#cfg-profile-toggle').addEventListener('click'" in html


def test_mobile_llm_connection_failures_show_actionable_diagnostic_modal():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "llm-diagnostic-modal" in html
    assert "function llmErrorDiagnosis" in html
    assert "function showLlmDiagnostic" in html
    assert "OpenAI 格式" in html
    assert "Claude / Anthropic 格式" in html
    assert "showLlmDiagnostic(r.error || r.reason || '失败', LLM.get_config())" in html
    assert "URL 路径可能不对" in html
    assert "模型名可能不匹配当前服务商" in html


def test_mobile_llm_payload_sanitizes_multimodal_messages_by_capability():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "sanitizeMessagesForCapability" in html
    assert "normalizeContentParts" in html
    assert "当前模型不支持识别图片" in html
    assert "image_url" in html
    assert "anthropic_text" in html
    assert "extractAnthropicText" in html


def test_mobile_openai_payload_merges_system_messages_for_strict_providers():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function normalizeOpenAiMessages" in html
    assert "systemParts.push(text)" in html
    assert "messages: normalizeOpenAiMessages(system, messages)" in html
    assert "if (!out.length) normalized.push({ role:'user', content:'开始吧' })" in html


def test_mobile_domestic_provider_profiles_disable_json_mode_and_handle_full_endpoint_urls():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function isStrictOpenAiCompatibleConfig" in html
    assert "function shouldUseResponseFormat" in html
    assert "opts.jsonMode && shouldUseResponseFormat(c)" in html
    assert "function openAiChatCompletionsUrl" in html
    assert "/\\/chat\\/completions$/i.test(baseUrl)" in html
    assert "finalEndpointForApiType" in html
    assert "open.bigmodel.cn" in html
    assert "api.moonshot.cn" in html
    assert "dashscope.aliyuncs.com" in html
    assert "json_mode:false" in html


def test_android_background_job_carries_api_type_and_capability():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "api_type: cfg.api_type" in html
    assert "capability: cfg.capability" in html
    assert "provider: cfg.provider" in html
    assert "max_completion_tokens" in html
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


def test_mobile_live_stream_wrapper_handles_async_stream_setup():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function normalizeStreamObject" in html
    assert "const ready = Promise.resolve(streamLike)" in html
    assert "return normalizeStreamObject(streamLike)" in html
    assert "LLM stream object missing async iterator" in html


def test_mobile_trial_channel_is_removed():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    provider_block = html.split("const LLM_PROVIDERS", 1)[1].split("const API_TYPE_OPTIONS", 1)[0]

    assert "cfg-trial-code" not in html
    assert "cfg-trial-redeem" not in html
    assert "DEFAULT_TRIAL_PROXY_BASE_URL" not in html
    assert "体验额度" not in html
    assert "id:'trial'" not in provider_block
    assert "function providerKeyScope" in html
    assert "function selectLocalFirstLlmConfig" in html
    assert "function isLocalApiConfig" in html
    assert "LLM_LOCAL_CONFIG_KEY" in html
    assert "providerKeyScope(existing.provider) === providerKeyScope(resolvedProvider)" in html
    assert "if (id === 'glm-anthropic') return 'glm'" in html
    assert "const active = selectLocalFirstLlmConfig(next, localApi)" in html
    assert "const next = selectLocalFirstLlmConfig(saved, localApi)" in html


def test_mobile_free_glm_can_be_explicitly_selected_after_user_api_exists():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    normalize_block = html.split("function normalizeLlmConfig", 1)[1].split("function loadLlmConfigLocal", 1)[0]
    select_block = html.split("function selectLocalFirstLlmConfig", 1)[1].split("function normalizeLlmConfig", 1)[0]
    endpoint_block = html.split("function applyEndpointDetectionFromBaseUrl", 1)[1].split("async function renderLlmProfiles", 1)[0]
    collect_block = html.split("function collectLlmConfigFromForm", 1)[1].split("async function saveCurrentLlmProfile", 1)[0]

    assert "provider === FREE_DEFAULT_LLM_CONFIG.provider" in normalize_block
    assert "baseUrl = baseUrl || FREE_DEFAULT_LLM_CONFIG.base_url" in normalize_block
    assert "apiKey = apiKey || FREE_DEFAULT_LLM_CONFIG.api_key" in normalize_block
    assert "model = model || FREE_DEFAULT_LLM_CONFIG.model" in normalize_block
    assert "if (isRunnableLlmConfig(normalizedCurrent)) return normalizedCurrent" in select_block
    assert "$('#cfg-provider').value = detected.providerId" not in endpoint_block
    assert "const resolvedProvider = provider" in collect_block
    assert "$('#cfg-provider').value = detected.providerId" not in collect_block


def test_mobile_llm_presets_keep_user_edits_and_hide_key_only_after_save():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    provider_block = html.split("const LLM_PROVIDERS", 1)[1].split("const API_TYPE_OPTIONS", 1)[0]
    normalize_block = html.split("function normalizeLlmConfig", 1)[1].split("function loadLlmConfigLocal", 1)[0]
    save_block = html.split("async function saveLlmConfig", 1)[1].split("function llmErrorDiagnosis", 1)[0]
    provider_preset_block = html.split("function applyLlmProviderPreset", 1)[1].split("async function renderSettings", 1)[0]
    api_type_block = html.split("function applyApiTypeSelection", 1)[1].split("function applyLlmProviderPreset", 1)[0]
    listener_block = html.split("$('#cfg-save').addEventListener", 1)[1].split("$('#llm-diagnostic-close')", 1)[0]

    assert "glm-4.5-air" in provider_block
    assert "const rawApiType = String(c.api_type || '').trim()" in normalize_block
    assert "apiType = rawApiType ? apiType : FREE_DEFAULT_LLM_CONFIG.api_type" in normalize_block
    assert "capability = capability || FREE_DEFAULT_LLM_CONFIG.capability" in normalize_block
    assert "baseUrl = baseUrl || FREE_DEFAULT_LLM_CONFIG.base_url" in normalize_block
    assert "model = model || FREE_DEFAULT_LLM_CONFIG.model" in normalize_block
    assert "function showCfgKeyForEditing" in html
    assert "function hideSavedCfgKey" in html
    assert "async function upsertLlmProfileFromConfig" in html
    assert "const profile = saveProfile ? await upsertLlmProfileFromConfig(c" in save_block
    assert "applyLlmProviderPreset(" not in api_type_block
    assert "showCfgKeyForEditing();" in provider_preset_block
    assert "hideSavedCfgKey(cfg.has_api_key)" in save_block
    assert "$('#cfg-key').addEventListener('focus', showCfgKeyForEditing)" in listener_block
    assert "$('#cfg-key').addEventListener('input', () => { showCfgKeyForEditing(); markLlmConfigFormDirty(); })" in listener_block


def test_mobile_llm_resume_does_not_overwrite_unsaved_config_form():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    resume_block = html.split("async function restoreRuntimeConfigOnResume", 1)[1].split("document.addEventListener('visibilitychange'", 1)[0]
    provider_preset_block = html.split("function applyLlmProviderPreset", 1)[1].split("async function renderSettings", 1)[0]
    api_type_block = html.split("function applyApiTypeSelection", 1)[1].split("function applyLlmProviderPreset", 1)[0]
    save_block = html.split("async function saveLlmConfig", 1)[1].split("function llmErrorDiagnosis", 1)[0]
    listener_block = html.split("$('#cfg-save').addEventListener", 1)[1].split("$('#llm-diagnostic-close')", 1)[0]

    assert "let llmConfigFormDirty = false" in html
    assert "function markLlmConfigFormDirty" in html
    assert "function resetLlmConfigFormDirty" in html
    assert "if (state.currentTab === 'settings' && !llmConfigFormDirty) renderSettings();" in resume_block
    assert "markLlmConfigFormDirty();" in provider_preset_block
    assert "markLlmConfigFormDirty();" in api_type_block
    assert "resetLlmConfigFormDirty();" in save_block
    assert "$('#cfg-key').addEventListener('input', () => { showCfgKeyForEditing(); markLlmConfigFormDirty(); })" in listener_block
    assert "$('#cfg-model').addEventListener('input', () => { markLlmConfigFormDirty(); renderModelPresetChips(); renderVisionCapabilityHint(); })" in listener_block
    assert "$('#cfg-base').addEventListener('input', () => { markLlmConfigFormDirty(); applyEndpointDetectionFromBaseUrl(); })" in listener_block


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


def test_mobile_proactive_conversation_has_global_modes_and_local_dispatch():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "PROACTIVE_CONFIG_KEY" in html
    assert "PROACTIVE_MODES" in html
    assert "online" in html
    assert "offline" in html
    assert "sleep" in html
    assert "custom" in html
    assert "minIntervalMs: 30 * 60 * 1000" in html
    assert "maxIntervalMs: 60 * 60 * 1000" in html
    assert "offline: { label: '离线', disabled: true }" in html
    assert "custom: { label: '自定义'" in html
    assert "PROACTIVE_CUSTOM_MINUTES_KEY" in html
    assert "global-proactive-custom-minutes" not in html
    assert "跟随会话窗原始设定未确定的默认为离线" in html
    assert "mode_disabled" in html
    assert "proactiveIntervalMs" in html
    assert "function proactiveConfig" in html
    assert "function renderGlobalProactiveControls" in html
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
    assert "if (r.lastReply && !silent)" in html
    assert "notifyAssistantReply('后台 LLM 回复', r.lastReply, 4200, { source: 'native_background', force: true })" in html
    assert "notifyAssistantReply('主动对话', result.reply, 4200, { source: 'proactive' })" in html
    assert 'id="message-popup-body" class="text-sm leading-snug max-h-28 overflow-y-auto whitespace-pre-wrap break-words"' in html
    assert "function showSystemReplyNotification" in html


def test_mobile_prompt_uses_post_history_instruction_for_better_role_replies():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function finalReplyInstruction" in html
    assert "Post-History Instructions" in html
    assert "只写学生 AI 的下一次回复" in html
    assert "尊重用户自主权" in html
    assert "不要把非学习目标强行改成教学/知识点讲解" in html
    assert "messages.push({ role: 'system', content: finalReplyInstruction" in html
    assert "shapeReplyBubbles(reply, 1)" in html
