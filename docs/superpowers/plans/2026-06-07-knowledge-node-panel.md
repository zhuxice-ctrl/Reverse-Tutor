# Knowledge Node Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved diagnosis-first knowledge-node detail panel while preserving the existing semantic fragment card deck and graph interactions.

**Architecture:** Keep the implementation inside the existing mobile app shell. Add small graph-sheet helper functions that derive a diagnosis model from the existing `node`, `digest`, `pairs`, relations, and source targets, then render that model into the compact panel. The expanded panel continues to use the existing `graphSheetReportHtml`, `graphSemanticFragments`, and fragment deck functions.

**Tech Stack:** Static HTML/JavaScript in `static/app/index.html`, Capacitor Android wrapper, pytest string-based regression tests in `tests/test_mobile_persistence.py`, APK build via `npm run build:apk` from `mobile`.

---

## Scope Check

This plan covers one subsystem: the graph knowledge-node detail panel. It does not include graph layout changes, update-source changes, release-feed publishing, model prompt changes, or Android native changes beyond packaging the web shell after implementation.

## File Structure

- Modify `static/app/index.html`
  - Add focused helper functions near the current graph sheet helpers:
    - `graphNodeMasteryPercent(node)`
    - `graphNodeMasteryStage(node, digest, pairs)`
    - `graphNodeDiagnosisText(node, digest, pairs)`
    - `graphNodePanelCards(node, digest, pairs)`
    - `graphNodePrimaryActionsHtml(node, digest, pairs)`
    - `graphSheetDiagnosisCompactHtml(node, digest, pairs)`
  - Update `showGraphSheet(node)` compact-state rendering to use the new diagnosis-first compact panel.
  - Preserve `graphSheetDetailHtml(node, digest, pairs)`, `graphSheetReportHtml`, `graphSemanticFragments`, `graphFragmentDeckHtml`, and all card-deck event binding.
- Modify `tests/test_mobile_persistence.py`
  - Add regression tests for diagnosis-first compact panel helpers.
  - Add regression tests that the compact panel has exactly the six approved card roles.
  - Add regression tests that expanded semantic fragment cards still exist and fallback chat nodes are adapted through `chatMessageIds`, not special one-off layouts.
- No new production files.
- Do not modify `static/app/latest.json`, update-feed metadata, or update-source priority.

---

### Task 1: Add Tests For Diagnosis-First Compact Panel Contract

**Files:**
- Modify: `tests/test_mobile_persistence.py`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Add the failing compact panel structure test**

Add this test near the existing graph sheet tests, after `test_mobile_graph_sheet_opens_chat_fragment_nodes_without_changing_sheet_layout`:

```python
def test_mobile_graph_sheet_compact_panel_is_diagnosis_first_with_six_cards():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    sheet_fn = html.split("async function showGraphSheet", 1)[1].split("function hideGraphSheet", 1)[0]

    assert "function graphSheetDiagnosisCompactHtml" in html
    assert "function graphNodeDiagnosisText" in html
    assert "function graphNodePanelCards" in html
    assert "function graphNodePrimaryActionsHtml" in html
    assert "data-graph-panel=\"diagnosis-compact\"" in html
    assert "data-graph-panel-card=\"already-know\"" in html
    assert "data-graph-panel-card=\"stuck-point\"" in html
    assert "data-graph-panel-card=\"evidence\"" in html
    assert "data-graph-panel-card=\"next-step\"" in html
    assert "data-graph-panel-card=\"related\"" in html
    assert "data-graph-panel-card=\"source\"" in html
    assert "data-graph-action=\"practice\"" in html
    assert "data-graph-action=\"ask-why\"" in html
    assert "data-graph-action=\"review-evidence\"" in html
    assert "graphSheetDiagnosisCompactHtml(node, digest, pairs)" in sheet_fn
    assert sheet_fn.index("graphSheetDiagnosisCompactHtml(node, digest, pairs)") < sheet_fn.index("graphSheetDetailHtml(node, digest, pairs)")
```

- [ ] **Step 2: Add the failing expanded-card preservation test**

Add this test after the compact panel structure test:

```python
def test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    sheet_fn = html.split("async function showGraphSheet", 1)[1].split("function hideGraphSheet", 1)[0]
    report_fn = html.split("function graphSheetReportHtml", 1)[1].split("function graphSheetDetailHtml", 1)[0]

    assert "html = graphSheetDiagnosisCompactHtml(node, digest, pairs);" in sheet_fn
    assert "html = `<div class=\"graph-compact-only\">${html}</div>`;" in sheet_fn
    assert "html += graphSheetDetailHtml(node, digest, pairs);" in sheet_fn
    assert "const fragments = graphSemanticFragments(node, digest, pairs);" in report_fn
    assert "graphFragmentDeckHtml(fragments, node?.sid || state.sid)" in report_fn
    assert "node.nodeType==='chat_session'" not in sheet_fn
    assert "node.nodeType==='chat_fragment'" not in sheet_fn
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_compact_panel_is_diagnosis_first_with_six_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards -v
```

Expected: both tests fail because the helper functions and compact diagnosis panel markup do not exist yet.

- [ ] **Step 4: Commit the failing tests**

```powershell
git add tests/test_mobile_persistence.py
git commit -m "test: specify diagnosis-first graph sheet panel"
```

---

### Task 2: Add Diagnosis Data Helpers Without Changing Rendering

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Add helper-focused tests**

Add this test near the tests from Task 1:

```python
def test_mobile_graph_sheet_diagnosis_helpers_use_existing_graph_data():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    helper_region = html.split("function graphSheetActionButtonsHtml", 1)[0].split("function graphNodeRelations", 1)[1]

    assert "function graphNodeMasteryPercent(node)" in html
    assert "function graphNodeMasteryStage(node, digest, pairs)" in html
    assert "function graphNodeDiagnosisText(node, digest, pairs)" in html
    assert "function graphPanelPreviewText(value, fallback='')" in html
    assert "Number(node?.level || 0)" in html
    assert "digest?.status" in html
    assert "digest?.errors" in html
    assert "digest?.evidence" in html
    assert "pairs.length" in html
    assert "graphNodeRelations(node)" in html
    assert "graphNodeSourceTargets(node)" in html
    assert "function graphNodeRelations" in html
    assert "function graphNodeSourceTargets" in html
    assert "node.nodeType==='chat_session'" not in helper_region
    assert "node.nodeType==='chat_fragment'" not in helper_region
```

- [ ] **Step 2: Run helper test to verify it fails**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_helpers_use_existing_graph_data -v
```

Expected: FAIL because the helper functions are not present.

- [ ] **Step 3: Add helper functions before `graphSheetActionButtonsHtml`**

In `static/app/index.html`, insert this block after `graphNodeSourceTargets(node)` and before `graphSheetActionButtonsHtml(node)`:

```javascript
function graphPanelPreviewText(value, fallback='') {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return graphTrim(text || fallback, 84);
}

function graphNodeMasteryPercent(node) {
  if (node?.nodeType === 'kp') return Math.round(Math.max(0, Math.min(1, Number(node?.level || 0))) * 100);
  if (node?.nodeType === 'source' || node?.nodeType === 'section' || node?.nodeType === 'diagnostic' || node?.nodeType === 'latent') return null;
  const correctness = Number(node?.meta?.evaluation?.correctness || node?.last_correctness || 0);
  const depth = Number(node?.meta?.evaluation?.depth || node?.last_depth || 0);
  const score = Math.max(correctness, depth);
  return score ? Math.round(Math.max(0, Math.min(1, score)) * 100) : null;
}

function graphNodeMasteryStage(node, digest, pairs) {
  if (node?.nodeType === 'source') return '资料锚点';
  if (node?.nodeType === 'section') return '资料章节';
  if (node?.nodeType === 'diagnostic') return '待诊断';
  if (node?.nodeType === 'latent') return '候选知识点';
  if (node?.nodeType === 'note') return '随笔记录';
  const percent = graphNodeMasteryPercent(node);
  if (percent === null) return pairs?.length ? '有对话证据' : '待观察';
  if (percent >= 80) return '能迁移';
  if (percent >= 60) return '能复述';
  if (percent >= 35) return '刚理解';
  return digest?.evidence?.length || pairs?.length ? '证据不足' : '待观察';
}

function graphNodeDiagnosisText(node, digest, pairs) {
  const title = graphNodeTitle(node);
  const error = graphUniqueClean([...(digest?.errors || [])], 1)[0];
  const evidence = graphUniqueClean([...(digest?.evidence || []), node?.summary, node?.content, node?.preview], 1)[0];
  if (error) return `你不是完全不会「${title}」，当前最值得处理的是：${graphPanelPreviewText(error)}。`;
  if (digest?.status && !/还没有足够|暂无|没有/.test(String(digest.status))) return graphPanelPreviewText(digest.status, `这个节点已经有学习记录，适合继续复盘「${title}」。`);
  if (evidence) return `这个节点已经有可回看的证据，但还需要更多练习来确认「${title}」是否稳定掌握。`;
  if (node?.nodeType === 'source' || node?.nodeType === 'section' || node?.nodeType === 'latent') return `这是来自资料的节点，适合先建立上下文，再通过对话把它接入学习路径。`;
  if (pairs?.length) return `这个节点来自最近对话，已经可以回看语义片段，但掌握判断还需要更多证据。`;
  return `这个节点目前主要表示图谱关系，继续对话后会补充更具体的诊断和证据。`;
}
```

- [ ] **Step 4: Run helper test to verify it passes**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_helpers_use_existing_graph_data -v
```

Expected: PASS.

- [ ] **Step 5: Commit helper functions**

```powershell
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: derive graph sheet diagnosis data"
```

---

### Task 3: Render The Six-Card Diagnosis Compact Panel

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Add renderer functions before `graphSheetActionButtonsHtml`**

Add this block after the helper functions from Task 2:

```javascript
function graphNodePanelCards(node, digest, pairs) {
  const relations = graphNodeRelations(node);
  const sources = graphNodeSourceTargets(node);
  const evidenceItems = graphUniqueClean([...(digest?.evidence || []), node?.summary, node?.content, node?.preview], 3);
  const errors = graphUniqueClean([...(digest?.errors || []), node?.meta?.evaluation?.misconception, node?.meta?.evaluation?.error_pattern], 2);
  const nextSteps = graphUniqueClean([...(digest?.nextSteps || []), ...(node?.memoryExpansion?.teacher_questions || [])], 2);
  const known = evidenceItems[0] || (pairs?.length ? `${pairs.length} 轮对话可回看` : '等待更多学习证据');
  const stuck = errors[0] || (node?.nodeType === 'latent' ? '还没有在对话中命中' : '还没有明显错因');
  const evidence = evidenceItems.length ? `${evidenceItems.length} 条证据` : '证据较薄';
  const next = nextSteps[0] || (errors[0] ? '先追问这个卡点' : '继续用一个小题验证');
  const related = relations[0] ? graphNodeTitle(relations[0].node) : '暂无相邻节点';
  const source = sources[0] ? sources[0].label : (pairs?.length ? '来自对话' : '暂无来源');
  return [
    { key:'already-know', label:'已会', tone:'ok', value:known },
    { key:'stuck-point', label:'卡点', tone:errors.length ? 'warn' : 'neutral', value:stuck },
    { key:'evidence', label:'证据', tone:evidenceItems.length ? 'info' : 'neutral', value:evidence },
    { key:'next-step', label:'下一步', tone:'action', value:next },
    { key:'related', label:'相关', tone:'relation', value:related },
    { key:'source', label:'来源', tone:'source', value:source },
  ];
}

function graphNodePrimaryActionsHtml(node, digest, pairs) {
  const hasEvidence = pairs?.length || digest?.evidence?.length || node?.chatMessageIds?.length || node?.messageId;
  const hasWeakPoint = (digest?.errors || []).length || node?.meta?.evaluation?.misconception || node?.meta?.evaluation?.error_pattern;
  return `<div class="graph-diagnosis-actions">
    <button type="button" data-graph-action="practice" data-graph-expand-detail class="graph-diagnosis-action primary">来一题</button>
    <button type="button" data-graph-action="ask-why" data-graph-expand-detail class="graph-diagnosis-action">${hasWeakPoint ? '追问卡点' : '问为什么'}</button>
    <button type="button" data-graph-action="review-evidence" ${hasEvidence ? 'data-graph-jump-chat' : 'data-graph-expand-detail'} class="graph-diagnosis-action">回看证据</button>
  </div>`;
}

function graphSheetDiagnosisCompactHtml(node, digest, pairs) {
  const percent = graphNodeMasteryPercent(node);
  const stage = graphNodeMasteryStage(node, digest, pairs);
  const diagnosis = graphNodeDiagnosisText(node, digest, pairs);
  const cards = graphNodePanelCards(node, digest, pairs);
  const evidenceCount = graphUniqueClean([...(digest?.evidence || []), node?.summary, node?.content, node?.preview], 8).length;
  const sourceCount = graphNodeSourceTargets(node).length;
  const meta = [
    pairs?.length ? `${pairs.length} 轮对话` : '',
    evidenceCount ? `${evidenceCount} 条证据` : '',
    sourceCount ? `${sourceCount} 个来源` : '',
  ].filter(Boolean).join(' · ') || graphNodeTypeLabel(node);
  return `<section class="graph-diagnosis-panel" data-graph-panel="diagnosis-compact">
    <header class="graph-diagnosis-head">
      <div class="min-w-0">
        <div class="graph-diagnosis-eyebrow">${esc(graphNodeTypeLabel(node))}</div>
        <h2 class="graph-diagnosis-title">${esc(graphNodeTitle(node))}</h2>
        <div class="graph-diagnosis-meta">${esc(meta)}</div>
      </div>
      <div class="graph-diagnosis-score">
        <span>${percent === null ? '诊断' : `${percent}%`}</span>
        <small>${esc(stage)}</small>
      </div>
    </header>
    <div class="graph-diagnosis-statement">
      <div class="label">当前判断</div>
      <p>${renderRichText(diagnosis)}</p>
    </div>
    <div class="graph-diagnosis-card-grid">
      ${cards.map(card => `<article class="graph-diagnosis-card ${esc(card.tone)}" data-graph-panel-card="${esc(card.key)}">
        <div class="label">${esc(card.label)}</div>
        <p>${renderRichText(graphPanelPreviewText(card.value, '暂无'))}</p>
      </article>`).join('')}
    </div>
    ${graphNodePrimaryActionsHtml(node, digest, pairs)}
  </section>`;
}
```

- [ ] **Step 2: Replace compact construction in `showGraphSheet`**

In `showGraphSheet(node)`, replace the old long branch-based compact `let html=''` through the end of the final `else` block with:

```javascript
  let html = graphSheetDiagnosisCompactHtml(node, digest, pairs);
```

Keep the following existing lines unchanged immediately after it:

```javascript
  html = `<div class="graph-compact-only">${html}</div>`;
  html += graphSheetDetailHtml(node, digest, pairs);
  body.innerHTML=html;
```

- [ ] **Step 3: Add CSS near existing `.graph-sheet` styles**

In `static/app/index.html`, near the existing graph sheet CSS, add:

```css
  .graph-diagnosis-panel {
    display: grid;
    gap: 12px;
  }
  .graph-diagnosis-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .graph-diagnosis-eyebrow,
  .graph-diagnosis-meta,
  .graph-diagnosis-card .label,
  .graph-diagnosis-statement .label {
    font-size: 10px;
    color: var(--muted);
  }
  .graph-diagnosis-title {
    font-size: 18px;
    line-height: 1.2;
    font-weight: 800;
    color: var(--text);
    margin: 2px 0 0;
  }
  .graph-diagnosis-score {
    width: 58px;
    min-width: 58px;
    height: 58px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--page);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    line-height: 1.05;
    font-weight: 800;
  }
  .graph-diagnosis-score small {
    margin-top: 3px;
    font-size: 9px;
    font-weight: 700;
    max-width: 48px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .graph-diagnosis-statement {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel-2);
    padding: 12px 13px;
  }
  .graph-diagnosis-statement p {
    margin: 4px 0 0;
    color: var(--text);
    font-size: 14px;
    line-height: 1.55;
    font-weight: 650;
  }
  .graph-diagnosis-card-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .graph-diagnosis-card {
    min-height: 74px;
    border-radius: 12px;
    background: var(--panel-2);
    border-left: 3px solid var(--line);
    padding: 10px 10px 9px;
  }
  .graph-diagnosis-card.ok { border-left-color: #91bf95; }
  .graph-diagnosis-card.warn { border-left-color: var(--warn); }
  .graph-diagnosis-card.info { border-left-color: #80a7c9; }
  .graph-diagnosis-card.action { border-left-color: #d8df9f; }
  .graph-diagnosis-card.relation { border-left-color: #b7a4d6; }
  .graph-diagnosis-card.source { border-left-color: #d4b46b; }
  .graph-diagnosis-card p {
    margin: 5px 0 0;
    color: var(--text-soft);
    font-size: 11px;
    line-height: 1.4;
  }
  .graph-diagnosis-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .graph-diagnosis-action {
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--panel-2);
    color: var(--text);
    padding: 8px 11px;
    font-size: 12px;
    font-weight: 750;
  }
  .graph-diagnosis-action.primary {
    background: var(--accent);
    color: var(--page);
    border-color: transparent;
  }
```

- [ ] **Step 4: Run compact panel tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_compact_panel_is_diagnosis_first_with_six_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_expanded_detail_reads_like_report_with_semantic_cards -v
```

Expected: PASS.

- [ ] **Step 5: Commit compact panel rendering**

```powershell
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: render diagnosis-first graph sheet panel"
```

---

### Task 4: Validate Fallback Chat Nodes, Mobile Layout, And Packaging

**Files:**
- Modify only if tests expose a bug:
  - `static/app/index.html`
  - `tests/test_mobile_persistence.py`
- Build output:
  - `release-artifacts/Reverse-Tutor-v0.19.6-graph-panel-test.apk`

- [ ] **Step 1: Run graph and update regression tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py tests/test_update_check_resilience.py
```

Expected:

```text
78 passed
6 passed
```

The exact mobile persistence count may be higher if new tests from this plan are added. No failures should remain.

- [ ] **Step 2: Run broader affected tests**

Run:

```powershell
py -m pytest tests/test_mobile_product_experience.py tests/test_llm_provider_presets.py tests/test_websearch.py
```

Expected: all tests pass.

- [ ] **Step 3: Build APK**

Run:

```powershell
Set-Location F:\xw\reverse-tutor\mobile
npm run build:apk
Set-Location F:\xw\reverse-tutor
```

Expected: Gradle reports `BUILD SUCCESSFUL`.

- [ ] **Step 4: Copy APK artifact**

Run:

```powershell
$src = 'F:\xw\reverse-tutor\mobile\android\app\build\outputs\apk\release\app-release.apk'
$dst = 'F:\xw\reverse-tutor\release-artifacts\Reverse-Tutor-v0.19.6-graph-panel-test.apk'
New-Item -ItemType Directory -Force -Path 'F:\xw\reverse-tutor\release-artifacts' | Out-Null
Copy-Item -LiteralPath $src -Destination $dst -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $dst
```

Expected: file exists and SHA-256 is printed.

- [ ] **Step 5: Install APK to the connected Android device**

Run:

```powershell
$adb = 'C:\Users\Lenovo\AppData\Local\Android\Sdk\platform-tools\adb.exe'
$apk = 'F:\xw\reverse-tutor\release-artifacts\Reverse-Tutor-v0.19.6-graph-panel-test.apk'
& $adb devices
& $adb install -r $apk
& $adb shell dumpsys package com.reversetutor.app | Select-String -Pattern 'versionCode|versionName'
```

Expected:

```text
Success
versionName=<current test version>
```

- [ ] **Step 6: Verify WebView runtime and panel cards**

Run the existing CDP pattern used in this thread, with Node's experimental WebSocket:

```powershell
@'
const targets = await fetch('http://127.0.0.1:9222/json').then(r => r.json());
const ws = new WebSocket(targets[0].webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
function send(method, params={}) {
  const msg = { id: ++id, method, params };
  ws.send(JSON.stringify(msg));
  return new Promise((resolve, reject) => {
    pending.set(msg.id, { resolve, reject });
    setTimeout(() => reject(new Error('timeout ' + method)), 30000);
  });
}
ws.onmessage = ev => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
  }
};
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
await send('Runtime.enable');
const result = await send('Runtime.evaluate', {
  returnByValue: true,
  awaitPromise: true,
  expression: `(async () => {
    if (!state.sid) {
      const sessions = await DB.all('sessions');
      state.sid = sessions?.[0]?.id || state.sid;
    }
    await openLearningContext('graph');
    await new Promise(r => setTimeout(r, 1200));
    const node = state.graphDetailNodes.find(n => (n.chatMessageIds || []).length) || state.graphDetailNodes[0];
    await showGraphSheet(node);
    expandGraphSheet();
    await new Promise(r => setTimeout(r, 200));
    const modal = document.querySelector('#update-modal');
    const style = modal ? getComputedStyle(modal) : null;
    return {
      version: APP_VERSION_NAME + ':' + APP_VERSION_CODE,
      updateModalVisible: !!modal && !modal.classList.contains('hidden') && style?.display !== 'none',
      sheetVisible: document.querySelector('#graph-sheet')?.classList.contains('show') || false,
      diagnosisPanel: document.querySelectorAll('[data-graph-panel="diagnosis-compact"]').length,
      diagnosisCards: document.querySelectorAll('[data-graph-panel-card]').length,
      fragmentDecks: document.querySelectorAll('[data-graph-fragment-deck]').length,
      fragmentCards: document.querySelectorAll('.graph-fragment-card').length,
      specialChatUiBranchesPresent: String(showGraphSheet).includes("node.nodeType==='chat_session'") || String(showGraphSheet).includes("node.nodeType==='chat_fragment'"),
    };
  })()`
});
console.log(JSON.stringify(result.result.value, null, 2));
ws.close();
'@ | node --experimental-websocket --input-type=module -
```

Expected JSON:

```json
{
  "updateModalVisible": false,
  "sheetVisible": true,
  "diagnosisPanel": 1,
  "diagnosisCards": 6,
  "fragmentDecks": 1,
  "specialChatUiBranchesPresent": false
}
```

- [ ] **Step 7: Commit final verification changes if any**

If implementation required any fixes after verification:

```powershell
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "fix: preserve graph card deck in diagnosis panel"
```

If no additional code changed after Task 3, skip this commit and record the verification in the final response.

---

## Self-Review

**Spec coverage:** The plan covers diagnosis-first compact layout, the six-card structure, preservation of expanded semantic cards, fallback chat-node evidence mapping through existing card data, and mobile validation. It explicitly excludes graph layout, update-source changes, and release publishing.

**Completeness scan:** No task uses unresolved filler language or vague "add tests" wording without concrete test code or commands.

**Type consistency:** Helper names introduced in Task 2 are used by renderers in Task 3. Existing functions `graphNodeRelations`, `graphNodeSourceTargets`, `graphSheetDetailHtml`, `graphSemanticFragments`, and `graphFragmentDeckHtml` are referenced consistently.
