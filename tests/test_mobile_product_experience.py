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
    assert 'id="global-sidebar-memo"' in drawer
    sidebar_renderer = html.split("async function renderSessionDrawer", 1)[1].split("async function openDrawer", 1)[0]
    assert "API 状态" not in sidebar_renderer
    assert "当前会话" not in sidebar_renderer
    assert "renderGlobalProactiveControls" not in sidebar_renderer
    assert "renderSidebarMemo" in sidebar_renderer
    assert "GLOBAL_SIDEBAR_MEMO_KEY" in html
    assert "function sidebarMemoSegments" in html
    assert "function renderSidebarMemo" in html
    assert "function addSidebarMemoSegment" in html
    assert "function saveSidebarMemoSegments" in html
    assert "function openSidebarMemoDelete" in html
    assert "function confirmSidebarMemoDelete" in html
    assert 'id="sidebar-memo-delete-dialog"' in html
    assert 'id="sidebar-memo-delete-confirm"' in html
    assert 'id="sidebar-memo-delete-cancel"' in html
    assert "data-sidebar-memo-section" in html
    assert "data-sidebar-memo-delete-index" in html
    assert "data-sidebar-memo-divider" in html
    assert "data-sidebar-memo-text" in html
    assert "备忘录" in html
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
    assert "const inReadOnlyBrowse = !!state.chatReadOnlyBrowse && inThread" in header_fn
    assert "contextBtn?.classList.toggle('hidden', !inThread || inReadOnlyBrowse)" in header_fn
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
    rename_fn = html.split("async function renameSession", 1)[1].split("function chooseSessionAvatar", 1)[0]

    assert 'data-session-action="rename"' in html
    assert 'id="session-rename-sheet"' in html
    assert 'id="session-rename-title"' in html
    assert 'id="session-rename-save"' in html
    assert 'id="session-rename-close"' in html
    assert "function openSessionRenameSheet" in html
    assert "function closeSessionRenameSheet" in html
    assert "async function saveSessionRename" in html
    assert "async function renameSession" in html
    assert "prompt(" not in rename_fn
    assert "openSessionRenameSheet(sid, session.title || '')" in rename_fn
    assert "session.title = title" in html
    assert "await saveSessionRename()" in html
    assert 'id="new-title"' in html
    assert "title: $('#new-title').value.trim()" in html
    assert "title || `${role}" in html


def test_mobile_context_strategy_controls_are_visible_and_runtime_bound():
    html = mobile_html()
    strategy_panel = html.split("function strategySettingsPanelHtml", 1)[1].split("async function saveCurrentSessionStrategySettings", 1)[0]
    save_fn = html.split("async function saveCurrentSessionStrategySettings", 1)[1].split("function bindStrategySettingsControls", 1)[0]
    prompt_fn = html.split("function build_system_prompt", 1)[1].split("function should_extract", 1)[0]

    assert "native-config-select" not in strategy_panel
    assert "class=\"strategy-select\"" in strategy_panel
    for setting in [
        "correction_timing",
        "correction_persistence",
        "review_frequency",
        "tone",
        "proactivity",
        "privacy_level",
    ]:
        assert f'data-strategy-setting="{setting}"' in strategy_panel
    assert 'data-strategy-setting="image_retention_days"' not in strategy_panel
    assert 'id="setting-image-retention-days"' not in strategy_panel
    assert "严格：只记录有学习证据的内容" in strategy_panel
    assert "s.settings = ENGINE.normalizeStrategySettings(raw)" in save_fn
    assert "formatStrategySettings(session.settings || {})" in prompt_fn


def test_mobile_context_avatar_and_session_info_are_editable_without_layout_drift():
    html = mobile_html()
    context_settings = html.split("async function renderContextSettings", 1)[1].split("// --- Insights", 1)[0]
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]

    assert ".context-avatar-preview .session-avatar" in css
    assert "position: static" in css
    assert 'class="context-avatar-preview' in context_settings
    for field in [
        "setting-session-title",
        "setting-session-role",
        "setting-session-goal",
        "setting-session-deadline",
        "setting-session-personality",
        "setting-save-session-info",
    ]:
        assert field in context_settings
    assert "async function saveCurrentSessionPersonaInfo" in html
    assert "s.title = title" in html
    assert "s.persona = { ...s.persona, role, goal, deadline, personality }" in html


def test_mobile_core_persona_edits_warn_before_saving_and_can_continue():
    html = mobile_html()
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    warning_markup = html.split('id="persona-change-warning"', 1)[1].split("</script>", 1)[0]
    save_fn = html.split("async function saveCurrentSessionPersonaInfo", 1)[1].split("async function renderContextSettings", 1)[0]

    assert 'id="persona-change-warning"' in html
    assert 'class="persona-warning-overlay hidden"' in html
    assert 'class="persona-warning-dialog"' in html
    assert ".persona-warning-overlay" in css
    assert "align-items: center" in css
    assert "justify-content: center" in css
    assert "background: rgba(0,0,0,.74)" in css
    assert ".persona-warning-overlay.hidden" in css
    assert ".persona-warning-dialog" in css
    assert "graph-sheet-handle" not in warning_markup
    assert "choice-sheet safe-bottom" not in warning_markup
    assert "大幅改动可能会影响体验感，请慎重选择" in html
    assert 'id="persona-change-warning-confirm"' in html
    assert 'id="persona-change-warning-cancel"' in html
    assert "detectCorePersonaChanges" in html
    assert "openPersonaChangeWarning" in html
    assert "commitCurrentSessionPersonaInfo" in html
    assert "if (changes.length && !skipWarning)" in save_fn
    assert "state.pendingPersonaInfoChange" in html


def test_mobile_core_persona_edits_record_transition_for_llm_and_memory():
    html = mobile_html()
    prompt_fn = html.split("function build_system_prompt", 1)[1].split("function should_extract", 1)[0]
    commit_fn = html.split("async function commitCurrentSessionPersonaInfo", 1)[1].split("async function renderContextSettings", 1)[0]

    assert "persona_transition_notice" in html
    assert "buildPersonaTransitionNotice" in html
    assert "formatPersonaTransitionNotice" in html
    assert "自然承接这次画像变更" in html
    assert "不要照抄示例台词" in html
    assert "addLocalAnchor('persona_change'" in commit_fn
    assert "s.persona_transition_notice = transitionNotice" in commit_fn
    assert "formatPersonaTransitionNotice(session.persona_transition_notice)" in prompt_fn


def test_mobile_deadline_status_uses_recorded_local_time_and_reaches_runtime_prompt():
    html = mobile_html()
    deadline_fn = html.split("function sessionDeadlineStatus", 1)[1].split("function strategyOption", 1)[0]
    prompt_fn = html.split("function build_system_prompt", 1)[1].split("function should_extract", 1)[0]
    context_settings = html.split("async function renderContextSettings", 1)[1].split("// --- Insights", 1)[0]

    assert "Date.now()" in deadline_fn
    assert "created_at" in deadline_fn
    assert "source: 'local_device_time'" in deadline_fn
    assert "deadline_status" in prompt_fn
    assert "sessionDeadlineStatus(session)" in prompt_fn
    assert "setting-deadline-status" in context_settings
    assert "setting-deadline-time-source" in context_settings


def test_mobile_context_image_tab_is_removed_and_images_move_into_anchors():
    html = mobile_html()
    context_markup = html.split('id="learning-context-page"', 1)[1].split('<div id="learning-context-body"', 1)[0]
    render_fn = html.split("async function renderLearningContext", 1)[1].split("async function renderContextGraph", 1)[0]
    open_fn = html.split("async function openLearningContext", 1)[1].split("function closeLearningContext", 1)[0]

    assert 'data-context-tab="images"' not in context_markup
    assert "return renderContextImages(renderId)" not in render_fn
    assert "'images'" not in open_fn.split("includes(tab)", 1)[0]
    assert "function renderContextImagesData" not in html
    assert "async function renderContextImages" not in html


def test_mobile_context_anchor_import_accepts_images_as_source_material():
    html = mobile_html()
    anchors_fn = html.split("async function renderContextAnchors", 1)[1].split("async function renderContextNotes", 1)[0]
    image_import_fn = html.split("async function importAnchorImages", 1)[1].split("function sourcePreviewText", 1)[0]

    assert 'id="context-anchor-image-file"' in anchors_fn
    assert 'accept="image/png,image/jpeg,image/webp"' in anchors_fn
    assert "await importAnchorImages(e.target.files" in anchors_fn
    assert "导入图片资料" in anchors_fn
    assert "图片资料会直接归入锚点" in anchors_fn
    assert "row = await uploadImageExtract(file)" in image_import_fn
    assert "await addImageExtractAsSourceAnchor(file, row)" in image_import_fn
    assert "图片资料已导入锚点" in image_import_fn


def test_mobile_anchor_image_import_falls_back_without_backend_api():
    html = mobile_html()
    image_import_fn = html.split("async function importAnchorImages", 1)[1].split("function sourcePreviewText", 1)[0]
    image_anchor_fn = html.split("async function addImageExtractAsSourceAnchor", 1)[1].split("async function importAnchorImages", 1)[0]
    preview_fn = html.split("function sourcePreviewText", 1)[1].split("function sourceAnchorCardHtml", 1)[0]

    assert "async function imageFileToDataUrl" in html
    assert "async function buildLocalImageAnchorRow" in html
    assert "row = await uploadImageExtract(file)" in image_import_fn
    assert "row = await buildLocalImageAnchorRow(file, err)" in image_import_fn
    assert "后端不可用，已本地归入锚点" in image_import_fn
    assert "image_local_only" in image_anchor_fn
    assert "当前静态服务没有图片识别接口" in image_anchor_fn
    assert "source_original_url: row.original_url || row.data_url || ''" in image_anchor_fn
    assert "diagnostics.code === 'image_local_only'" in preview_fn


def test_mobile_anchor_lists_group_uploaded_materials_by_type():
    html = mobile_html()
    context_anchors_fn = html.split("async function renderContextAnchors", 1)[1].split("async function renderContextNotes", 1)[0]
    anchors_fn = html.split("async function renderAnchors", 1)[1].split("$('#anchor-form')", 1)[0]
    grouped_fn = html.split("function anchorCategoryMeta", 1)[1].split("async function renderAnchors", 1)[0]

    assert "function anchorCategoryMeta" in html
    assert "function renderGroupedAnchorsHtml" in html
    for label in ["手动锚点", "图片资料", "文件资料", "画像变更", "其他记录"]:
        assert label in grouped_fn
    assert "source_type === 'image'" in grouped_fn
    assert "renderGroupedAnchorsHtml(anchors.filter(a => a.kind !== 'note'), { deleteAttr: 'context-del-anchor' })" in context_anchors_fn
    assert "renderGroupedAnchorsHtml(anchors, { deleteAttr: 'del' })" in anchors_fn


def test_mobile_context_async_renders_cannot_overwrite_new_tab():
    html = mobile_html()
    render_fn = html.split("async function renderLearningContext", 1)[1].split("async function renderContextGraph", 1)[0]
    graph_fn = html.split("async function renderContextGraph", 1)[1].split("async function renderContextAnchors", 1)[0]
    anchors_fn = html.split("async function renderContextAnchors", 1)[1].split("async function renderContextNotes", 1)[0]
    notes_fn = html.split("async function renderContextNotes", 1)[1].split("function relativeDayText", 1)[0]
    errors_fn = html.split("async function renderContextErrors", 1)[1].split("function addCalendarMonths", 1)[0]
    settings_fn = html.split("async function renderContextSettings", 1)[1].split("// --- Insights", 1)[0]

    assert "contextRenderSeq" in html
    assert "function isActiveContextRender" in html
    assert "const renderId = ++state.contextRenderSeq" in render_fn
    assert "return renderContextAnchors(renderId)" in render_fn
    assert "return renderContextNotes(renderId)" in render_fn
    assert "return renderContextErrors(renderId)" in render_fn
    assert "return renderContextSettings(renderId)" in render_fn
    assert "return renderContextGraph(renderId)" in render_fn
    assert "renderContextMemory" not in render_fn
    assert "if (!isActiveContextRender(renderId, 'graph')) return;" in graph_fn
    assert graph_fn.index("await Promise.all") < graph_fn.index("if (!isActiveContextRender(renderId, 'graph')) return;")
    assert "if (!isActiveContextRender(renderId, 'anchors')) return;" in anchors_fn
    assert "if (!isActiveContextRender(renderId, 'notes')) return;" in notes_fn
    assert "if (!isActiveContextRender(renderId, 'errors')) return;" in errors_fn
    assert "if (!isActiveContextRender(renderId, 'settings')) return;" in settings_fn


def test_mobile_context_tab_click_shows_immediate_shell_before_async_render():
    html = mobile_html()
    shell_fn = html.split("function renderContextImmediateShell", 1)[1].split("async function renderLearningContext", 1)[0]
    tab_handler = html.split("$$('[data-context-tab]').forEach", 1)[1].split("$('#graph-editor-close')", 1)[0]

    assert "function renderContextImmediateShell" in html
    assert "context-graph-body" in shell_fn
    assert "renderContextImmediateShell(state.contextTab)" in tab_handler
    assert tab_handler.index("renderContextImmediateShell(state.contextTab)") < tab_handler.index("await renderLearningContext()")


def test_mobile_context_image_import_creates_source_anchor():
    html = mobile_html()
    image_import_fn = html.split("async function importAnchorImages", 1)[1].split("function sourcePreviewText", 1)[0]

    assert "async function addImageExtractAsSourceAnchor" in html
    helper = html.split("async function addImageExtractAsSourceAnchor", 1)[1].split("async function importAnchorImages", 1)[0]
    assert "row = await uploadImageExtract(file)" in image_import_fn
    assert "await addImageExtractAsSourceAnchor(file, row)" in image_import_fn
    assert "await addLocalAnchor('source'" in helper
    assert "source_type: 'image'" in helper
    assert "source_image_id: row.image_id" in helper
    assert "source_detected_kps: row.detected_kps || []" in helper
    assert "图片资料" in helper

def test_mobile_session_row_swipe_sets_presence_and_long_press_has_management_menu():
    html = mobile_html()
    popover = html.split('id="session-card-popover"', 1)[1].split("</div>", 1)[0]
    card_fn = html.split("const sessionCardHtml =", 1)[1].split("const pinnedCards =", 1)[0]
    home_events = html.split("home.querySelectorAll('[data-session-open]')", 1)[1].split("refreshIcons();", 1)[0]
    handler = html.split("async function handleSessionSwipeAction", 1)[1].split("async function openSessionWindow", 1)[0]
    proactive_fn = html.split("async function maybeRunProactiveTurn", 1)[1].split("const CHAT_IMAGE_MAX_EDGE", 1)[0]

    assert 'data-session-swipe-action="sleep"' in card_fn
    assert 'data-session-swipe-action="online"' in card_fn
    assert 'data-session-swipe-action="offline"' in card_fn
    assert 'data-session-swipe-action="pin"' not in card_fn
    assert 'data-session-swipe-action="delete"' not in card_fn
    assert 'data-session-swipe-action="rename"' not in card_fn
    assert 'data-session-action="pin"' in popover
    assert 'data-session-action="delete"' in popover
    assert 'data-session-action="rename"' in popover
    assert 'data-session-action="export"' in popover
    assert 'data-session-action="preset-export"' not in popover
    assert 'data-session-action="avatar"' not in popover
    assert 'data-session-action="avatar-clear"' not in popover
    assert "#session-card-popover" in html
    assert "#session-card-popover button span" in html
    assert "text-overflow: ellipsis;" in html
    assert "pop.style.right" in home_events
    assert "pop.style.width = 'auto'" in home_events
    assert "const rightInset = Math.max" in home_events
    assert "Math.max(156, Math.min(360, viewportWidth - margin * 2))" in home_events
    assert "function sessionProactiveMode" in html
    assert "function sessionStatusBadgeHtml" in html
    assert "setSessionProactiveMode(sid, action)" in handler
    assert "sessionStatusBadgeHtml(s, 'list')" in card_fn
    assert "sessionStatusBadgeHtml(s, 'header')" in html
    assert "const mode = sessionProactiveMode(session, cfg)" in proactive_fn
    assert "ENGINE.run_proactive_turn(state.sid, mode)" in proactive_fn
    assert "session.proactive_last_at = Date.now()" in proactive_fn
    assert "touchAction = 'pan-y'" in home_events
    assert "session-swipe-open" in home_events
    assert "handleSessionSwipeAction" in home_events
    assert "pop.classList.add('hidden');" in home_events
    assert "pop.style.left = '-9999px';" in home_events
    assert "pop.style.left = `${Math.round(viewportLeft + margin)}px`" in home_events
    assert "pop.style.right = `${Math.round(rightInset)}px`" in home_events
    assert "viewportBottom - popRect.height - margin" in home_events
    assert "pop.style.setProperty('--popover-arrow-x'" in home_events
    assert "confirm('删除该会话及所有数据？')" in handler
    assert "deleteSessionById(sid)" in html
    assert "async function buildSessionExportPayload(sid=state.sid)" in html
    assert "shareExportPayload(() => buildSessionExportPayload(sid))" in html


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


def test_mobile_theme_cards_clip_long_labels_on_small_screens():
    html = mobile_html()
    theme_css = html.split(".theme-grid", 1)[1].split(".native-config-select", 1)[0]

    assert ".theme-choice {\n    min-width: 0;" in theme_css
    assert ".theme-choice-title {\n    width: 100%;" in theme_css
    assert ".theme-choice-detail {\n    width: 100%;" in theme_css
    assert "min-width: 0;" in theme_css
    assert "max-width: 100%;" in theme_css
    assert "text-overflow: ellipsis;" in theme_css


def test_mobile_chat_background_gradients_do_not_tile():
    html = mobile_html()
    chat_rule = html.split("#chat {", 1)[1].split("#chat > *", 1)[0]

    assert "background-image: var(--grain-overlay), var(--chat-slant-overlay), var(--chat-gradient);" in chat_rule
    assert "background-size: var(--grain-size), 260px 100%, 100% 100%, 100% 100%, 100% 100%;" in chat_rule
    assert "background-repeat: repeat, repeat, no-repeat, no-repeat, no-repeat;" in chat_rule


def test_mobile_chat_background_has_subtle_white_diagonal_lines_without_horizontal_stripes():
    html = mobile_html()
    root_theme = html.split(":root {", 1)[1].split(":root.theme-warm", 1)[0]
    slant_overlay = re.search(r"--chat-slant-overlay:\s*([^;]+);", root_theme).group(1)

    assert "repeating-linear-gradient(108deg" in slant_overlay
    assert "rgba(236,244,225,.040)" in slant_overlay
    assert "linear-gradient(0deg" not in slant_overlay


def test_mobile_chat_background_uses_top_glow_to_bottom_depth_without_stripes():
    html = mobile_html()
    theme_blocks = [
        html.split(":root {", 1)[1].split(":root.theme-warm", 1)[0],
        html.split(":root.theme-warm", 1)[1].split(":root.theme-berry", 1)[0],
        html.split(":root.theme-berry", 1)[1].split(":root.theme-midnight", 1)[0],
        html.split(":root.theme-midnight", 1)[1].split(":root.theme-ember", 1)[0],
        html.split(":root.theme-ember", 1)[1].split(":root.theme-ocean", 1)[0],
        html.split(":root.theme-ocean", 1)[1].split("html, body", 1)[0],
    ]

    for block in theme_blocks:
        chat_gradient = re.search(r"--chat-gradient:\s*([^;]+);", block).group(1)
        assert "radial-gradient(" in chat_gradient
        assert "linear-gradient(180deg" in chat_gradient
        assert "linear-gradient(0deg" not in chat_gradient
        assert "repeating-linear-gradient(" not in chat_gradient


def test_mobile_default_chat_background_has_visible_top_glow_and_bottom_depth():
    html = mobile_html()
    root_theme = html.split(":root {", 1)[1].split(":root.theme-warm", 1)[0]
    chat_gradient = re.search(r"--chat-gradient:\s*([^;]+);", root_theme).group(1)

    assert "--chat-bg: #071008;" in root_theme
    assert "rgba(236,244,225,.48)" in chat_gradient
    assert "rgba(133,156,132,.32)" in chat_gradient
    assert "linear-gradient(180deg, #60705f 0%, #2b392d 45%, #071008 100%)" in chat_gradient


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
    assert "rawSettings.image_retention_days" not in html
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
    assert "生成状态" in streaming_fn
    assert "思考链" not in streaming_fn
    assert "可公开推理旁白" in streaming_fn
    assert "thinking..." in streaming_fn
    assert "data-thinking-monologue" in streaming_fn
    assert "thinking-monologue live hidden" in streaming_fn
    assert ".streaming-thinking-panel .thinking-monologue" in html
    assert "思考链" in summary_fn
    assert "可公开推理旁白" in summary_fn
    assert "function publicThinkingSentence" in html
    assert "function appendThinkingNarration" in html
    assert "function tickThinkingNarration" in html
    assert "function resetThinkingNarration" in html
    assert "const STREAM_RENDER_INTERVAL_MS = 80;" in html
    assert "const streamingRenderState = {" in html
    assert "function renderStreamingBubbleNow" in html
    assert "function flushStreamingBubbleRender" in html
    assert "thinkingNarrationState.visible = thinkingNarrationState.target" in html
    assert "setTimeout(tickThinkingNarration" not in html
    assert "function pauseStreamingThinking" in html
    assert "const THINKING_CHAIN_OPEN_KEY = 'rt-mobile-thinking-chain-open';" in html
    assert "function thinkingChainOpen" in html
    assert "function setThinkingChainOpen" in html
    assert "function bindThinkingPreference" in html
    assert "${thinkingChainOpen() ? 'open' : ''}" not in streaming_fn
    assert 'details class="thinking-panel streaming-thinking-panel text-[11px] text-neutral-500 mb-2">' in streaming_fn
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
    render_streaming_fn = html.split("function renderStreamingBubbleNow", 1)[1].split("function flushStreamingBubbleRender", 1)[0]
    flush_streaming_fn = html.split("function flushStreamingBubbleRender", 1)[1].split("function updateStreamingBubble", 1)[0]
    update_streaming_fn = html.split("function updateStreamingBubble", 1)[1].split("function pauseStreamingThinking", 1)[0]
    assert "thinkingChainOpen()" not in update_streaming_fn
    assert "details.open = false" in render_streaming_fn
    update_thinking_fn = html.split("function updateThinkingStage", 1)[1].split("function resetStreamingRenderState", 1)[0]
    assert "container.querySelector('.streaming-thinking-panel')" in update_thinking_fn
    assert "details.open = false" in update_thinking_fn
    assert "safeChatHtml(htmlText)" in render_streaming_fn
    assert "renderStreamingBubbleNow(text)" in flush_streaming_fn
    assert "STREAM_RENDER_INTERVAL_MS" in update_streaming_fn
    assert "setTimeout(flushStreamingBubbleRender" in update_streaming_fn
    pause_streaming_fn = html.split("function pauseStreamingThinking", 1)[1].split("function finalizeStreamingBubble", 1)[0]
    assert "flushStreamingBubbleRender();" in pause_streaming_fn
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

    for name in ["后台回复", "后台生成", "自由回复", "模型自由回复", "师生角色定位"]:
        assert name in html
    assert "GRAPH_NON_LEARNING_KP_PATTERNS" in html
    assert "!isLogicalGraphKp(kp)" in normalize_action_fn
    assert "if (!isLogicalGraphKp(kp)) return;" in upsert_mastery_fn
    assert "masteries.filter(m => isLogicalGraphKp(m.kp || m.knowledge_point))" in build_graph_fn


def test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields():
    html = mobile_html()
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]
    assert "function graphSheetCompactHtml" in html
    compact_region = html.split("function graphSheetCompactHtml", 1)[1].split("function graphSheetActionButtonsHtml", 1)[0]

    assert "nodeType:'kp'" in build_graph_fn
    assert "nodeType:'latent'" in build_graph_fn
    assert "nodeType:'note'" in build_graph_fn
    assert "nodeType:'source'" in build_graph_fn
    assert "nodeType:'section'" in build_graph_fn
    assert "nodeType:'insight'" not in build_graph_fn
    assert "kind:'memory'" not in build_graph_fn
    assert "data-graph-kp-main-stuck" in compact_region
    assert "data-graph-structure-reason" in compact_region
    assert "data-graph-context-coverage" in compact_region
    assert "graphNodeSheetTemplate(node)" in compact_region
def test_mobile_graph_canvas_uses_focus_subset_but_detail_keeps_full_dataset():
    html = mobile_html()
    context_graph_fn = html.split("async function renderContextGraph", 1)[1].split("async function renderContextAnchors", 1)[0]
    insights_fn = html.split("async function renderInsights", 1)[1].split("// --- Settings ---", 1)[0]

    assert "setActiveGraphDataset(nodes, links);" in context_graph_fn
    assert "const focused = buildFocusedGraphData(nodes, links, { centerKey: state.graphSelected });" in context_graph_fn
    assert "ForceGraph.setData(focused.nodes, focused.links);" in context_graph_fn
    assert "graphFormationStateHtml(nodes, links, { context: 'session', focus: focused })" in context_graph_fn

    assert "setActiveGraphDataset(allNodes, allLinks);" in insights_fn
    assert "const focused = graphFullDataset(allNodes, allLinks);" in insights_fn
    assert "buildFocusedGraphData(allNodes, allLinks" not in insights_fn
    assert "ForceGraph.setData(focused.nodes, focused.links);" in insights_fn
    assert "graphFormationStateHtml(allNodes, allLinks, { context: 'global', focus: focused })" in insights_fn


def test_mobile_chat_note_graph_nodes_use_sticky_note_template():
    html = mobile_html()
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function graphLinkEndpointKey", 1)[0]
    sheet_template_fn = html.split("function graphNodeSheetTemplate", 1)[1].split("function graphNodeLightPath", 1)[0]
    compact_region = html.split("function graphChatNoteCompactHtml", 1)[1].split("function graphKnowledgeCompactHtml", 1)[0]
    report_region = html.split("function graphChatNoteReportHtml", 1)[1].split("function graphKnowledgeReportHtml", 1)[0]

    assert "anchors.filter(a => a.kind === 'chat_note')" in build_graph_fn
    assert "nodeType:'chat_note'" in build_graph_fn
    assert "kind:'chat_note'" in build_graph_fn
    assert "type === 'chat_note'" in sheet_template_fn
    assert "return 'chat-note'" in sheet_template_fn
    assert "闲聊便签" in compact_region
    assert "归入大纲" in compact_region
    assert "围绕它聊" in compact_region
    assert "查看原话" in compact_region
    assert "为什么记下它" in report_region
    assert "可能放到哪里" in report_region
    assert "原话" in report_region
    assert "可以怎么用" in report_region
    assert "待接入学习" not in compact_region
    assert "证据不足" not in compact_region
    assert "graph-node-score" not in compact_region


def test_mobile_global_graph_has_selected_session_completion_modal_shell():
    html = mobile_html()
    insights_fn = html.split("async function renderInsights", 1)[1].split("// --- Settings ---", 1)[0]
    populated_actions_region = insights_fn.split("const focused = graphFullDataset(allNodes, allLinks);", 1)[1]
    modal_region = html.split('id="graph-completion-modal"', 1)[1].split("<!--", 1)[0]
    actions_css = html.split("#insights-actions", 1)[1].split("}", 1)[0]

    assert 'data-graph-completion-open' in insights_fn
    assert "整理会话线索" in insights_fn
    assert "actDiv.classList.remove('hidden')" in insights_fn
    assert "actDiv.classList.add('hidden')" in insights_fn
    assert "position: absolute" in actions_css
    assert "z-index" in actions_css
    assert "$$('[data-graph-completion-open]').forEach(btn => btn.onclick = openGraphCompletionModal);\n  refreshIcons();" in populated_actions_region
    assert 'id="graph-completion-modal"' in html
    assert "function openGraphCompletionModal" in html
    assert "function closeGraphCompletionModal" in html
    assert "function renderGraphCompletionSessionPicker" in html
    assert "function renderGraphCompletionPreview" in html
    assert "data-graph-completion-step=\"sessions\"" in modal_region
    assert "data-graph-completion-step=\"preview\"" in modal_region
    assert "预览线索" in modal_region
    assert "保存到图谱" in modal_region
    assert "取消" in modal_region


def test_mobile_graph_completion_preview_groups_and_confirm_flow_are_wired():
    html = mobile_html()
    preview_fn = html.split("function renderGraphCompletionPreview", 1)[1].split("async function renderInsights", 1)[0]
    controls_fn = html.split("function bindGraphCompletionModalControls", 1)[1].split("async function openGraphCompletionModal", 1)[0]

    assert "function graphCompletionPreviewGroupHtml" in html
    assert "将新增的学习节点" in preview_fn
    assert "将更新的已有学习节点" in preview_fn
    assert "将补充的子节点 / 关系" in preview_fn
    assert "将新增的闲聊便签" in preview_fn
    assert "疑似重复，准备合并" in preview_fn
    assert "保存到图谱" in html
    assert "buildSelectedSessionGraphCompletionPreview(Array.from(state.graphCompletionSelectedSids))" in controls_fn
    assert "applySelectedSessionGraphCompletionPreview(state.graphCompletionPreview)" in controls_fn
    assert "await renderInsights()" in controls_fn
    assert "closeGraphCompletionModal()" in controls_fn
    assert "DB.add(" not in controls_fn
    assert "DB.put(" not in controls_fn


def test_mobile_graph_completion_modal_operations_are_tokenized_and_close_does_not_unlock_busy():
    html = mobile_html()
    state_block = html.split("graphCompletionOpen: false,", 1)[1].split("essaySourceMessage: null,", 1)[0]
    controls_fn = html.split("function bindGraphCompletionModalControls", 1)[1].split("async function openGraphCompletionModal", 1)[0]
    close_fn = html.split("function closeGraphCompletionModal()", 1)[1].split("function renderGraphCompletionModal()", 1)[0]

    assert "graphCompletionOperationId" in state_block
    assert "graphCompletionActiveOperationId" in state_block
    assert "state.graphCompletionBusy = false" not in close_fn
    assert "state.graphCompletionOperationId += 1;" in close_fn
    assert controls_fn.count("const opId = ++state.graphCompletionOperationId") >= 2
    assert "state.graphCompletionActiveOperationId = opId;" in controls_fn
    assert "const preview = await buildSelectedSessionGraphCompletionPreview(Array.from(state.graphCompletionSelectedSids));" in controls_fn
    assert "state.graphCompletionPreview = preview;" in controls_fn
    assert "if (opId !== state.graphCompletionOperationId || !state.graphCompletionOpen) return;" in controls_fn
    assert controls_fn.index("if (opId !== state.graphCompletionOperationId || !state.graphCompletionOpen) return;") < controls_fn.index("state.graphCompletionPreview = preview;")
    assert "if (opId === state.graphCompletionOperationId && state.graphCompletionOpen) {" in controls_fn
    assert "finally" in controls_fn
    assert "if (state.graphCompletionActiveOperationId === opId)" in controls_fn
    assert "state.graphCompletionBusy = false;" in controls_fn


def test_mobile_graph_completion_modal_runtime_helpers_cross_script_boundary():
    html = mobile_html()
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)
    preview_script_index = next(i for i, script in enumerate(scripts) if "function renderGraphCompletionPreview" in script)
    modal_script_index = next(i for i, script in enumerate(scripts) if "function renderGraphCompletionModal" in script)
    if preview_script_index == modal_script_index:
        return

    preview_script = scripts[preview_script_index]
    engine_return = preview_script.index("return { create_session")
    for export_line in [
        "window.buildSelectedSessionGraphCompletionPreview = buildSelectedSessionGraphCompletionPreview;",
        "window.applySelectedSessionGraphCompletionPreview = applySelectedSessionGraphCompletionPreview;",
        "window.renderGraphCompletionPreview = renderGraphCompletionPreview;",
    ]:
        assert export_line in preview_script
        assert preview_script.index(export_line) < engine_return
