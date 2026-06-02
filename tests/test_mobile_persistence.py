from __future__ import annotations

import re
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


def test_mobile_llm_keeps_local_api_snapshot_for_local_first_routing():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LLM_LOCAL_CONFIG_KEY" in html
    assert "saveLocalApiConfigLocal(next)" in html
    assert "DB.kvSet('llm_local_config', next)" in html
    assert "restoreLocalApiConfig" in html
    assert "selectLocalFirstLlmConfig(saved, localApi)" in html
    assert "const active = selectLocalFirstLlmConfig(next, localApi)" in html


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
    assert "build_system_prompt(session, anchors, masteries, summary_text, sourceContext, kgContextText)" in html


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


def test_mobile_graph_organizes_chat_turns_into_learning_digest_nodes():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function buildKpMemoryDigests" in html
    assert "nodeType:'insight'" in html
    assert "insightType:'error'" in html
    assert "insightType:'evidence'" in html
    assert "insightType:'next_step'" in html
    assert "chatMessageIds: digest.chatMessageIds" in html
    assert "content:msg.content" not in html
    assert "nodeType: count%5===0?'support':'memory'" not in html


def test_mobile_graph_sheet_shows_structured_learning_digest_before_raw_records():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function buildKpConversationDigest" in html
    assert "学习整理" in html
    assert "历史错因" in html
    assert "证据摘要" in html
    assert "可回顾原始对话" in html
    assert "summaryBullets.push(c)" not in html
    assert "exampleBullets.push(c)" not in html


def test_mobile_kg_indexeddb_stores_and_crud_helpers_are_present():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "const DB_VERSION = 3;" in html
    assert "'kg_nodes'" in html
    assert "'kg_edges'" in html
    assert "createObjectStore('kg_nodes', { keyPath: 'id', autoIncrement: true })" in html
    assert "createIndex('sid_kind_name', ['sid', 'kind', 'name'], { unique: true })" in html
    assert "createObjectStore('kg_edges', { keyPath: 'id', autoIncrement: true })" in html
    assert "createIndex('source_id', 'source_id', { unique: false })" in html
    assert "createIndex('target_id', 'target_id', { unique: false })" in html
    assert "kg_nodes: await all('kg_nodes')" in html
    assert "kg_edges: await all('kg_edges')" in html
    assert "DB.delBySid('kg_edges', sid)" in html
    assert "DB.delBySid('kg_nodes', sid)" in html
    for fn in [
        "upsert_kg_node",
        "get_kg_node",
        "find_kg_node",
        "list_kg_nodes",
        "invalidate_kg_node",
        "upsert_kg_edge",
        "get_kg_edge",
        "list_kg_edges",
        "invalidate_kg_edge",
        "supersede_kg_edge",
    ]:
        assert f"async function {fn}" in html


def test_mobile_kg_gate_and_rule_extractor_are_mounted_on_turns():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "kg_extraction_enabled: true" in html
    assert "const KG_DEFAULT_BLACKLIST = [" in html
    for word in ["身份证", "手机号", "银行卡", "隐私"]:
        assert word in html
    assert "function should_extract(settings, userInput, evaluation, action)" in html
    assert "function kgHasLearningEvidence(evaluation)" in html
    assert "async function extract_from_turn(sid, { evaluation={}, action={}, episodeId=null }={})" in html
    assert "async function maybe_extract_kg_from_turn(session, sid, userInput, evaluation, action, episodeId)" in html
    assert "await supersede_kg_edge(sid, userNode.id, concept.id, REL_LEARNING" in html
    assert "REL_MASTERED" in html
    assert "REL_ERROR_ON" in html
    assert "REL_MISUNDERSTOOD" in html
    assert html.count("await maybe_extract_kg_from_turn(") >= 3
    assert "kg extraction failed" in html


def test_mobile_kg_context_retrieval_is_injected_into_system_prompt():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "async function retrieve_kg_context(sid, currentKp, { includePendingReview=true }={})" in html
    assert "function format_for_prompt(ctx)" in html
    assert "# 知识图谱上下文" in html
    assert "## 相关/前置概念" in html
    assert "## 用户历史错因" in html
    assert "## 用户曾误解" in html
    assert "## 用户学习偏好" in html
    assert "## 挂起待复习" in html
    assert "kgContextText=''" in html
    assert "if (kgContextText) s += `\\n\\n${kgContextText}`;" in html
    assert "async function buildKgContextTextForPrompt(sid, session, currentKp)" in html
    assert html.count("await buildKgContextTextForPrompt(") >= 3


def test_mobile_prereq_gap_detection_is_injected_into_kg_prompt():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "const PREREQ_MASTERY_THRESHOLD = 0.5;" in html
    assert "async function detect_prereq_gaps(sid, currentKp, masteryThreshold=PREREQ_MASTERY_THRESHOLD)" in html
    assert "ctx.prereq_gaps = await detect_prereq_gaps(sid, kp);" in html
    assert "ctx.prereq_gaps" in html
    assert "## 前置缺口" in html
    assert "老师，要学这个我是不是得先搞懂" in html
    assert "edge.target_id !== currentNode.id" in html
    assert "Number(m.mastery_score || 0) / 100" in html


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


def test_mobile_chat_image_attachment_sends_direct_multimodal_turn():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'id="chat-image-file" type="file" accept="image/*"' in html
    assert 'id="chat-image-pick"' in html
    assert 'id="image-draft-card"' in html
    assert 'id="image-draft-text"' not in html
    assert 'id="image-draft-send"' not in html
    assert "const CHAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024" in html
    assert "async function compressChatImageFile(file)" in html
    assert "file.size > CHAT_IMAGE_MAX_BYTES" in html
    assert "canvas.toDataURL('image/jpeg', CHAT_IMAGE_JPEG_QUALITY)" in html
    assert "function supports_image_messages()" in html
    assert "function chatImageAttachmentFromDraft" in html
    assert "function contentWithImageAttachments" in html
    assert "currentInputAttachments" in html
    assert "const activeImageDraft = opts.imageDraft || chatImageDraft || null;" in html
    assert "if (activeImageDraft) closeImageDraft();" in html
    assert "图片已附加，发送后由多模态模型直接读取" in html

    image_flow = html[html.index("const CHAT_IMAGE_MAX_EDGE"):html.index("let chatSendHandledByPointer")]
    assert "recognizeChatImageDraft" not in image_flow
    assert "LLM.chat_json(system, [{ role:'user', content }]" not in image_flow
    assert "setChatInputValue(text, true, { focus: true });\n  sendMessage();" not in image_flow
    assert "$('#image-draft-text')" not in image_flow
    assert "请手动填写图片文字" not in image_flow
    assert "ENGINE.run_turn" not in image_flow
    assert "/api/sessions/${encodeURIComponent(state.sid)}/images" not in image_flow


def test_mobile_chat_image_messages_support_anthropic_and_openai_payloads():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    llm_src = html.split("const LLM = (() => {", 1)[1].split("})();", 1)[0]
    supports_fn = llm_src.split("function supports_image_messages", 1)[1].split("return {", 1)[0]
    anthropic_payload = html.split("function anthropicImageSource", 1)[1].split("function extractAnthropicText", 1)[0]

    assert "supports_vision()" in supports_fn
    assert "c.api_type !== 'anthropic'" not in supports_fn
    assert "type:'image'" in anthropic_payload
    assert "source:{ type:'base64'" in anthropic_payload
    assert "supports_image_messages" in llm_src.rsplit("return {", 1)[1].split("};", 1)[0]


def test_mobile_chat_strips_model_thinking_from_visible_replies():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    strip_fn = html.split("function stripModelThinkingText", 1)[1].split("function renderRichText", 1)[0]
    stream_fn = html.split("if (opts.stream)", 1)[1].split("// Non-streaming path", 1)[0]
    non_stream_fn = html.split("// Non-streaming path", 1)[1].split("async function run_proactive_turn", 1)[0]

    assert "Thinking Process" in strip_fn
    assert "<think>" in strip_fn
    assert "stripModelThinkingText(streamObj.fullText() || currentBubbleText)" in stream_fn
    assert "stripModelThinkingText(raw.reply||'')" in non_stream_fn
    assert "content.innerHTML = safeChatHtml(htmlText);" in html


def test_mobile_service_worker_cache_key_is_not_changed_for_v4_image_card():
    sw = (ROOT / "static" / "app" / "sw.js").read_text(encoding="utf-8")

    assert "rt-mobile-v0.19.1-test.1-39-pwa-profile-long-text-only" in sw
    assert "v4-image-card" not in sw
    assert "rt-mobile-v0.19.1-test.1-40" not in sw


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
    assert "function stripModelThinkingText" in html
    assert "safeChatHtml(content) {\n  return renderRichText(stripModelThinkingText(content));" in html
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
    assert "sessionAvatarHtml" in html
    assert "fileToAvatarDataUrl" in html
    assert "avatar_image" in html
    assert "avatar_hidden" in html
    assert "data-avatar-sess" in html
    assert "data-avatar-hide" in html


def test_mobile_side_back_uses_in_app_navigation_history():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function navigateBackInApp" in html
    assert "function initAppHistory" in html
    assert "function syncAppHistory" in html
    assert "window.addEventListener('popstate'" in html
    assert "history.pushState" in html
    assert "history.replaceState" in html
    assert "window.__rtHandleNativeBack" in html
    assert "navigateBackInApp({ source: 'edge-swipe' })" in html
    assert "swipeStart.x < 18 && dx > 110" in html
    assert "appHistorySuppress" in html


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
    assert "思考链" in html
    assert "公开策略链" in html
    assert ".thinking-dots::after" in html
    assert "function updateThinkingStage" in html
    assert "onThinkingStage" in html
    assert "检索资料" in html
    assert "组织回复" in html
    assert "开始输出" in html


def test_mobile_offline_engine_schema_matches_v1_learning_fields():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "entry_status" in html
    assert "has_entry|no_entry|recall_decay" in html
    assert "student_role" in html
    assert "probing_student|clue_student|scaffold_student|confused_student|examiner|review_student" in html
    assert "evidence_for_mastery" in html
    assert "none|explanation|retrieval|transfer|delayed_retrieval|correction" in html
    assert "ask|probe|challenge|clue|scaffold_example|examiner_verify|emote|persuade|next|recap" in html
    assert "const allowed = ['ask', 'probe', 'challenge', 'clue', 'scaffold_example', 'examiner_verify', 'emote', 'persuade', 'next', 'recap', 'pending', 'error']" in html
    assert "normalizeEvidence" in html
    assert "EVIDENCE_SCORES" in html
    assert "delayed_retrieval:0.82" in html
    assert "correction:0.90" in html
    assert "async function upsert_mastery(sid, kp, correctness, depth, evidenceType='none', verificationStatus='none')" in html
    assert html.count("evidence_for_mastery?.type || 'none'") >= 3
    assert html.count("evidence_for_mastery?.status || 'none'") >= 3


def test_android_background_fallback_uses_v1_learning_schema():
    service = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "com" / "reversetutor" / "app" / "BackgroundLlmService.java").read_text(encoding="utf-8")

    assert 'evaluation.put("entry_status", "has_entry")' in service
    assert 'evaluation.put("evidence_for_mastery", evidence)' in service
    assert 'action.put("student_role", "probing_student")' in service


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
    assert 'data-lucide="ellipsis"' in html
    assert 'data-lucide="chevron-left"' in html
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
    assert "return queueForNextTurn({ notifyBusy: true });" in html
    assert "const batch = state.messageQueue.splice(0)" in html
    assert "await submitChatText(combinedText, { queuedUserMessages" in html
    assert "queued_user_message" in html
    assert "待处理" in html
    assert "处理中" in html


def test_mobile_opening_turn_is_skipped_once_user_has_started_talking():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "async function hasUserMessagesBeforeOpening" in html
    assert "if (await hasUserMessagesBeforeOpening(sid)) return { reply: '', action: { type: 'pending' }, skipped: true };" in html
    assert "if (await hasUserMessagesBeforeOpening(sid)) return { reply: '', action, skipped: true };" in html
    assert "if (result?.skipped) return;" in html
    assert "if (state.messageQueue.length) await processMessageQueue();" in html


def test_mobile_regular_sends_are_debounced_into_one_queued_turn():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "queueProcessing: false" in html
    assert "let queueProcessTimer = null;" in html
    assert "function scheduleMessageQueueProcessing" in html
    assert "clearTimeout(queueProcessTimer);" in html
    assert "state.queueProcessing = true;" in html
    assert "state.queueProcessing = false;" in html
    assert "return queueForNextTurn({ notifyBusy: true });" in html
    assert "await queueForNextTurn({ notifyBusy: pendingNative });" in html
    assert "scheduleMessageQueueProcessing();" in html
    assert "await submitChatText(txt);" not in html


def test_mobile_streaming_bubble_follows_newer_user_messages_and_shows_thinking_summary():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    streaming_fn = html.split("function getOrCreateStreamingBubble", 1)[1].split("function updateThinkingStage", 1)[0]
    queued_fn = html.split("function appendQueuedUserMessageBubble", 1)[1].split("function renderProcessSummary", 1)[0]
    build_messages_fn = html.split("function build_messages", 1)[1].split("function formatQuotedReplyContext", 1)[0]
    process_queue_fn = html.split("async function processMessageQueue", 1)[1].split("function renderQueueIndicator", 1)[0]
    native_queue_fn = html.split("async function tryQueueNativeTurnEarly", 1)[1].split("async function run_turn", 1)[0]
    run_turn_fn = html.split("async function run_turn", 1)[1].split("async function run_proactive_turn", 1)[0]

    assert "function moveStreamingBubbleToTail" in html
    assert "moveStreamingBubbleToTail();" in streaming_fn
    assert "moveStreamingBubbleToTail();" in queued_fn
    assert "appendQueuedUserMessageBubble(queuedMessage);" in html
    assert "if (meta.kind === 'queued_user_message')" in html
    assert "meta.queued_at || m.created_at || m.id || 0" in html
    assert "function build_messages(msgs, user_input, skip_until_id=0, opts={})" in html
    assert "const excludeIds = new Set((opts.exclude_ids || [])" in build_messages_fn
    assert ".filter(m => {" in build_messages_fn
    assert "if (excludeIds.has(Number(m.id))) return false;" in build_messages_fn
    assert "if (meta.kind === 'queued_user_message' && !meta.turn_input) return false;" in build_messages_fn
    assert "RECENT_PROMPT_MESSAGE_LIMIT = 12" in html
    assert "}).slice(-RECENT_PROMPT_MESSAGE_LIMIT);" in build_messages_fn
    assert "function formatCurrentInputInstruction" in html
    assert "最后一条 user 消息是用户本轮刚发送/合并后的最新输入" in html
    assert "不要把最后一条 user 消息当作历史总结" in html
    assert "const currentInputMessageIds = queuedUserMessages.map" in run_turn_fn
    assert "const promptUserInput = currentInputMessageIds.length ? effectiveUserInput : null;" in run_turn_fn
    assert "build_messages(msgs, promptUserInput, skip_id, { exclude_ids: currentInputMessageIds, current_input_attachments: currentInputAttachments })" in run_turn_fn
    assert "formatCurrentInputInstruction(promptUserInput)" in run_turn_fn
    assert "const currentInputMessageIds = turnMeta.currentInputMessageIds || [];" in native_queue_fn
    assert "build_messages(msgs, promptUserInput, skip_id, { exclude_ids: currentInputMessageIds, current_input_attachments: currentInputAttachments })" in native_queue_fn
    assert "formatCurrentInputInstruction(promptUserInput)" in native_queue_fn
    assert "logical_created_at: Date.now() + 86400000" not in html
    assert "logicalBase" not in html
    assert "const batch = state.messageQueue.splice(0)" in process_queue_fn
    assert "if (state.messageQueue.length > 0)" in process_queue_fn
    assert "scheduleMessageQueueProcessing(0)" in process_queue_fn
    assert "thinking..." in html
    assert "思考链" in html
    assert "公开策略链" in html
    assert ".thinking-dots::after" in html
    assert "@keyframes thinkingDots" in html
    assert "msg.content || msg.reasoning_content" not in html
    process_summary = html.split("function renderProcessSummary", 1)[1].split("function renderCitedSources", 1)[0]
    assert "<summary>本轮判断</summary>" not in process_summary


def test_mobile_graph_view_is_fullscreen_and_filters_process_nodes():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    insights_section = html.split('data-view="insights"', 1)[1].split("<!-- 设置 view -->", 1)[0]
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]
    digest_fn = html.split("function buildKpMemoryDigests", 1)[1].split("function cleanOutlineTitle", 1)[0]
    normalize_action_fn = html.split("function normalizeAction", 1)[1].split("function normalizeEvidence", 1)[0]
    upsert_mastery_fn = html.split("async function upsert_mastery", 1)[1].split("async function upsert_error_log", 1)[0]

    assert "insights-graph-page" in html
    assert "记忆图谱" not in insights_section
    assert "动作分布（近 12 轮）" not in insights_section
    assert "function isLogicalGraphKp" in html
    assert "GRAPH_PROCESS_KP_NAMES" in html
    for process_kp in ["后台回复", "后台生成", "自由回复", "模型自由回复", "后台生成中", "后台回复生成中"]:
        assert process_kp in html
    assert "!isLogicalGraphKp(kp)" in normalize_action_fn
    assert "if (!isLogicalGraphKp(kp)) return;" in upsert_mastery_fn
    assert "masteries.filter(m => isLogicalGraphKp(m.kp || m.knowledge_point))" in build_graph_fn
    assert "if (!isLogicalGraphKp(kp)) continue;" in digest_fn
    assert re.search(r'id="knowledge-graph" class="[^"]*knowledge-graph[^"]*knowledge-graph-fullscreen', html)
    assert re.search(r'id="context-knowledge-graph" class="[^"]*knowledge-graph[^"]*knowledge-graph-fullscreen', html)


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
