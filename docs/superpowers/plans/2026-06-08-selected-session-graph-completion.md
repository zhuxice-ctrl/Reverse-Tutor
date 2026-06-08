# Selected Session Graph Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global graph tool that lets the user select historical sessions, preview generated learning nodes / chat notes / relationship supplements, then merge confirmed results into the graph without deleting old data.

**Architecture:** Keep the existing single-file mobile app structure in `static/app/index.html`. Add a graph-completion modal, deterministic preview builders over existing `sessions`, `messages`, `mastery`, `anchors`, `kg_nodes`, and `kg_edges`, and merge-only apply helpers that overwrite current system-generated fields but append/dedupe evidence and relations. Use existing `upsert_mastery`, `upsert_kg_node`, `upsert_kg_edge`, and `extractChatNoteCandidates` rather than creating a separate background data model.

**Tech Stack:** Static HTML/JS mobile app, IndexedDB wrapper `DB`, existing graph renderer, pytest string-structure tests, Node syntax check, Capacitor Android build.

---

## File Map

- Modify: `static/app/index.html`
  - Add global graph completion modal markup near the existing graph sheet/modal markup.
  - Add state fields under the existing `state` object for selected sessions, scan preview, and modal step.
  - Add session picker rendering, preview rendering, scan helpers, merge helpers, and event handlers.
  - Wire the `整理会话线索` button into `renderInsights()`.
- Modify: `tests/test_mobile_product_experience.py`
  - Add structure tests for the global graph button, modal two-step flow, preview groups, and no direct writes before confirmation.
- Modify: `tests/test_mobile_persistence.py`
  - Add structure tests for deterministic scan helpers, merge-only apply helpers, dedupe behavior, no delete calls, and current default overwrite of system-generated fields.
- Generated during verification only: `mobile/www`, `mobile/android/app/src/main/assets/public`
  - Produced by `npm run sync`; commit only if tracked source changes are intentional.

---

### Task 1: Add Global Graph Completion Entry And Modal Shell

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_mobile_product_experience.py`:

```python
def test_mobile_global_graph_has_selected_session_completion_modal_shell():
    html = mobile_html()
    insights_fn = html.split("async function renderInsights", 1)[1].split("// --- Settings ---", 1)[0]
    modal_region = html.split('id="graph-completion-modal"', 1)[1].split("<!--", 1)[0]

    assert 'data-graph-completion-open' in insights_fn
    assert "整理会话线索" in insights_fn
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_global_graph_has_selected_session_completion_modal_shell -q
```

Expected: FAIL because `graph-completion-modal` and `openGraphCompletionModal` do not exist.

- [ ] **Step 3: Add modal markup and state**

In `static/app/index.html`, add modal markup near the existing sheet/modal markup:

```html
<div id="graph-completion-modal" class="fixed inset-0 z-50 hidden graph-completion-modal">
  <div class="absolute inset-0 bg-black/70" data-graph-completion-close></div>
  <section class="absolute left-3 right-3 bottom-3 max-h-[82vh] overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950 shadow-2xl flex flex-col">
    <header class="flex items-start justify-between gap-3 p-3 border-b border-neutral-800">
      <div>
        <div class="text-sm font-semibold">整理会话线索</div>
        <div class="text-[11px] text-neutral-500">只扫描你勾选的历史会话，先预览，确认后再写入图谱。</div>
      </div>
      <button type="button" class="icon-only text-neutral-400" data-graph-completion-close aria-label="关闭"><i data-lucide="x"></i></button>
    </header>
    <div class="graph-completion-body flex-1 overflow-y-auto p-3">
      <div data-graph-completion-step="sessions"></div>
      <div data-graph-completion-step="preview" class="hidden"></div>
    </div>
    <footer class="p-3 border-t border-neutral-800 flex gap-2 justify-end">
      <button type="button" class="px-3 py-2 rounded border border-neutral-700 text-xs" data-graph-completion-close>取消</button>
      <button type="button" class="px-3 py-2 rounded border border-neutral-700 text-xs hidden" data-graph-completion-back>返回选择</button>
      <button type="button" class="px-3 py-2 rounded bg-neutral-100 text-neutral-950 text-xs font-semibold" data-graph-completion-preview>预览线索</button>
      <button type="button" class="px-3 py-2 rounded bg-emerald-400 text-neutral-950 text-xs font-semibold hidden" data-graph-completion-save>保存到图谱</button>
    </footer>
  </section>
</div>
```

In the existing `state` object, add:

```js
graphCompletionOpen: false,
graphCompletionStep: 'sessions',
graphCompletionSessions: [],
graphCompletionSelectedSids: new Set(),
graphCompletionPreview: null,
graphCompletionBusy: false,
```

If the state object cannot safely store a `Set` literal because of serialization assumptions, initialize it after `state`:

```js
state.graphCompletionSelectedSids = state.graphCompletionSelectedSids || new Set();
```

- [ ] **Step 4: Add modal open/close and initial render functions**

Add these functions before `async function renderInsights()`. Keep `bindGraphCompletionModalControls()` before `openGraphCompletionModal()` so later tests can split the region deterministically:

```js
function graphCompletionSessionTimeLabel(value) {
  const time = Number(value || 0);
  if (!time) return '时间未知';
  try {
    return new Date(time).toLocaleString();
  } catch (_) {
    return String(time);
  }
}

function bindGraphCompletionModalControls() {
  $$('[data-graph-completion-close]').forEach(el => el.addEventListener('click', closeGraphCompletionModal));
  $('[data-graph-completion-back]')?.addEventListener('click', () => {
    state.graphCompletionStep = 'sessions';
    renderGraphCompletionModal();
  });
  $('#graph-completion-modal')?.addEventListener('change', e => {
    const box = e.target.closest?.('[data-graph-completion-session]');
    if (!box) return;
    if (!(state.graphCompletionSelectedSids instanceof Set)) state.graphCompletionSelectedSids = new Set();
    const sid = String(box.dataset.graphCompletionSession || '');
    if (!sid) return;
    if (box.checked) state.graphCompletionSelectedSids.add(sid);
    else state.graphCompletionSelectedSids.delete(sid);
  });
}

async function openGraphCompletionModal() {
  state.graphCompletionOpen = true;
  state.graphCompletionStep = 'sessions';
  state.graphCompletionPreview = null;
  state.graphCompletionSessions = (await DB.all('sessions')).sort((a,b)=>(b.updated_at||0)-(a.updated_at||0));
  if (!(state.graphCompletionSelectedSids instanceof Set)) state.graphCompletionSelectedSids = new Set();
  renderGraphCompletionModal();
  $('#graph-completion-modal')?.classList.remove('hidden');
  refreshIcons();
}

function closeGraphCompletionModal() {
  state.graphCompletionOpen = false;
  state.graphCompletionBusy = false;
  $('#graph-completion-modal')?.classList.add('hidden');
}

function renderGraphCompletionModal() {
  const modal = $('#graph-completion-modal');
  if (!modal) return;
  const sessionsStep = modal.querySelector('[data-graph-completion-step="sessions"]');
  const previewStep = modal.querySelector('[data-graph-completion-step="preview"]');
  if (sessionsStep) sessionsStep.innerHTML = renderGraphCompletionSessionPicker(state.graphCompletionSessions || []);
  if (previewStep) previewStep.innerHTML = renderGraphCompletionPreview(state.graphCompletionPreview);
  sessionsStep?.classList.toggle('hidden', state.graphCompletionStep !== 'sessions');
  previewStep?.classList.toggle('hidden', state.graphCompletionStep !== 'preview');
  modal.querySelector('[data-graph-completion-preview]')?.classList.toggle('hidden', state.graphCompletionStep !== 'sessions');
  modal.querySelector('[data-graph-completion-save]')?.classList.toggle('hidden', state.graphCompletionStep !== 'preview');
  modal.querySelector('[data-graph-completion-back]')?.classList.toggle('hidden', state.graphCompletionStep !== 'preview');
}

function renderGraphCompletionSessionPicker(sessions=[]) {
  if (!sessions.length) return '<div class="text-xs text-neutral-500 text-center py-8">暂无历史会话。</div>';
  const selected = state.graphCompletionSelectedSids instanceof Set ? state.graphCompletionSelectedSids : new Set();
  return `<div class="space-y-2">${sessions.map(session => `
    <label class="graph-completion-session-row flex gap-2 items-start rounded border border-neutral-800 bg-neutral-900 p-2 text-xs">
      <input type="checkbox" class="mt-0.5" data-graph-completion-session="${esc(String(session.id))}" ${selected.has(String(session.id)) ? 'checked' : ''}>
      <span class="min-w-0 flex-1">
        <span class="block font-semibold truncate">${esc(session.title || '未命名会话')}</span>
        <span class="block text-[11px] text-neutral-500">${esc(graphCompletionSessionTimeLabel(session.updated_at || session.created_at || Date.now()))}</span>
      </span>
    </label>
  `).join('')}</div>`;
}

function renderGraphCompletionPreview(preview) {
  if (!preview) return '<div class="text-xs text-neutral-500 text-center py-8">选择会话后先预览线索。</div>';
  return '<div class="text-xs text-neutral-400">已建立预览容器，扫描结果渲染在后续任务接入。</div>';
}
```

- [ ] **Step 5: Wire the button into global graph actions**

Inside `renderInsights()`, add the button before `actDiv.innerHTML` is assigned or in the global graph actions area:

```js
actDiv.innerHTML = `
  <button type="button" data-graph-completion-open class="w-full text-xs px-3 py-2 rounded border border-neutral-700 active:bg-neutral-800 text-left flex items-center gap-2">
    <i class="button-icon" data-lucide="scan-search"></i><span>整理会话线索</span>
  </button>
  <div class="flex flex-wrap gap-1 pt-2">${Object.entries(actCount).map(([k,v]) =>
    `<span class="pill pill-${k}">${k} ${v}/${total}</span>`).join('') || '<span class="text-xs text-neutral-500">暂无动作分布</span>'}</div>
`;
$$('[data-graph-completion-open]').forEach(btn => btn.onclick = openGraphCompletionModal);
```

If this replaces existing action pills, keep the action pills inside the new wrapper as shown so existing signal is preserved.

- [ ] **Step 6: Call modal control binding during startup**

Call `bindGraphCompletionModalControls()` from the same startup/binding area that initializes other global event handlers:

```js
bindGraphCompletionModalControls();
```

- [ ] **Step 7: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_global_graph_has_selected_session_completion_modal_shell -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add static/app/index.html tests/test_mobile_product_experience.py
git commit -m "feat: add graph completion modal shell"
```

---

### Task 2: Build Preview Candidates Without Writing Data

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_mobile_persistence.py`:

```python
def test_mobile_selected_session_graph_completion_builds_preview_without_writes():
    html = mobile_html()
    preview_region = html.split("async function buildSelectedSessionGraphCompletionPreview", 1)[1].split("async function applySelectedSessionGraphCompletionPreview", 1)[0]

    assert "function graphCompletionMessagePairs" in html
    assert "function graphCompletionCandidateKey" in html
    assert "function graphCompletionClassifyPair" in html
    assert "async function buildSelectedSessionGraphCompletionPreview" in html
    assert "extractChatNoteCandidates({" in preview_region
    assert "type: 'learning_node'" in preview_region
    assert "type: 'chat_note'" in preview_region
    assert "type: 'relationship'" in preview_region
    assert "existingMasteries" in preview_region
    assert "existingChatNotes" in preview_region
    assert "existingKgNodes" in preview_region
    assert "DB.add(" not in preview_region
    assert "DB.put(" not in preview_region
    assert "upsert_mastery(" not in preview_region
    assert "upsert_kg_node(" not in preview_region
    assert "upsert_kg_edge(" not in preview_region
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_selected_session_graph_completion_builds_preview_without_writes -q
```

Expected: FAIL because `buildSelectedSessionGraphCompletionPreview` does not exist.

- [ ] **Step 3: Add candidate helper functions**

Add these helpers after `persistChatNoteAnchors()` and before `inferTurnRoute()`:

```js
function graphCompletionText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function graphCompletionCandidateKey(type, title, outline='') {
  return [type, normalizeGraphTopic(outline), normalizeGraphTopic(title)].filter(Boolean).join('::');
}

function graphCompletionMessagePairs(messages=[]) {
  const sorted = [...(messages || [])].sort(compareConversationMessages);
  const pairs = [];
  for (let i = 0; i < sorted.length; i++) {
    const user = sorted[i];
    if (user.role !== 'user') continue;
    const assistant = sorted.slice(i + 1).find(m => m.role === 'assistant');
    pairs.push({ user, assistant: assistant || null });
  }
  return pairs;
}

function graphCompletionHasLearningBehavior(userText='', assistantText='', action={}, evaluation={}) {
  const text = `${userText}\n${assistantText}`;
  const actType = String(action?.type || '');
  if (['ask', 'probe', 'challenge', 'examiner_verify', 'scaffold_example', 'practice', 'recap'].includes(actType)) return true;
  if (graphCompletionText(action?.knowledge_point) && kgHasLearningEvidence(evaluation || {})) return true;
  return /(解释|讲解|练习|做题|纠错|复述|追问|举例|例题|推导|证明|为什么|怎么理解|卡点|错因|迁移|应用)/.test(text);
}

function graphCompletionOutlineFor(title, session=null) {
  return chatNoteOutlineFor(title, session);
}
```

- [ ] **Step 4: Add pair classifier**

Add:

```js
function graphCompletionClassifyPair(pair, session=null) {
  const userText = graphCompletionText(pair?.user?.content || '');
  const assistantText = graphCompletionText(pair?.assistant?.content || '');
  const meta = pair?.assistant?.meta || {};
  const action = meta.action || {};
  const evaluation = meta.evaluation || {};
  const candidates = [];
  const kp = graphCompletionText(action.knowledge_point || '');

  if (kp && isLogicalGraphKp(kp) && graphCompletionHasLearningBehavior(userText, assistantText, action, evaluation)) {
    candidates.push({
      type: 'learning_node',
      title: kp,
      outline: graphCompletionOutlineFor(kp, session),
      summary: graphPanelPreviewText(evaluation.status || assistantText || userText, ''),
      stuck: graphCompletionText(evaluation.misconception || evaluation.error_pattern || ''),
      nextStep: graphCompletionText((evaluation.next_steps || [])[0] || ''),
      keywords: graphUniqueClean([kp, ...(action.related_kps || [])], 8),
      evidenceIds: [pair?.user?.id, pair?.assistant?.id].filter(Boolean),
      evidenceText: graphPanelPreviewText(userText || assistantText, ''),
      correctness: Number(evaluation.correctness || 0) || 0,
      depth: Number(evaluation.depth || 0) || 0,
      evidenceType: evaluation.evidence_for_mastery?.type || 'none',
      verificationStatus: evaluation.evidence_for_mastery?.status || 'none',
    });
    for (const related of action.related_kps || []) {
      const cleanRelated = graphCompletionText(related);
      if (cleanRelated && isLogicalGraphKp(cleanRelated)) {
        candidates.push({
          type: 'relationship',
          sourceTitle: kp,
          targetTitle: cleanRelated,
          relation: 'related',
          weight: 1.2,
          evidenceIds: [pair?.user?.id, pair?.assistant?.id].filter(Boolean),
        });
      }
    }
    return candidates;
  }

  for (const note of extractChatNoteCandidates({ userInput: userText, reply: assistantText, session })) {
    candidates.push({
      type: 'chat_note',
      title: note.title,
      body: note.body,
      outline: note.outline,
      quote: note.quote,
      keywords: note.keywords || [],
      evidenceIds: [pair?.user?.id, pair?.assistant?.id].filter(Boolean),
    });
  }
  return candidates;
}
```

- [ ] **Step 5: Add preview builder**

Add:

```js
async function buildSelectedSessionGraphCompletionPreview(sids=[]) {
  const selectedSids = Array.from(new Set((sids || []).map(String).filter(Boolean)));
  const preview = {
    sessionCount: selectedSids.length,
    learningNodes: [],
    updatedLearningNodes: [],
    relationships: [],
    chatNotes: [],
    duplicateMerges: [],
    skipped: [],
  };
  const seen = new Set();

  for (const sid of selectedSids) {
    const session = await DB.get('sessions', sid);
    if (!session) continue;
    const messages = (await DB.bySid('messages', sid)).sort(compareConversationMessages);
    const existingMasteries = await DB.bySid('mastery', sid);
    const existingChatNotes = (await DB.bySid('anchors', sid)).filter(a => a.kind === 'chat_note');
    const existingKgNodes = await DB.bySid('kg_nodes', sid);
    const pairs = graphCompletionMessagePairs(messages);

    for (const pair of pairs) {
      const candidates = graphCompletionClassifyPair(pair, session);
      if (!candidates.length) {
        const text = graphCompletionText(pair?.user?.content || '');
        if (text) preview.skipped.push({ sid, sessionTitle: session.title || '', reason: 'no_learning_signal', text: graphPanelPreviewText(text, '') });
        continue;
      }
      for (const candidate of candidates) {
        const key = graphCompletionCandidateKey(candidate.type, candidate.title || `${candidate.sourceTitle}->${candidate.targetTitle}`, candidate.outline || candidate.relation || '');
        const scopedKey = `${sid}::${key}`;
        if (seen.has(scopedKey)) continue;
        seen.add(scopedKey);
        const base = { ...candidate, sid, sessionTitle: session.title || '', candidateKey: key };
        if (candidate.type === 'learning_node') {
          const existing = existingMasteries.find(m => normalizeGraphTopic(m.kp || m.knowledge_point) === normalizeGraphTopic(candidate.title));
          const kgExisting = existingKgNodes.find(n => n.kind === 'concept' && normalizeGraphTopic(n.name) === normalizeGraphTopic(candidate.title));
          if (existing || kgExisting) {
            preview.updatedLearningNodes.push({ ...base, mergeTarget: existing?.kp || kgExisting?.name || candidate.title });
            preview.duplicateMerges.push({ ...base, mergeTarget: existing?.kp || kgExisting?.name || candidate.title });
          } else {
            preview.learningNodes.push(base);
          }
        } else if (candidate.type === 'chat_note') {
          const existing = existingChatNotes.find(a => normalizeGraphTopic(a.chat_note_title || a.content) === normalizeGraphTopic(candidate.title));
          if (existing) preview.duplicateMerges.push({ ...base, mergeTarget: existing.chat_note_title || existing.content || candidate.title });
          else preview.chatNotes.push(base);
        } else if (candidate.type === 'relationship') {
          preview.relationships.push(base);
        }
      }
    }
  }
  return preview;
}
```

Immediately after it, add a stub for Task 3 so the test split boundary exists:

```js
async function applySelectedSessionGraphCompletionPreview(preview=null) {
  void preview;
  return { learningNodes: 0, chatNotes: 0, relationships: 0, merges: 0 };
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_selected_session_graph_completion_builds_preview_without_writes -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: preview selected session graph completion"
```

---

### Task 3: Apply Preview With Merge-Only Writes

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_mobile_persistence.py`:

```python
def test_mobile_selected_session_graph_completion_applies_merge_only_writes():
    html = mobile_html()
    apply_region = html.split("async function applySelectedSessionGraphCompletionPreview", 1)[1].split("function renderGraphCompletionPreview", 1)[0]

    assert "async function mergeGraphCompletionLearningNode" in html
    assert "async function mergeGraphCompletionChatNote" in html
    assert "async function mergeGraphCompletionRelationship" in html
    assert "applySelectedSessionGraphCompletionPreview" in html
    assert "upsert_mastery(candidate.sid, candidate.title" in apply_region
    assert "upsert_kg_node(candidate.sid, 'concept', candidate.title" in apply_region
    assert "upsert_kg_edge(candidate.sid" in apply_region
    assert "kind: 'chat_note'" in apply_region
    assert "DB.put('anchors', existing)" in apply_region
    assert "DB.add('anchors'" in apply_region
    assert "graph_completion_evidence_ids" in apply_region
    assert "graph_completion_last_merged_at" in apply_region
    assert "user_edited_at" in apply_region
    assert "user_locked_fields" in apply_region
    assert "DB.del(" not in apply_region
    assert "invalidate_kg_node(" not in apply_region
    assert "invalidate_kg_edge(" not in apply_region
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_selected_session_graph_completion_applies_merge_only_writes -q
```

Expected: FAIL because merge helpers do not exist.

- [ ] **Step 3: Add evidence merge helper**

Add before `applySelectedSessionGraphCompletionPreview()`:

```js
function graphCompletionMergeIds(existing=[], incoming=[]) {
  return Array.from(new Set([...(existing || []), ...(incoming || [])].filter(Boolean).map(Number).filter(Number.isFinite)));
}

function graphCompletionNow() {
  return Date.now();
}
```

- [ ] **Step 4: Add learning-node merge helper**

Add:

```js
async function mergeGraphCompletionLearningNode(candidate) {
  if (!candidate?.sid || !candidate?.title || !isLogicalGraphKp(candidate.title)) return null;
  await upsert_mastery(
    candidate.sid,
    candidate.title,
    Number(candidate.correctness || 0) || 0,
    Number(candidate.depth || 0) || 0,
    candidate.evidenceType || 'none',
    candidate.verificationStatus || 'none'
  );
  const concept = await upsert_kg_node(candidate.sid, 'concept', candidate.title, {
    properties: {
      outline: candidate.outline || '',
      summary: candidate.summary || '',
      stuck: candidate.stuck || '',
      next_step: candidate.nextStep || '',
      keywords: candidate.keywords || [],
      graph_completion_evidence_ids: candidate.evidenceIds || [],
      graph_completion_last_merged_at: graphCompletionNow(),
      user_edited_at: null,
      user_locked_fields: [],
    },
    episodeId: (candidate.evidenceIds || [])[1] || (candidate.evidenceIds || [])[0] || null,
  });
  return concept;
}
```

- [ ] **Step 5: Add chat-note merge helper**

Add:

```js
async function mergeGraphCompletionChatNote(candidate) {
  if (!candidate?.sid || !candidate?.title) return null;
  const now = graphCompletionNow();
  const existingRows = (await DB.bySid('anchors', candidate.sid)).filter(a => a.kind === 'chat_note');
  const existing = existingRows.find(a => normalizeGraphTopic(a.chat_note_title || a.content) === normalizeGraphTopic(candidate.title));
  if (existing) {
    existing.content = candidate.body || existing.content || candidate.title;
    existing.chat_note_title = candidate.title;
    existing.chat_note_body = candidate.body || existing.chat_note_body || existing.content || '';
    existing.chat_note_outline = candidate.outline || existing.chat_note_outline || '';
    existing.chat_note_quote = candidate.quote || existing.chat_note_quote || '';
    existing.chat_note_keywords = graphUniqueClean([...(existing.chat_note_keywords || []), ...(candidate.keywords || [])], 12);
    existing.graph_completion_evidence_ids = graphCompletionMergeIds(existing.graph_completion_evidence_ids || [], candidate.evidenceIds || []);
    existing.graph_completion_last_merged_at = now;
    existing.updated_at = now;
    await DB.put('anchors', existing);
    return existing;
  }
  const row = {
    sid: candidate.sid,
    kind: 'chat_note',
    content: candidate.body || candidate.title,
    weight: 1.25,
    created_at: now,
    chat_note_title: candidate.title,
    chat_note_body: candidate.body || '',
    chat_note_outline: candidate.outline || '',
    chat_note_quote: candidate.quote || '',
    chat_note_keywords: candidate.keywords || [],
    graph_completion_evidence_ids: graphCompletionMergeIds([], candidate.evidenceIds || []),
    graph_completion_last_merged_at: now,
    user_edited_at: null,
    user_locked_fields: [],
  };
  row.id = await DB.add('anchors', row);
  return row;
}
```

- [ ] **Step 6: Add relationship merge helper**

Add:

```js
async function mergeGraphCompletionRelationship(candidate) {
  if (!candidate?.sid || !candidate?.sourceTitle || !candidate?.targetTitle) return null;
  const source = await upsert_kg_node(candidate.sid, 'concept', candidate.sourceTitle, {
    properties: { graph_completion_last_merged_at: graphCompletionNow() },
    episodeId: (candidate.evidenceIds || [])[0] || null,
  });
  const target = await upsert_kg_node(candidate.sid, 'concept', candidate.targetTitle, {
    properties: { graph_completion_last_merged_at: graphCompletionNow() },
    episodeId: (candidate.evidenceIds || [])[1] || (candidate.evidenceIds || [])[0] || null,
  });
  if (!source || !target) return null;
  return upsert_kg_edge(candidate.sid, source.id, target.id, candidate.relation || 'related', {
    weight: Number(candidate.weight || 1.0) || 1.0,
    properties: {
      graph_completion_evidence_ids: candidate.evidenceIds || [],
      graph_completion_last_merged_at: graphCompletionNow(),
    },
    episodeId: (candidate.evidenceIds || [])[1] || (candidate.evidenceIds || [])[0] || null,
  });
}
```

- [ ] **Step 7: Replace apply stub**

Replace the Task 2 stub with:

```js
async function applySelectedSessionGraphCompletionPreview(preview=null) {
  const result = { learningNodes: 0, chatNotes: 0, relationships: 0, merges: 0 };
  const learningCandidates = [
    ...(preview?.learningNodes || []),
    ...(preview?.updatedLearningNodes || []),
    ...(preview?.duplicateMerges || []).filter(c => c.type === 'learning_node'),
  ];
  const chatNoteCandidates = [
    ...(preview?.chatNotes || []),
    ...(preview?.duplicateMerges || []).filter(c => c.type === 'chat_note'),
  ];
  for (const candidate of learningCandidates) {
    const merged = await mergeGraphCompletionLearningNode(candidate);
    if (merged) {
      result.learningNodes += 1;
      if (candidate.mergeTarget) result.merges += 1;
    }
  }
  for (const candidate of chatNoteCandidates) {
    const merged = await mergeGraphCompletionChatNote(candidate);
    if (merged) {
      result.chatNotes += 1;
      if (candidate.mergeTarget) result.merges += 1;
    }
  }
  for (const candidate of preview?.relationships || []) {
    const merged = await mergeGraphCompletionRelationship(candidate);
    if (merged) result.relationships += 1;
  }
  return result;
}
```

- [ ] **Step 8: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_selected_session_graph_completion_applies_merge_only_writes -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: merge selected session graph completion"
```

---

### Task 4: Render Preview Groups And Connect Modal Actions

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_mobile_product_experience.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_graph_completion_preview_groups_and_confirm_flow_are_wired -q
```

Expected: FAIL because preview groups and action handlers are not wired.

- [ ] **Step 3: Add preview rendering helpers**

Place before `function renderGraphCompletionPreview(preview)`:

```js
function graphCompletionPreviewCardHtml(item) {
  const title = item.title || item.sourceTitle || '未命名线索';
  const meta = graphUniqueClean([
    item.sessionTitle,
    item.outline,
    item.mergeTarget ? `合并到：${item.mergeTarget}` : '',
    item.relation ? `关系：${graphLinkKindLabel(item.relation)}` : '',
  ], 4).join(' · ');
  const body = item.summary || item.body || item.quote || item.evidenceText || item.targetTitle || '';
  return `<article class="rounded border border-neutral-800 bg-neutral-900 p-2 text-xs">
    <div class="font-semibold text-neutral-100">${esc(title)}</div>
    ${meta ? `<div class="mt-0.5 text-[11px] text-neutral-500">${esc(meta)}</div>` : ''}
    ${body ? `<div class="mt-1 leading-relaxed text-neutral-300">${renderRichText(graphPanelPreviewText(body, ''))}</div>` : ''}
  </article>`;
}

function graphCompletionPreviewGroupHtml(title, items=[]) {
  if (!items.length) return '';
  return `<section class="space-y-2">
    <div class="flex items-center justify-between">
      <h3 class="text-xs font-semibold text-neutral-300">${esc(title)}</h3>
      <span class="text-[11px] text-neutral-500">${items.length} 条</span>
    </div>
    <div class="space-y-2">${items.map(graphCompletionPreviewCardHtml).join('')}</div>
  </section>`;
}
```

- [ ] **Step 4: Replace initial preview renderer**

Replace `renderGraphCompletionPreview(preview)` with:

```js
function renderGraphCompletionPreview(preview) {
  if (!preview) return '<div class="text-xs text-neutral-500 text-center py-8">选择会话后先预览线索。</div>';
  const groups = [
    graphCompletionPreviewGroupHtml('将新增的学习节点', preview.learningNodes || []),
    graphCompletionPreviewGroupHtml('将更新的已有学习节点', preview.updatedLearningNodes || []),
    graphCompletionPreviewGroupHtml('将补充的子节点 / 关系', preview.relationships || []),
    graphCompletionPreviewGroupHtml('将新增的闲聊便签', preview.chatNotes || []),
    graphCompletionPreviewGroupHtml('疑似重复，准备合并', preview.duplicateMerges || []),
  ].filter(Boolean).join('');
  const skipped = preview.skipped?.length
    ? `<details class="text-xs text-neutral-500"><summary>已跳过 ${preview.skipped.length} 条无学习含义片段</summary><div class="mt-2 space-y-1">${preview.skipped.slice(0, 8).map(x => `<div>${esc(x.text || x.reason || '')}</div>`).join('')}</div></details>`
    : '';
  return `<div class="space-y-4">
    ${groups || '<div class="text-xs text-neutral-500 text-center py-8">没有发现可写入的学习线索。</div>'}
    ${skipped}
  </div>`;
}
```

- [ ] **Step 5: Wire preview/save buttons**

Update `bindGraphCompletionModalControls()` to include:

```js
$('[data-graph-completion-preview]')?.addEventListener('click', async () => {
  if (state.graphCompletionBusy) return;
  if (!(state.graphCompletionSelectedSids instanceof Set) || !state.graphCompletionSelectedSids.size) {
    toast('请先勾选至少一个会话');
    return;
  }
  state.graphCompletionBusy = true;
  renderGraphCompletionModal();
  try {
    state.graphCompletionPreview = await buildSelectedSessionGraphCompletionPreview(Array.from(state.graphCompletionSelectedSids));
    state.graphCompletionStep = 'preview';
    renderGraphCompletionModal();
  } finally {
    state.graphCompletionBusy = false;
  }
});

$('[data-graph-completion-save]')?.addEventListener('click', async () => {
  if (state.graphCompletionBusy || !state.graphCompletionPreview) return;
  state.graphCompletionBusy = true;
  try {
    const result = await applySelectedSessionGraphCompletionPreview(state.graphCompletionPreview);
    toast(`已保存：学习节点 ${result.learningNodes}，便签 ${result.chatNotes}，关系 ${result.relationships}`);
    closeGraphCompletionModal();
    await renderInsights();
  } finally {
    state.graphCompletionBusy = false;
  }
});
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_graph_completion_preview_groups_and_confirm_flow_are_wired -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add static/app/index.html tests/test_mobile_product_experience.py
git commit -m "feat: preview and save selected graph completion"
```

---

### Task 5: Verify Regression, Build APK, And Device Smoke Test

**Files:**
- Modify: none unless verification exposes a required fix.

- [ ] **Step 1: Run mobile regression tests**

Run:

```bash
pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run JS syntax check**

Run:

```bash
node -e "const fs=require('fs');const html=fs.readFileSync('static/app/index.html','utf8');const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);for(const [i,s] of scripts.entries()){new Function(s);console.log('script '+(i+1)+' ok')}"
```

Expected: all script blocks print `ok`.

- [ ] **Step 3: Sync and build APK**

Run:

```bash
cd mobile
npm run sync
cd android
.\gradlew.bat assembleRelease
cd ..\..
```

Expected: Capacitor sync succeeds and Gradle prints `BUILD SUCCESSFUL`.

- [ ] **Step 4: Install and launch**

Run:

```bash
adb devices
adb install -r mobile\android\app\build\outputs\apk\release\app-release.apk
adb shell monkey -p com.reversetutor.app -c android.intent.category.LAUNCHER 1
```

Expected: connected device is listed, install prints `Success`, app launches.

- [ ] **Step 5: Device-side smoke test through WebView CDP**

Forward the WebView socket:

```bash
adb shell pidof com.reversetutor.app
adb shell cat /proc/net/unix | Select-String webview_devtools
adb forward tcp:9222 localabstract:webview_devtools_remote_<PID>
```

Run this CDP check with `<PID>` already forwarded:

```bash
@'
const pages = await (await fetch('http://localhost:9222/json')).json();
const ws = new WebSocket(pages[0].webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.onmessage = ev => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
};
await new Promise(resolve => ws.onopen = resolve);
function send(method, params={}) {
  return new Promise(resolve => {
    const callId = ++id;
    pending.set(callId, resolve);
    ws.send(JSON.stringify({ id: callId, method, params }));
  });
}
const expression = `
(async () => ({
  hasModal: !!document.querySelector('#graph-completion-modal'),
  hasOpenButton: !!document.querySelector('[data-graph-completion-open]'),
  previewBuilder: typeof buildSelectedSessionGraphCompletionPreview,
  applyBuilder: typeof applySelectedSessionGraphCompletionPreview,
  selectedSid: state?.sid || null
}))()
`;
const res = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
console.log(JSON.stringify(res.result.result.value, null, 2));
ws.close();
'@ | node --input-type=module -
```

Expected:

```json
{
  "hasModal": true,
  "hasOpenButton": true,
  "previewBuilder": "function",
  "applyBuilder": "function"
}
```

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: source/tests committed. If only `mobile/android/app/capacitor.build.gradle` and `mobile/android/capacitor.settings.gradle` are dirty from prior line-ending/build state, leave them uncommitted.

---

## Self-Review

Spec coverage:
- Global graph entry and selected-session modal: Task 1.
- Preview before write: Task 2 and Task 4.
- Learning nodes, chat notes, child/relationship supplement candidates: Task 2.
- Merge-only apply with current default overwrite of system fields: Task 3.
- Evidence/relations append and dedupe without deletes: Task 3.
- Confirmation flow and graph refresh: Task 4.
- Regression, syntax, APK, device check: Task 5.

No implementation step intentionally deletes nodes, evidence, or relations. Future manual-edit protection is represented by `user_edited_at` and `user_locked_fields` fields in merged records, but current behavior treats all existing generated content as overwritable because node editing is not implemented.
