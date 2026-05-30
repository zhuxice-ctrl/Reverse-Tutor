from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def mobile_html() -> str:
    return (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")


def test_mobile_header_uses_global_sidebar_api_status_and_top_right_new_entry():
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


def test_mobile_new_session_modal_is_quick_sheet_with_custom_preset_import_and_full_custom_page():
    html = mobile_html()

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


def test_mobile_preset_import_export_is_lightweight_and_safe():
    html = mobile_html()

    assert "function buildLightweightPreset" in html
    assert "function sanitizeImportedPreset" in html
    assert "external_resources" in html
    assert "api_key" in html
    assert "delete safe.api_key" in html
    assert "messages" in html
    assert "delete safe.messages" in html
    assert "base64" in html
    assert "not automatically downloaded" in html


def test_mobile_settings_long_term_sections_are_kept_and_transient_sections_are_folded():
    html = mobile_html()
    settings = html.split('data-view="settings"', 1)[1].split("</section>", 1)[0]

    assert 'id="settings-api-section"' in settings
    assert 'id="settings-data-section"' in settings
    assert 'id="settings-update-section"' in settings
    assert 'id="settings-system-section"' in settings
    assert 'id="settings-transient-section"' in settings
    assert '<details id="settings-transient-section"' in settings
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
