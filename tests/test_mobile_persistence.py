from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_llm_config_uses_native_preferences_for_long_term_storage():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "nativePreferences()" in html
    assert "saveLlmConfigNative" in html
    assert "loadLlmConfigNative" in html
    assert "saveLocalApiConfigNative" in html
    assert "loadLocalApiConfigNative" in html
    assert "Preferences.set" in html
    assert "Preferences.get" in html


def test_mobile_llm_keeps_local_api_snapshot_separate_from_trial_redeem():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LLM_LOCAL_CONFIG_KEY" in html
    assert "saveLocalApiConfigLocal(next)" in html
    assert "DB.kvSet('llm_local_config', next)" in html
    assert "restoreLocalApiConfig" in html
    assert "selectLocalFirstLlmConfig(saved, localApi)" in html
    assert "activeLocalApi = !isTrialProvider(cfg.provider)" in html


def test_android_webview_uses_native_ime_input_connection():
    config = (ROOT / "mobile" / "capacitor.config.json").read_text(encoding="utf-8")

    assert '"captureInput": false' in config
    assert '"captureInput": true' not in config


def test_chat_input_avoids_layout_mutation_during_chinese_ime_composition():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "if (chatInputComposing) delay = Math.max(delay, 260);" in html
    assert "if (chatInputComposing) return;" in html
    assert "field-sizing: content" not in html
    assert "height: 42px;" in html


def test_android_manifest_requests_notification_permission_only_for_background_llm():
    manifest = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "android.permission.POST_NOTIFICATIONS" in manifest
    assert 'android:name=".BackgroundLlmService"' in manifest


def test_mobile_insights_graph_keeps_minimum_canvas_and_slower_gestures():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "GRAPH_MIN_W" in html
    assert "GRAPH_MIN_H" in html
    assert "TOUCH_PAN_SPEED" in html
    assert "WHEEL_ZOOM_STEP" in html
    assert "Math.max(GRAPH_MIN_W" in html
    assert "dx > 110" in html
    assert "swipeStart.x < 18" in html


def test_mobile_insights_graph_includes_source_grounded_locked_nodes():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "extractSourceTopics" in html
    assert "nodeType:'source'" in html
    assert "nodeType:'latent'" in html
    assert "unlockedFromSource" in html
    assert "Glow is reserved for learned nodes" in html
    assert "buildGraphData(masteries, ai, anchors)" in html


def test_mobile_pdf_sources_are_retrieved_for_each_llm_turn():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "source_text: text" in html
    assert "retrieveSourceSnippets" in html
    assert "formatSourceContext" in html
    assert "当前问题命中的上传资料片段" in html
    assert "const sourceSnippets = retrieveSourceSnippets(anchors, user_input);" in html
    assert "const sourceContext = formatSourceContext(sourceSnippets, user_input, anchors);" in html
    assert "const sourceContext = formatSourceContext(sourceSnippets, effectiveUserInput, anchors);" in html
    assert "build_system_prompt(session, anchors, masteries, summary_text, sourceContext)" in html


def test_mobile_insights_graph_builds_document_outline_branches_from_full_source_text():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function graphSourceText" in html
    assert "String(a?.source_text || a?.content || '')" in html
    assert "function extractSourceOutline" in html
    assert "nodeType:'section'" in html
    assert "kind:'outline'" in html
    assert "extractSourceOutline(sources" in html


def test_mobile_new_session_can_optionally_import_documents_before_opening_turn():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'id="new-source-files"' in html
    assert 'id="new-source-files" type="file"' in html
    assert 'multiple class="hidden"' in html
    assert 'id="anchor-file" type="file"' in html
    assert 'id="anchor-file" type="file" accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm,.pptx,.epub,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/html,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/epub+zip" multiple' in html
    assert 'id="new-source-status"' in html
    assert "PDF、DOCX、TXT、Markdown、HTML、PPTX、EPUB" in html
    assert "PDF、DOCX、TXT、Markdown、HTML、PPTX、EPUB 等资料" in html
    assert "选择多个文件" in html
    assert "async function importAnchorFiles(files, opts={})" in html
    assert r"\.(pdf|docx|txt|md|markdown|html|htm|pptx?|epub)$" in html
    assert "const pendingSourceFiles = Array.from($('#new-source-files')?.files || []);" in html
    assert "await importAnchorFiles(pendingSourceFiles, { statusEl: $('#new-source-status'), render: false });" in html
    assert html.index("await importAnchorFiles(pendingSourceFiles") < html.index("await openingFor(s.id)")


def test_mobile_insights_graph_summarizes_branch_nodes_when_document_has_no_outline():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function graphSourceChunks" in html
    assert "function summarizeSourceBlock" in html
    assert "function synthesizeSourceOutline" in html
    assert "按内容概括" in html
    assert "graphSourceChunks(text, 1400, 120)" in html
    assert "synthesizeSourceOutline(text, sourceId, maxPerSource)" in html


def test_mobile_document_import_records_pdf_readability_diagnostics():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function diagnoseImportedSource" in html
    assert "function sourceNeedsOcr" in html
    assert "source_diagnostics: diagnostics" in html
    assert "pdf_empty_text" in html
    assert "需要视觉模型" in html


def test_mobile_unreadable_pdf_is_visible_in_prompt_and_graph():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "sourceReadabilityHint" in html
    assert "资料尚未真正读到正文" in html
    assert "nodeType:'diagnostic'" in html
    assert "kind:'diagnostic'" in html
    assert "待视觉模型" in html


def test_mobile_partial_visual_documents_still_build_text_graph():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function sourceHasVisualGaps" in html
    assert "if ((diagnostics.char_count || 0) > 0) return false;" in html
    assert "clean.length === 0" in html
    assert "partial_text_with_visual" in html
    assert "已先读取可提取文字并生成图谱" in html
    assert "图片内容保留为待视觉模型补读" in html
    assert "已先读取文字；图片内容待视觉模型补读" in html


def test_mobile_document_import_persists_temporal_source_memory():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function createSourceMemory" in html
    assert "source_memory: createSourceMemory" in html
    assert "schema: 'source_memory_v1'" in html
    assert "status:" in html
    assert "'outlined'" in html
    assert "valid_from" in html
    assert "episodes: [" in html


def test_mobile_source_memory_is_updated_lazily_when_chat_hits_a_node():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function recordSourceMemoryHit" in html
    assert "async function persistSourceMemoryHits" in html
    assert "const sourceSnippets = retrieveSourceSnippets(anchors, effectiveUserInput);" in html
    assert "await persistSourceMemoryHits(anchors, sourceSnippets, effectiveUserInput, userMessage ? [userMessage.id] : []);" in html
    assert "event: 'chat_hit'" in html
    assert "status = node.status === 'raw' ? 'outlined' : node.status" in html


def test_mobile_second_layer_expands_only_hit_source_memory_branches():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "async function expandSourceMemoryBranches" in html
    assert "normalizeBranchExpansion" in html
    assert "event: 'branch_expand'" in html
    assert "node.status = 'expanded'" in html
    assert "node.pending_expansion = false" in html
    assert "await expandSourceMemoryBranches(anchors, sourceSnippets, effectiveUserInput);" in html
    assert "最多分析 1 个命中的资料节点" in html


def test_mobile_graph_sheet_displays_saved_branch_expansion():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "memoryExpansion" in html
    assert "单支分析" in html
    assert "teacher_questions" in html
    assert "key_concepts" in html


def test_mobile_image_pdf_import_saves_preview_pages_for_vision_recovery():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "async function renderPdfPreviewPages" in html
    assert "source_pages: pdfResult?.pages || []" in html
    assert "has_visual_pages" in html
    assert "vision_page_count" in html
    assert "image/jpeg" in html
    assert "toDataURL" in html


def test_mobile_vision_model_can_expand_unreadable_pdf_diagnostic_node():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "supports_vision" in html
    assert "function sourceVisualPages" in html
    assert "visual_pages" in html
    assert "input_image" in html
    assert "node.type === 'diagnostic' && !LLM.supports_vision()" in html
    assert "image_url" in html
    assert "PDF 页面图片" in html


def test_mobile_visual_model_state_is_clear_and_old_docs_can_be_reprocessed():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'id="cfg-vision-hint"' in html
    assert "renderVisionCapabilityHint" in html
    assert "当前模型不支持视觉" in html
    assert "支持视觉" in html
    assert 'id="anchor-reprocess-file"' in html
    assert "data-reprocess-source" in html
    assert "replaceAnchorId" in html
    assert "重新处理" in html


def test_mobile_graph_nodes_show_human_readable_analysis_status():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function memoryStatusLabel" in html
    assert "已分析" in html
    assert "待分析" in html
    assert "待视觉模型" in html
    assert "分析中" in html


def test_mobile_renders_math_and_chemistry_as_readable_rich_text():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function renderRichText" in html
    assert "function renderMathExpression" in html
    assert "math-inline" in html
    assert "frac-line" in html
    assert "safeChatHtml(content) {\n  return renderRichText(content);" in html
    assert "renderRichText(m.content)" in html


def test_mobile_source_ui_uses_compact_cards_instead_of_raw_document_text():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function sourceAnchorCardHtml" in html
    assert "sourcePreviewText" in html
    assert "文档内容已保存为检索证据" in html
    assert "data-reprocess-source" in html
    assert "资料快照" in html
    assert "renderRichText(String(node.content).slice(0, 520))" not in html


def test_mobile_graph_topic_labels_are_cleaned_for_display():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function displaySourceTopicLabel" in html
    assert "looksLikeNoisyFormulaLabel" in html
    assert "内容片段" in html
    assert "label: displaySourceTopicLabel" in html


def test_mobile_source_nodes_preserve_user_title_over_model_renames():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function sourceNodeTitle" in html
    assert "user_title" in html
    assert "model_title" in html
    assert "用户命名" in html
    assert "模型建议" in html
    assert "model_title_suggestion" in html
    assert "sourceNodeTitle(node, i + 1)" in html


def test_mobile_graph_sheet_can_jump_to_chat_and_edit_source_node():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "data-graph-jump-chat" in html
    assert "data-graph-edit-node" in html
    assert "function jumpToGraphNodeChat" in html
    assert "function openGraphNodeEditor" in html
    assert "function saveGraphNodeEdit" in html
    assert "graph-source-node-editor" in html
    assert "chat_message_ids" in html


def test_mobile_chat_long_press_can_create_note_nodes_in_graph():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "data-message-id" in html
    assert "contextmenu" in html
    assert "function openEssayComposer" in html
    assert "function saveEssayNote" in html
    assert "kind:'note'" in html
    assert "nodeType:'note'" in html
    assert "随笔" in html


def test_mobile_header_without_session_does_not_reference_graph_node_state():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    refresh_header = html.split("async function refreshHeader()", 1)[1].split("// --- Chat ---", 1)[0]

    assert "node.nodeType" not in refresh_header
    assert "点 会话 新建你的第一个窗口" in refresh_header
    assert "会话列表" in refresh_header


def test_mobile_ui_uses_session_list_and_learning_context():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'id="session-home"' in html
    assert 'id="chat-thread"' in html
    assert 'id="learning-context-page"' in html
    assert 'id="learning-context-open"' in html
    assert 'id="learning-context-sheet"' not in html
    assert 'data-context-tab="graph"' in html
    assert 'data-context-tab="anchors"' in html
    assert 'data-context-tab="notes"' in html
    assert 'id="context-note-form"' not in html
    assert "data-context-edit-note" in html
    assert 'data-tab="anchors"' not in html
    assert "openSessionWindow" in html
    assert "renderSessionHome" in html
    assert 'id="session-search-input"' in html
    assert "SESSION_PINNED_KEY" in html
    assert "togglePinnedSession" in html
    assert "compositionstart" in html


def test_mobile_chat_input_preserves_caret_and_handles_keyboard_layout():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function resizeChatInput" in html
    assert "document.activeElement === el" in html
    assert "return tag === 'textarea' || tag === 'input' || el.isContentEditable" in html
    assert "function scheduleKeyboardLayout" in html
    assert "scheduleKeyboardLayout(260)" in html
    assert "viewportShrink > 80" in html
    assert "interactive-widget=resizes-content" in html
    assert "field-sizing: content" not in html
    assert "height: 42px;" in html
    assert "if (chatInputComposing) return;" in html
    assert "compositionstart" in html
    assert "compositionend" in html
    assert "function syncKeyboardLayout" in html
    assert "body.keyboard-open .bottom-nav" in html
    assert "--keyboard-bottom" in html
    assert "padding-bottom: calc(0.75rem + var(--keyboard-bottom))" in html
    assert "scroll-padding-bottom: calc(86px + var(--keyboard-bottom))" in html
    assert "function keepChatTailVisible" in html
    assert "function isChatNearBottom" in html
    assert "opts.wasNearBottom" in html
    assert "const shouldFollowChat = state.currentTab === 'chat'" in html
    assert "keepChatTailVisible(80, { wasNearBottom: shouldFollowChat })" in html
    assert "keepChatTailVisible(0, { wasNearBottom })" in html
    assert "addEventListener('pointerdown'" in html
    assert "addEventListener('pointerup'" in html
    assert "chatSendHandledByPointer" in html
    assert "e.pointerType !== 'mouse'" in html
    assert "document.activeElement?.id === 'chat-input'" in html
    assert "e.preventDefault()" in html
    assert "overflow: hidden;" in html
    assert ".bottom-nav { flex-shrink: 0;" in html
    assert "overscroll-behavior: contain;" in html


def test_mobile_chat_handles_topic_drift_fuzzy_retrieval_and_visible_thinking_status():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "话题偏离与关联性判断" in html
    assert "强相关、弱相关、暂时无关" in html
    assert "先解决用户此刻的问题" in html
    assert "不要硬拽用户回“中点”" in html
    assert "function sourceTermVariants" in html
    assert "function fuzzySourceTermScore" in html
    assert "function sourceEditDistanceLimited" in html
    assert "function isDefinitionLikeQuery" in html
    assert "joinedLatin" in html
    assert "v.length >= 4 ? 10 : 4" in html
    assert "broadIntent && idx === 0" in html
    assert "资料里暂时没检到直接定义" in html
    assert "思考模式（状态）" in html
    assert "function updateThinkingStage" in html
    assert "onThinkingStage" in html
    assert "检索资料" in html
    assert "组织回复" in html
    assert "开始输出" in html


def test_mobile_failed_chat_message_can_be_retried_or_restored_to_input():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "retry_text: String(msg.content || effectiveUserInput || '')" in html
    assert "data-retry-message" in html
    assert "data-edit-message" in html
    assert "async function retryFailedMessage" in html
    assert "async function restoreFailedMessageDraft" in html
    assert "发送失败：" in html
    assert "record.id = id" in html


def test_mobile_message_action_sheet_supports_quote_essay_rollback_and_delete():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "selectedActionMessage: null" in html
    assert "quotedMessage: null" in html
    assert 'id="quote-preview"' in html
    assert 'id="message-action-popover"' in html
    assert "function openMessageActionSheet" in html
    assert "function positionMessageActionPopover" in html
    assert "message-action-popover" in html
    assert "transition: opacity .14s ease, transform .14s ease, visibility .14s ease;" in html
    assert "pointer-events: none;" in html
    assert ".message-action-popover.hidden { display: none; }" not in html
    assert ".message-action-active {" in html
    assert "@keyframes messagePressPop" in html
    assert 'data-message-id="${m.id}"' in html
    assert 'class="flex ${isUser?\'justify-end\':\'justify-start\'}" id="msg-${m.id}"' in html
    assert "const targetEl = anchorEl.closest?.('[data-message-id]') || anchorEl" in html
    assert "const viewportWidth = Math.min(" in html
    assert "screen.width || Infinity" in html
    assert "const viewportRight = viewportLeft + viewportWidth" in html
    assert "viewportRight - popRect.width - margin" in html
    assert "clampMessageActionPopover()" in html
    assert "requestAnimationFrame(clampMessageActionPopover)" in html
    assert "const belowSpace = viewportBottom - rect.bottom - margin - gap" in html
    assert "let side = aboveSpace >= popRect.height || aboveSpace >= belowSpace ? 'above' : 'below'" in html
    assert "rect.top - gap - popRect.height" in html
    assert "pop.style.setProperty('--popover-arrow-x'" in html
    assert ".message-action-popover::after" in html
    assert "setMessageActionAnchor(anchorEl" in html
    assert "clearMessageActionAnchor()" in html
    assert "positionMessageActionPopover(message, anchorEl" in html
    assert "document.addEventListener('pointerdown'" in html
    assert "if (e.target.closest('[data-message-id]')) return;" not in html
    assert "function quoteMessageForReply" in html
    quote_fn = html.split("function quoteMessageForReply", 1)[1].split("async function cleanupMessageMemory", 1)[0]
    assert ".focus()" not in quote_fn
    assert "function rollbackFromMessage" in html
    assert "function deleteSingleMessage" in html
    assert "function cleanupMessageMemory" in html
    assert "formatQuotedReplyContext" in html
    assert "quoted_message_id" in html
    assert "source_message_id" in html
    assert "note_message_id" in html
    assert "引用" in html
    assert "随笔" in html
    assert "回档" in html
    assert "删除" in html
    assert "openChoiceSheet({\n    title: '消息操作'" not in html


def test_mobile_uses_lucide_icons_and_custom_proactive_segments():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "lucide" in html
    assert "function refreshIcons" in html
    assert 'data-lucide="message-circle"' in html
    assert 'data-lucide="network"' in html
    assert 'data-lucide="menu"' in html
    assert 'data-lucide="plus"' in html
    assert 'data-lucide="share-2"' in html
    assert 'data-lucide="folder-down"' in html
    assert 'data-lucide="upload"' in html
    assert 'data-lucide="trash-2"' in html
    assert 'data-lucide="smartphone"' in html
    assert 'data-lucide="check-circle-2"' in html
    assert 'data-lucide="rotate-ccw"' in html
    assert 'data-lucide="pencil"' in html
    assert 'aria-label="删除会话"' in html
    assert 'aria-label="删除锚点"' in html
    assert "测试中…" in html
    assert "联通 OK" in html
    assert "🔌 测试中" not in html
    assert "✅ 联通 OK" not in html
    assert "❌ ${r.error" not in html
    assert 'id="proactive-mode-segments"' in html
    assert "data-proactive-mode" in html
    assert "native-config-select" in html


def test_mobile_queued_user_messages_are_visible_and_reused_for_next_turn():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "async function queue_pending_user_message" in html
    assert "kind: 'queued_user_message'" in html
    assert "已进入对话，等待上一条回复完成" in html
    assert "existingUserMessages" in html
    assert "queuedUserMessages" in html
    assert "await hasPendingNativeBackgroundTurn(state.sid)" in html
    assert "return queueForNextTurn();" in html
    assert "const batch = state.messageQueue.splice(0)" in html
    assert "await submitChatText(combinedText, { queuedUserMessages" in html
    assert "queued_user_message" in html
    assert "待处理" in html
    assert "处理中" in html


def test_mobile_import_accepts_reader_friendly_document_formats():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert ".txt" in html
    assert ".md" in html
    assert ".markdown" in html
    assert ".html" in html
    assert ".htm" in html
    assert ".pptx" in html
    assert ".epub" in html
    assert "application/vnd.openxmlformats-officedocument.presentationml.presentation" in html
    assert "application/epub+zip" in html


def test_mobile_import_routes_each_supported_format_to_a_parser():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function sourceTypeFromFile" in html
    assert "async function extractPlainText" in html
    assert "async function extractMarkdownText" in html
    assert "async function extractHtmlText" in html
    assert "async function extractPptxText" in html
    assert "async function extractEpubText" in html
    assert "await extractSourceByType(file, sourceType)" in html
    assert "sourceType === 'pptx'" in html
    assert "sourceType === 'epub'" in html


def test_mobile_zip_based_formats_use_jszip_and_preserve_structure_for_graph():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "jszip" in html.lower()
    assert "window.JSZip" in html
    assert "ppt/slides/slide" in html
    assert "META-INF/container.xml" in html
    assert "extractTextFromHtmlDocument" in html
    assert "source_metadata" in html
