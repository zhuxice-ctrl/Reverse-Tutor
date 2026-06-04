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
    assert "全局主动对话设置" in html
    assert "全局离线：所有会话都不会主动发起对话。" in html
    assert "跟随会话窗原始设定未确定的默认为离线" in html
    assert "约每 ${cfg.customMinutes} 分钟" not in html
    assert "global-proactive-custom-minutes" not in html
    assert 'id="global-proactive-custom-minutes"' not in html
    assert "自定义间隔（分钟）" not in html
    assert "data-global-proactive-mode" in html
    assert "data-global-proactive-panel" in html
    assert "data-global-proactive-strip" in html
    assert ".global-proactive-mode-strip {\n    gap: 5px;" in html
    assert "global-proactive-mode-strip .seg-option" in html
    assert "function bindGlobalProactiveSwipe" in html
    assert "function setAdjacentGlobalProactiveMode" in html
    assert "Math.abs(dx) < 34" in html
    assert "pointerdown" in html
    assert "pointerup" in html
    assert "scrollIntoView({ block: 'nearest', inline: 'center' })" in html


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

    assert 'data-session-swipe-action="rename"' in html
    assert "async function renameSession" in html
    assert "session.title = title" in html
    assert 'id="new-title"' in html
    assert "title: $('#new-title').value.trim()" in html
    assert "title || `${role}" in html


def test_mobile_session_row_swipe_actions_are_separate_from_long_press_avatar_menu():
    html = mobile_html()
    popover = html.split('id="session-card-popover"', 1)[1].split("</div>", 1)[0]
    card_fn = html.split("const sessionCardHtml =", 1)[1].split("const pinnedCards =", 1)[0]
    home_events = html.split("home.querySelectorAll('[data-session-open]')", 1)[1].split("refreshIcons();", 1)[0]
    handler = html.split("async function handleSessionSwipeAction", 1)[1].split("async function openSessionWindow", 1)[0]

    assert 'data-session-swipe-action="pin"' in card_fn
    assert 'data-session-swipe-action="delete"' in card_fn
    assert 'data-session-swipe-action="rename"' in card_fn
    assert 'data-session-action="pin"' not in popover
    assert 'data-session-action="rename"' not in popover
    assert 'data-session-action="preset-export"' in popover
    assert 'data-session-action="avatar"' in popover
    assert 'data-session-action="avatar-clear"' in popover
    assert "touchAction = 'pan-y'" in home_events
    assert "session-swipe-open" in home_events
    assert "handleSessionSwipeAction" in home_events
    assert "confirm('删除该会话及所有数据？')" in handler
    assert "ENGINE.delete_session(sid)" in handler


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
    assert new_page.index('id="new-create"') < new_page.index('data-new-mode="custom"')
    assert new_page.index('data-new-mode="custom"') < new_page.index('id="tpl-grid"')
    assert "switchTab('new-session')" in open_new_fn
    assert "const targetTab = route.tab || 'chat'" in close_new_fn
    assert "switchTab(targetTab)" in close_new_fn


def test_mobile_highlight_themes_match_reference_styles():
    html = mobile_html()
    berry_theme = html.split(":root.theme-berry", 1)[1].split(":root.theme-midnight", 1)[0]
    ember_theme = html.split(":root.theme-ember", 1)[1].split(":root.theme-ocean", 1)[0]
    ocean_theme = html.split(":root.theme-ocean", 1)[1].split("html, body", 1)[0]
    theme_options = html.split("const THEME_OPTIONS = [", 1)[1].split("];", 1)[0]

    assert "label:'迈阿密夕阳'" in theme_options
    assert "#2a1b27" in berry_theme
    assert "#d87963" in berry_theme
    assert "#d8b86b" in berry_theme
    assert "swatches:['#2a1b27','#d87963','#d8b86b']" in theme_options
    assert "label:'侘寂原木'" in theme_options
    assert "#292724" in ember_theme
    assert "#b88c67" in ember_theme
    assert "#8f9d92" in ember_theme
    assert "swatches:['#292724','#b88c67','#8f9d92']" in theme_options
    assert "label:'复古黑客'" in theme_options
    assert "color-scheme: dark" in ocean_theme
    assert "#09100e" in ocean_theme
    assert "#3fbd8d" in ocean_theme
    assert "#8460b5" in ocean_theme
    assert "swatches:['#09100e','#3fbd8d','#8460b5']" in theme_options
    for theme in [berry_theme, ember_theme, ocean_theme]:
        assert "--grain-overlay: none" in theme
        assert "--texture-overlay: none" in theme
        assert "--texture-opacity: 0" in theme
        assert "repeating-linear-gradient" not in theme
        assert "linear-gradient(0deg" not in theme


def test_mobile_builtin_session_presets_are_rich_and_varied():
    html = mobile_html()
    template_src = html.split("const TEMPLATES = [", 1)[1].split("];", 1)[0]
    open_new_fn = html.split("function openNew", 1)[1].split("function closeNew", 1)[0]
    create_fn = html.split("async function createSessionFromForm", 1)[1].split("$('#new-create')", 1)[0]
    apply_preset_fn = html.split("function applyPresetToCustomForm", 1)[1].split("function renderPresetPreview", 1)[0]

    assert template_src.count("{ label:") >= 16
    for label in [
        "高三冲刺",
        "Python 入门",
        "雅思口语",
        "考研英语",
        "公务员行测",
        "前端作品集",
        "日语 N2",
        "机器学习入门",
    ]:
        assert label in template_src
    for field in ["profile_tags", "profile_long_text", "settings", "feedback_intensity", "probing_intensity", "scaffold_intensity"]:
        assert field in template_src
    assert "applyPresetToCustomForm({ ...t" in open_new_fn
    assert "state.newStrategySettings" in apply_preset_fn
    assert "settings: state.newStrategySettings" in create_fn


def test_mobile_custom_profile_tags_and_runtime_hint_are_present():
    html = mobile_html()
    prompt_fn = html.split("function build_system_prompt", 1)[1].split("function finalReplyInstruction", 1)[0]
    custom_panel = html.split('id="new-custom-panel"', 1)[1].split('id="new-create"', 1)[0]

    assert 'id="profile-tag-bank"' in html
    assert 'id="profile-selected-tags"' in html
    assert 'id="profile-custom-tag"' in html
    assert 'id="profile-long-text"' in custom_panel
    assert 'id="profile-description"' not in custom_panel
    assert 'id="new-pers"' not in custom_panel
    assert '画像描述（最多 1000 字）' not in custom_panel
    assert '语气、追问强度、纠错时机等偏好' not in custom_panel
    assert 'maxlength="20"' in html
    assert 'maxlength="5000"' in html
    assert "PROFILE_TAG_CATEGORIES" in html
    assert "function buildStructuredProfileSummary" in html
    assert "function buildRuntimeProfileHint" in html
    assert "mergeProfileLongText" in html
    assert "runtime_profile_hint" in prompt_fn
    assert "profile_long_text" not in prompt_fn


def test_mobile_profile_tags_use_large_dialog_with_sectioned_hash_tags():
    html = mobile_html()
    custom_panel = html.split('id="new-custom-panel"', 1)[1].split('id="profile-long-text"', 1)[0]
    dialog = html.split('id="profile-tag-dialog"', 1)[1].split('<!-- ==============', 1)[0]
    render_fn = html.split("function renderProfileTags", 1)[1].split("function addProfileTag", 1)[0]
    categories_src = html.split("const PROFILE_TAG_CATEGORIES", 1)[1].split("function normalizeProfileTags", 1)[0]

    assert 'id="profile-tag-open"' in html
    assert 'id="profile-tag-close"' in html
    assert 'id="profile-tag-dialog"' in html
    assert 'max-h-[88vh]' in dialog or 'h-[88vh]' in dialog
    assert 'id="profile-tag-bank"' not in custom_panel
    assert 'id="profile-tag-category-buttons"' in dialog

    for label in ["学习弱点", "性格反应", "学习偏好", "抗拒行为", "策略调音台"]:
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
    assert len(category_blocks) == 5
    tag_counts = [block.count("'") // 2 for block in category_blocks]
    assert all(count >= 8 for count in tag_counts)
    assert any(count > 8 for count in tag_counts)
    assert 'data-profile-category-button' in render_fn
    assert 'state.activeProfileTagCategory' in render_fn
    assert 'state.profileTagExpanded' in render_fn
    assert '.slice(0, 8)' in render_fn
    assert 'data-profile-tag-toggle' in render_fn
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
    assert "可公开推理旁白" in streaming_fn
    assert "thinking..." in streaming_fn
    assert "data-thinking-monologue" in streaming_fn
    assert "thinking-monologue live" in streaming_fn
    assert "思考链" in summary_fn
    assert "可公开推理旁白" in summary_fn
    assert "function publicThinkingSentence" in html
    assert "function appendThinkingNarration" in html
    assert "function tickThinkingNarration" in html
    assert "function resetThinkingNarration" in html
    assert "function pauseStreamingThinking" in html
    assert "const THINKING_CHAIN_OPEN_KEY = 'rt-mobile-thinking-chain-open';" in html
    assert "function thinkingChainOpen" in html
    assert "function setThinkingChainOpen" in html
    assert "function bindThinkingPreference" in html
    assert "${thinkingChainOpen() ? 'open' : ''}" not in streaming_fn
    assert 'details class="thinking-panel text-[11px] text-neutral-500 mb-2">' in streaming_fn
    assert "bindThinkingPreference(bubble.querySelector('.thinking-panel'))" not in streaming_fn
    assert "${thinkingChainOpen() ? 'open' : ''}" in summary_fn
    assert "$$('.process-summary').forEach(bindThinkingPreference);" in html
    assert "thinkingCursor" in html
    assert "我先不急着答" in html
    assert "我脑子里先过一遍资料线索" in html
    assert "回复要像学生自然开口" in html
    assert "function renderProcessMonologue" in html
    assert "thinking-monologue" in html
    assert "<dt>判断</dt>" not in summary_fn
    assert "<dt>依据</dt>" not in summary_fn
    update_streaming_fn = html.split("function updateStreamingBubble", 1)[1].split("function finalizeStreamingBubble", 1)[0]
    assert "thinkingChainOpen()" not in update_streaming_fn
    assert "details.open = false" in update_streaming_fn
    pause_streaming_fn = html.split("function pauseStreamingThinking", 1)[1].split("function finalizeStreamingBubble", 1)[0]
    assert "indicator.remove()" in pause_streaming_fn
    assert "details.open = false" in pause_streaming_fn
    assert "live.classList.remove('live')" in pause_streaming_fn
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
