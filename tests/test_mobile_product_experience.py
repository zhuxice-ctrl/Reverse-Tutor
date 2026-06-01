from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def mobile_html() -> str:
    return (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")


def test_mobile_header_uses_global_sidebar_and_top_right_new_entry():
    html = mobile_html()
    header = html.split("<header", 1)[1].split("</header>", 1)[0]
    drawer = html.split('id="session-drawer"', 1)[1].split("</aside>", 1)[0]

    assert 'id="global-sidebar-open"' in header
    assert 'data-lucide="ellipsis"' in header
    assert 'id="header-mode"' in header
    assert header.index('id="header-mode"') < header.index('id="header-title"')
    assert 'id="header-new-session"' in header
    assert 'data-lucide="plus"' in header
    assert 'id="drawer-new"' not in drawer
    assert 'id="global-sidebar-theme-grid"' in drawer
    assert 'id="global-avatar-visible"' in drawer
    assert 'id="global-sidebar-status"' in drawer
    sidebar_renderer = html.split("async function renderSessionDrawer", 1)[1].split("async function openDrawer", 1)[0]
    assert "API 状态" not in sidebar_renderer
    assert "当前会话" not in sidebar_renderer
    assert "renderGlobalProactiveControls" in sidebar_renderer
    assert "全局类主动对话" in html
    assert "data-global-proactive-mode" in html
    assert 'value="${esc(String(cfg.customMinutes))}"' in html


def test_mobile_session_thread_is_immersive_without_global_navigation():
    html = mobile_html()
    header_fn = html.split("async function refreshHeader", 1)[1].split("// --- Chat ---", 1)[0]

    assert "body.session-focus .bottom-nav" in html
    assert "body.session-focus #global-sidebar-open" in html
    assert "body.session-focus #header-mode" in html
    assert "body.session-focus #header-new-session" in html
    assert "body.new-session-focus .bottom-nav" in html
    assert "document.body.classList.toggle('session-focus', inSessionPage)" in header_fn
    assert "document.body.classList.toggle('new-session-focus', inNewPage)" in header_fn
    assert "globalBtn?.classList.toggle('hidden', inSessionPage || inNewPage)" in header_fn
    assert "newBtn?.classList.toggle('hidden', inSessionPage || inNewPage)" in header_fn
    assert "contextBtn?.classList.toggle('hidden', !inThread)" in header_fn
    assert "drawerBtn.innerHTML = inSessionPage ? '<i data-lucide=\"chevron-left\">返回</i>'" in header_fn
    assert "脉络" in html


def test_mobile_settings_do_not_duplicate_global_sidebar_controls():
    html = mobile_html()
    settings = html.split('data-view="settings"', 1)[1].split("</section>", 1)[0]

    assert 'id="theme-grid"' not in settings
    assert 'id="settings-transient-section"' not in settings
    assert "临时与会话级选项" not in settings


def test_mobile_hidden_avatars_render_no_placeholder_or_initials():
    html = mobile_html()
    avatar_fn = html.split("function sessionAvatarHtml", 1)[1].split("function fileToAvatarDataUrl", 1)[0]
    card_fn = html.split("const sessionCardHtml =", 1)[1].split("const pinnedCards =", 1)[0]

    assert "globalAvatarsVisible()" in avatar_fn
    assert "return '';" in avatar_fn
    assert "sessionInitials(session)" in avatar_fn
    assert "avatar-hidden" in card_fn
    assert "s.avatar_hidden || !globalAvatarsVisible()" in card_fn


def test_mobile_sessions_can_be_renamed_and_created_with_custom_title():
    html = mobile_html()

    assert 'data-session-action="rename"' in html
    assert "async function renameSession" in html
    assert "session.title = title" in html
    assert 'id="new-title"' in html
    assert "title: $('#new-title').value.trim()" in html
    assert "title || `${role}" in html


def test_mobile_new_session_is_child_page_with_custom_preset_import_and_full_custom_page():
    html = mobile_html()
    new_page = html.split('id="new-session-page"', 1)[1].split("</section>", 1)[0]
    open_new_fn = html.split("function openNew", 1)[1].split("function closeNew", 1)[0]
    close_new_fn = html.split("function closeNew", 1)[1].split("window.closeNew", 1)[0]

    assert 'data-view="new-session"' in html
    assert 'id="new-session-page"' in html
    assert 'id="new-modal"' not in html
    assert "fixed inset-0 bg-black/80 hidden items-end" not in html
    assert 'id="new-quick-panel"' in html
    assert 'id="new-custom-panel"' in html
    assert 'data-new-mode="custom"' in html
    assert 'data-new-mode="builtin"' in html
    assert 'id="preset-import-file"' in html
    assert 'id="preset-preview"' in html
    assert 'data-preset-action="save"' in html
    assert 'data-preset-action="create"' in html
    assert 'data-preset-action="customize"' in html
    assert "function openNewCustomPanel" in html
    assert 'id="new-create"' in new_page
    assert "switchTab('new-session')" in open_new_fn
    assert "const targetTab = route.tab || 'chat'" in close_new_fn
    assert "switchTab(targetTab)" in close_new_fn


def test_mobile_custom_profile_tags_and_runtime_hint_are_present():
    html = mobile_html()
    prompt_fn = html.split("function build_system_prompt", 1)[1].split("function finalReplyInstruction", 1)[0]

    assert 'id="profile-tag-bank"' in html
    assert 'id="profile-selected-tags"' in html
    assert 'id="profile-custom-tag"' in html
    assert 'maxlength="20"' in html
    assert 'maxlength="1000"' in html
    assert 'maxlength="5000"' in html
    assert "PROFILE_TAG_CATEGORIES" in html
    assert "function buildStructuredProfileSummary" in html
    assert "function buildRuntimeProfileHint" in html
    assert "runtime_profile_hint" in prompt_fn
    assert "profile_long_text" not in prompt_fn


def test_mobile_profile_tags_use_large_dialog_with_sectioned_hash_tags():
    html = mobile_html()
    custom_panel = html.split('id="new-custom-panel"', 1)[1].split('id="profile-description"', 1)[0]
    dialog = html.split('id="profile-tag-dialog"', 1)[1].split('<!-- ==============', 1)[0]
    render_fn = html.split("function renderProfileTags", 1)[1].split("function addProfileTag", 1)[0]
    categories_src = html.split("const PROFILE_TAG_CATEGORIES", 1)[1].split("function normalizeProfileTags", 1)[0]

    assert 'id="profile-tag-open"' in html
    assert 'id="profile-tag-close"' in html
    assert 'id="profile-tag-dialog"' in html
    assert 'max-h-[88vh]' in dialog or 'h-[88vh]' in dialog
    assert 'id="profile-tag-bank"' not in custom_panel

    for label in ["学习弱点", "性格反应", "学习偏好", "抗拒行为"]:
        assert f"label: '{label}'" in categories_src

    for tag in [
        "基础断层",
        "公式会背不会用",
        "审题跳步",
        "迁移困难",
        "容易焦虑",
        "被否定会退缩",
        "先例题再抽象",
        "多追问少讲解",
        "逃避难题",
        "急着要答案",
    ]:
        assert f"#{tag}" not in categories_src

    category_blocks = re.findall(r"\{\s*label: '[^']+', tags: \[([^\]]+)\]\s*\}", categories_src)
    assert len(category_blocks) == 4
    assert all(block.count("'") // 2 == 8 for block in category_blocks)
    assert "<details" in render_fn
    assert "<summary" in render_fn
    assert "category === 'weakness' || query ? 'open' : ''" in render_fn
    assert "data-profile-fold-icon" in render_fn
    assert 'tagHash(label)' in render_fn
    assert 'tagHash(tag.label)' in render_fn
    assert "addProfileTag($('#profile-custom-tag').value, 'custom')" in html


def test_mobile_preset_import_export_is_lightweight_and_safe():
    html = mobile_html()
    sanitizer = html.split("function sanitizeImportedPreset", 1)[1].split("function applyPresetToCustomForm", 1)[0]

    assert "function buildLightweightPreset" in html
    assert "function sanitizeImportedPreset" in html
    assert "external_resources" in html
    assert "api_key" in html
    assert "delete safe.api_key" not in sanitizer
    assert "messages" in html
    assert "delete safe.messages" not in sanitizer
    assert "base64" not in sanitizer
    assert "not automatically downloaded" in html


def test_mobile_default_free_llm_config_does_not_ship_client_api_key():
    html = mobile_html()
    free_config = html.split("const FREE_DEFAULT_LLM_CONFIG = {", 1)[1].split("};", 1)[0]

    assert not re.search(r"api_key\s*:\s*['\"][^'\"]{12,}['\"]", free_config)


def test_mobile_preset_import_sanitizer_uses_allowlist_schema():
    html = mobile_html()
    sanitizer = html.split("function sanitizeImportedPreset", 1)[1].split("function applyPresetToCustomForm", 1)[0]

    assert "const allowedKeys = new Set([" in sanitizer
    assert "const safe = { ...(raw || {}) }" not in sanitizer
    assert "delete safe.api_key" not in sanitizer
    assert "delete safe.messages" not in sanitizer
    for allowed in [
        "schema",
        "id",
        "title",
        "role",
        "goal",
        "deadline",
        "personality",
        "settings",
        "profile_tags",
        "profile_summary",
        "runtime_profile_hint",
        "external_resources",
    ]:
        assert allowed in sanitizer


def test_mobile_preset_import_sanitizes_setting_values():
    html = mobile_html()

    assert "function sanitizePresetSettings" in html
    assert "const PRESET_SETTING_ENUMS" in html
    assert "tone: new Set(['natural', 'calm', 'warm'])" in html
    assert "proactivity: new Set(['low', 'normal', 'high'])" in html
    assert "privacy_level: new Set(['standard', 'strict'])" in html
    assert "web_search_enabled = rawSettings.web_search_enabled === true" in html
    assert "kg_extraction_enabled = rawSettings.kg_extraction_enabled !== false" in html


def test_mobile_runtime_memory_hint_has_global_item_cap():
    html = mobile_html()
    hint_fn = html.split("async function buildRuntimeMemoryHint", 1)[1].split("async function add_anchor", 1)[0]

    assert "const RUNTIME_MEMORY_HINT_MAX_ITEMS = 16" in html
    assert "pushRuntimeMemoryHintLine" in hint_fn
    assert "itemCount >= RUNTIME_MEMORY_HINT_MAX_ITEMS" in hint_fn


def test_mobile_runtime_memory_hint_prioritizes_mastery_errors_before_related_kg_context():
    html = mobile_html()
    hint_fn = html.split("async function buildRuntimeMemoryHint", 1)[1].split("async function add_anchor", 1)[0]

    assert hint_fn.index("for (const m of (masteries || []).slice(0, 10))") < hint_fn.index("for (const concept of")
    assert hint_fn.index("for (const e of errors.slice(0, 10))") < hint_fn.index("for (const concept of")


def test_mobile_settings_long_term_sections_are_kept_without_sidebar_duplicates():
    html = mobile_html()
    settings = html.split('data-view="settings"', 1)[1].split("</section>", 1)[0]

    assert 'id="settings-api-section"' in settings
    assert 'id="settings-data-section"' in settings
    assert 'id="settings-update-section"' in settings
    assert 'id="settings-system-section"' not in settings
    assert 'id="settings-transient-section"' not in settings
    assert settings.index('id="settings-api-section"') < settings.index('id="settings-data-section"')


def test_mobile_thinking_chain_is_public_strategy_only_and_animated():
    html = mobile_html()
    streaming_fn = html.split("function getOrCreateStreamingBubble", 1)[1].split("function updateThinkingStage", 1)[0]
    summary_fn = html.split("function renderProcessSummary", 1)[1].split("function renderCitedSources", 1)[0]

    assert "思考摘要" not in html
    assert "思考链" in streaming_fn
    assert "公开策略链" in streaming_fn
    assert "thinking..." in streaming_fn
    assert "思考链" in summary_fn
    assert "公开策略链" in summary_fn
    assert "reasoning_content" not in html
    assert "hidden_reasoning" not in html


def test_mobile_graph_filters_process_nodes_from_mastery_and_digest_paths():
    html = mobile_html()
    normalize_action_fn = html.split("function normalizeAction", 1)[1].split("function normalizeEvidence", 1)[0]
    upsert_mastery_fn = html.split("async function upsert_mastery", 1)[1].split("async function upsert_error_log", 1)[0]
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]

    for name in ["后台回复", "后台生成", "自由回复", "模型自由回复"]:
        assert name in html
    assert "!isLogicalGraphKp(kp)" in normalize_action_fn
    assert "if (!isLogicalGraphKp(kp)) return;" in upsert_mastery_fn
    assert "masteries.filter(m => isLogicalGraphKp(m.kp || m.knowledge_point))" in build_graph_fn
