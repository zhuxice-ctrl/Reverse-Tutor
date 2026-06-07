# Tiered Graph Node Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mobile graph node bottom sheet and expanded detail page as tiered presentation templates for learning-state, candidate/structure, and context/source nodes.

**Architecture:** Keep graph creation and relation logic unchanged. Add a small presentation-template layer in `static/app/index.html` that routes existing node types to compact and expanded renderers, using only current node, digest, source, chat, and relation data. Update the existing string-based mobile tests so they specify tiered rendering instead of the old uniform six-card compact panel.

**Tech Stack:** Vanilla JavaScript, HTML string renderers, existing CSS in `static/app/index.html`, pytest string assertions.

---

## File Structure

- Modify: `static/app/index.html`
  - CSS near `.graph-diagnosis-panel` for compact learning-state, structure, and context cards.
  - JS helper region from `graphNodeTypeLabel()` through compact panel helpers.
  - JS report region from `graphReportLead()` through `graphSheetDetailHtml()`.
  - `showGraphSheet()` compact renderer call.
- Modify: `tests/test_mobile_persistence.py`
  - Replace the old uniform six-card compact panel test with tiered compact/detail tests.
  - Keep semantic evidence preservation tests, but point them at the new learning-state report.
- Modify: `tests/test_mobile_product_experience.py`
  - Keep the node-creation rule test focused on graph node origin, not old panel field cards.

No schema files, backend storage, update feeds, release metadata, or graph-build relation logic should change.

---

### Task 1: Update Tests To Specify Tiered Rendering

**Files:**
- Modify: `tests/test_mobile_persistence.py`
- Modify: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Replace the old six-card compact panel test**

In `tests/test_mobile_persistence.py`, replace `test_mobile_graph_sheet_compact_panel_is_diagnosis_first_with_six_cards` with:

```python
def test_mobile_graph_sheet_uses_tiered_compact_templates():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    sheet_fn = html.split("async function showGraphSheet", 1)[1].split("function hideGraphSheet", 1)[0]

    assert "function graphNodeSheetTemplate(node)" in html
    assert "function graphSheetCompactHtml(node, digest, pairs)" in html
    assert "function graphKnowledgeCompactHtml(node, digest, pairs)" in html
    assert "function graphStructureCompactHtml(node, digest, pairs)" in html
    assert "function graphContextCompactHtml(node, digest, pairs)" in html
    assert "data-graph-panel=\"node-compact\"" in html
    assert "data-graph-template=\"learning-state\"" in html
    assert "data-graph-template=\"candidate-structure\"" in html
    assert "data-graph-template=\"context-source\"" in html
    assert "data-graph-kp-main-stuck" in html
    assert "data-graph-structure-reason" in html
    assert "data-graph-context-coverage" in html
    assert "data-graph-action=\"practice\"" in html
    assert "data-graph-action=\"ask-why\"" in html
    assert "data-graph-action=\"open-source\"" in html
    assert "graphSheetCompactHtml(node, digest, pairs)" in sheet_fn
    assert sheet_fn.index("graphSheetCompactHtml(node, digest, pairs)") < sheet_fn.index("graphSheetDetailHtml(node, digest, pairs)")
```

- [ ] **Step 2: Add a detail-template test**

In `tests/test_mobile_persistence.py`, add this test after the compact template test:

```python
def test_mobile_graph_sheet_expanded_detail_uses_tiered_reports():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    report_fn = html.split("function graphSheetReportHtml", 1)[1].split("function graphSheetDetailHtml", 1)[0]

    assert "function graphKnowledgeReportHtml(node, digest, pairs=[])" in html
    assert "function graphStructureReportHtml(node, digest, pairs=[])" in html
    assert "function graphContextReportHtml(node, digest, pairs=[])" in html
    assert "data-graph-report-template=\"learning-state\"" in html
    assert "data-graph-report-template=\"candidate-structure\"" in html
    assert "data-graph-report-template=\"context-source\"" in html
    assert "data-graph-detail-section=\"current-judgment\"" in html
    assert "data-graph-detail-section=\"already-know\"" in html
    assert "data-graph-detail-section=\"main-stuck\"" in html
    assert "data-graph-detail-section=\"why-stuck\"" in html
    assert "data-graph-detail-section=\"evidence\"" in html
    assert "data-graph-detail-section=\"strategy\"" in html
    assert "data-graph-detail-section=\"relations\"" in html
    assert "graphNodeSheetTemplate(node)" in report_fn
    assert "graphKnowledgeReportHtml(node, digest, pairs)" in report_fn
    assert "graphStructureReportHtml(node, digest, pairs)" in report_fn
    assert "graphContextReportHtml(node, digest, pairs)" in report_fn
```

- [ ] **Step 3: Update the structured digest test**

In `test_mobile_graph_sheet_shows_structured_learning_digest_before_raw_records`, replace the old panel/card assertions:

```python
assert "data-graph-panel=\"diagnosis-compact\"" in html
assert "data-graph-panel-card=\"evidence\"" in html
```

with:

```python
assert "data-graph-panel=\"node-compact\"" in html
assert "data-graph-template=\"learning-state\"" in html
assert "data-graph-detail-section=\"evidence\"" in html
```

- [ ] **Step 4: Update semantic-card preservation test names only where needed**

Keep `test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards`, but update these expected strings:

```python
assert "html = graphSheetCompactHtml(node, digest, pairs);" in sheet_fn
assert "const fragments = graphSemanticFragments(node, digest, pairs);" in report_fn
assert "graphFragmentDeckHtml(fragments, node?.sid || state.sid)" in report_fn
assert "node.nodeType==='chat_session'" not in sheet_fn
assert "node.nodeType==='chat_fragment'" not in sheet_fn
```

- [ ] **Step 5: Update product-experience graph node rule test**

In `tests/test_mobile_product_experience.py`, update `test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields` so it no longer depends on `graphNodePanelCards`.

Use:

```python
def test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields():
    html = mobile_html()
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]
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
```

- [ ] **Step 6: Run focused tests and verify they fail**

Run:

```powershell
pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_uses_tiered_compact_templates tests/test_mobile_persistence.py::test_mobile_graph_sheet_expanded_detail_uses_tiered_reports tests/test_mobile_product_experience.py::test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields -q
```

Expected: FAIL because the new template functions and data attributes do not exist yet.

- [ ] **Step 7: Commit the failing tests**

Run:

```powershell
git add tests/test_mobile_persistence.py tests/test_mobile_product_experience.py
git commit -m "test: specify tiered graph node sheets"
```

---

### Task 2: Add Template And Data-Shaping Helpers

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`
- Test: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Add helper functions after `graphPanelPreviewText()`**

Add:

```javascript
function graphNodeSheetTemplate(node) {
  const type = node?.nodeType || '';
  if (type === 'kp') return 'learning-state';
  if (type === 'latent' || type === 'section' || type === 'diagnostic') return 'candidate-structure';
  if (type === 'source' || type === 'note') return 'context-source';
  return 'candidate-structure';
}

function graphNodeLightPath(node) {
  const type = graphNodeTypeLabel(node);
  const parts = [type];
  if (node?.sourceName) parts.push(node.sourceName);
  if (node?.sessionTitle) parts.push(node.sessionTitle);
  if (node?.sourceType && !node?.sourceName) parts.push(String(node.sourceType).toUpperCase());
  const rel = graphNodeRelations(node)[0];
  if (parts.length < 3 && rel) parts.push(graphNodeTitle(rel.node));
  return graphUniqueClean(parts, 3).join(' / ') || type;
}

function graphNodeEvidenceItems(node, digest, limit=5) {
  return graphUniqueClean([
    ...(digest?.evidence || []),
    node?.summary,
    node?.memoryExpansion?.summary,
    node?.preview,
    node?.content,
  ], limit);
}

function graphNodeKnownItems(node, digest, pairs, limit=3) {
  const items = [];
  if (Array.isArray(digest?.known)) items.push(...digest.known);
  if (digest?.status) items.push(digest.status);
  if (pairs?.length) items.push(`已有 ${pairs.length} 轮相关对话可回看`);
  return graphUniqueClean(items, limit);
}

function graphNodeWeakPoint(node, digest) {
  return graphUniqueClean([
    ...(digest?.errors || []),
    node?.meta?.evaluation?.misconception,
    node?.meta?.evaluation?.error_pattern,
  ], 1)[0] || '';
}

function graphNodeNextStepItems(node, digest, limit=3) {
  return graphUniqueClean([
    ...(digest?.nextSteps || []),
    ...(node?.memoryExpansion?.teacher_questions || []),
  ], limit);
}

function graphNodeCoverageText(node) {
  const relations = graphNodeRelations(node);
  const sources = graphNodeSourceTargets(node);
  const parts = [];
  if (relations.length) parts.push(`${relations.length} 个相关节点`);
  if (sources.length) parts.push(`${sources.length} 个来源锚点`);
  if (node?.sourcePages?.length) parts.push(`${node.sourcePages.length} 页`);
  if (node?.sourceText || node?.content) parts.push(`${String(node.sourceText || node.content).length} 字`);
  return parts.join(' · ') || '覆盖范围会随着资料和对话证据继续补全';
}

function graphRelationGroupLabel(kind) {
  if (kind === 'foundation') return '来源支撑';
  if (kind === 'outline') return '来源章节';
  if (kind === 'diagnostic') return '诊断提示';
  if (kind === 'note') return '随笔引用';
  if (kind === 'sequence') return '学习顺序';
  if (kind === 'related') return '相关概念';
  return graphLinkKindLabel(kind);
}

function graphNodeRelationGroups(node) {
  const groups = new Map();
  for (const rel of graphNodeRelations(node)) {
    const label = graphRelationGroupLabel(rel.kind);
    const list = groups.get(label) || [];
    list.push(rel);
    groups.set(label, list);
  }
  return [...groups.entries()].map(([label, relations]) => ({ label, relations }));
}
```

The important invariant is that these helpers use existing data only.

- [ ] **Step 2: Remove the uniform panel-card helper**

Remove `graphNodePanelCards(node, digest, pairs)` after the new compact renderers are added in Task 3. If this function is still referenced after Task 3, replace the references with `graphNodeEvidenceItems`, `graphNodeWeakPoint`, `graphNodeNextStepItems`, or `graphNodeRelationGroups`.

- [ ] **Step 3: Run helper grep check**

Run:

```powershell
rg -n "function graphNodeSheetTemplate|function graphNodeLightPath|function graphNodeEvidenceItems|function graphNodeRelationGroups" static/app/index.html
```

Expected: each new helper is present exactly once.

---

### Task 3: Implement Tiered Compact Bottom Sheets

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Replace compact CSS**

Keep existing `.graph-diagnosis-*` rules only if reused by report content. Add these rules near the current graph sheet CSS:

```css
.graph-node-compact {
  display: grid;
  gap: 12px;
}
.graph-node-compact-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.graph-node-eyebrow,
.graph-node-path,
.graph-node-label,
.graph-node-hint {
  font-size: 10px;
  color: var(--muted);
}
.graph-node-title {
  margin: 2px 0 0;
  font-size: 18px;
  line-height: 1.2;
  font-weight: 800;
  color: var(--text);
  letter-spacing: 0;
}
.graph-node-score {
  width: 62px;
  min-width: 62px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel-2);
  padding: 8px 6px;
  text-align: center;
}
.graph-node-score strong {
  display: block;
  font-size: 16px;
  line-height: 1;
  color: var(--text);
}
.graph-node-score span {
  display: block;
  margin-top: 4px;
  font-size: 9px;
  color: var(--muted);
}
.graph-node-meter {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 55%, transparent);
}
.graph-node-meter > i {
  display: block;
  height: 100%;
  width: var(--graph-progress, 0%);
  border-radius: inherit;
  background: var(--accent);
}
.graph-node-statement,
.graph-node-main-point,
.graph-node-context-box {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel-2);
  padding: 12px 13px;
}
.graph-node-statement p,
.graph-node-main-point p,
.graph-node-context-box p {
  margin: 4px 0 0;
  color: var(--text);
  font-size: 13px;
  line-height: 1.55;
  font-weight: 650;
}
.graph-node-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.graph-node-chip {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-2);
  color: var(--text-soft);
  padding: 6px 9px;
  font-size: 11px;
  line-height: 1.2;
}
```

- [ ] **Step 2: Add compact renderer router**

Replace `graphSheetDiagnosisCompactHtml(node, digest, pairs)` with:

```javascript
function graphSheetCompactHtml(node, digest, pairs) {
  const template = graphNodeSheetTemplate(node);
  if (template === 'learning-state') return graphKnowledgeCompactHtml(node, digest, pairs);
  if (template === 'context-source') return graphContextCompactHtml(node, digest, pairs);
  return graphStructureCompactHtml(node, digest, pairs);
}
```

- [ ] **Step 3: Add `graphKnowledgeCompactHtml()`**

Add:

```javascript
function graphKnowledgeCompactHtml(node, digest, pairs) {
  pairs = pairs || [];
  const percent = graphNodeMasteryPercent(node);
  const stage = graphNodeMasteryStage(node, digest, pairs);
  const diagnosis = graphNodeDiagnosisText(node, digest, pairs);
  const weakPoint = graphNodeWeakPoint(node, digest);
  const nextSteps = graphNodeNextStepItems(node, digest, 1);
  const progress = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  const mainPoint = weakPoint || nextSteps[0] || '这个知识点还需要更多学习证据，暂时不能稳定判断主要卡点。';
  return `<section class="graph-node-compact" data-graph-panel="node-compact" data-graph-template="learning-state">
    <header class="graph-node-compact-head">
      <div class="min-w-0">
        <div class="graph-node-eyebrow">${esc(graphNodeTypeLabel(node))}</div>
        <h2 class="graph-node-title">${esc(graphNodeTitle(node))}</h2>
        <div class="graph-node-path">${esc(graphNodeLightPath(node))}</div>
      </div>
      <div class="graph-node-score">
        <strong>${percent === null ? '--' : `${percent}%`}</strong>
        <span>${esc(stage)}</span>
      </div>
    </header>
    <div class="graph-node-meter" style="--graph-progress:${progress}%"><i></i></div>
    <div class="graph-node-statement">
      <div class="graph-node-label">当前判断</div>
      <p>${renderRichText(diagnosis)}</p>
    </div>
    <div class="graph-node-main-point" data-graph-kp-main-stuck>
      <div class="graph-node-label">${weakPoint ? '主要卡点' : '当前重点'}</div>
      <p>${renderRichText(graphPanelPreviewText(mainPoint, '还需要更多证据。'))}</p>
    </div>
    ${graphNodePrimaryActionsHtml(node, digest, pairs)}
  </section>`;
}
```

- [ ] **Step 4: Add `graphStructureCompactHtml()`**

Add:

```javascript
function graphStructureCompactHtml(node, digest, pairs) {
  const templateLabel = node?.nodeType === 'latent' ? '候选知识点'
    : node?.nodeType === 'diagnostic' ? '诊断节点'
    : '资料结构';
  const evidence = graphNodeEvidenceItems(node, digest, 1)[0];
  const reason = evidence || node?.modelTitleSuggestion || node?.titleOrigin || '这个节点来自资料结构、内容提取或导入诊断。';
  const relations = graphNodeRelations(node).slice(0, 3);
  const chips = relations.map(rel => `<button type="button" data-graph-node-jump="${esc(String(rel.node.key))}" class="graph-node-chip">${esc(graphNodeTitle(rel.node))}</button>`).join('');
  return `<section class="graph-node-compact" data-graph-panel="node-compact" data-graph-template="candidate-structure">
    <header class="graph-node-compact-head">
      <div class="min-w-0">
        <div class="graph-node-eyebrow">${esc(templateLabel)}</div>
        <h2 class="graph-node-title">${esc(graphNodeTitle(node))}</h2>
        <div class="graph-node-path">${esc(graphNodeLightPath(node))}</div>
      </div>
    </header>
    <div class="graph-node-context-box" data-graph-structure-reason>
      <div class="graph-node-label">为什么出现</div>
      <p>${renderRichText(graphPanelPreviewText(reason, '来自资料的上下文'))}</p>
    </div>
    <div class="graph-node-chip-row">${chips || '<span class="graph-node-chip">暂未接入学习节点</span>'}</div>
    ${graphStructureActionsHtml(node)}
  </section>`;
}
```

- [ ] **Step 5: Add `graphContextCompactHtml()`**

Add:

```javascript
function graphContextCompactHtml(node, digest, pairs) {
  const preview = graphNodeEvidenceItems(node, digest, 1)[0] || graphPanelPreviewText(node?.content || node?.sourceText, '');
  const relations = graphNodeRelations(node).slice(0, 3);
  const chips = relations.map(rel => `<button type="button" data-graph-node-jump="${esc(String(rel.node.key))}" class="graph-node-chip">${esc(graphNodeTitle(rel.node))}</button>`).join('');
  return `<section class="graph-node-compact" data-graph-panel="node-compact" data-graph-template="context-source">
    <header class="graph-node-compact-head">
      <div class="min-w-0">
        <div class="graph-node-eyebrow">${esc(graphNodeTypeLabel(node))}</div>
        <h2 class="graph-node-title">${esc(graphNodeTitle(node))}</h2>
        <div class="graph-node-path">${esc(graphNodeLightPath(node))}</div>
      </div>
    </header>
    <div class="graph-node-context-box" data-graph-context-coverage>
      <div class="graph-node-label">覆盖范围</div>
      <p>${esc(graphNodeCoverageText(node))}</p>
    </div>
    ${preview ? `<div class="graph-node-context-box"><div class="graph-node-label">内容预览</div><p>${renderRichText(graphPanelPreviewText(preview, ''))}</p></div>` : ''}
    <div class="graph-node-chip-row">${chips || '<span class="graph-node-chip">暂未关联学习节点</span>'}</div>
    ${graphContextActionsHtml(node)}
  </section>`;
}
```

- [ ] **Step 6: Add adaptive compact actions**

Keep `graphNodePrimaryActionsHtml()` for `kp`, but add:

```javascript
function graphStructureActionsHtml(node) {
  const targets = graphNodeSourceTargets(node);
  return `<div class="graph-diagnosis-actions">
    <button type="button" data-graph-action="ask-why" data-graph-expand-detail class="graph-diagnosis-action primary">围绕它提问</button>
    ${targets[0] ? `<button type="button" data-graph-action="open-source" data-graph-source-anchor="${esc(targets[0].sourceId)}" data-graph-open-source="${esc(targets[0].sourceId)}" data-graph-source-sid="${esc(String(targets[0].sid || ''))}" class="graph-diagnosis-action">打开来源</button>` : ''}
    <button type="button" data-graph-expand-detail class="graph-diagnosis-action">查看详情</button>
  </div>`;
}

function graphContextActionsHtml(node) {
  const targets = graphNodeSourceTargets(node);
  const chatIds = [...(node?.chatMessageIds || []), node?.messageId].filter(Boolean);
  return `<div class="graph-diagnosis-actions">
    ${targets[0] ? `<button type="button" data-graph-action="open-source" data-graph-source-anchor="${esc(targets[0].sourceId)}" data-graph-open-source="${esc(targets[0].sourceId)}" data-graph-source-sid="${esc(String(targets[0].sid || ''))}" class="graph-diagnosis-action primary">打开来源</button>` : ''}
    ${chatIds.length ? '<button type="button" data-graph-jump-chat class="graph-diagnosis-action">回到聊天</button>' : ''}
    <button type="button" data-graph-expand-detail class="graph-diagnosis-action">查看详情</button>
  </div>`;
}
```

- [ ] **Step 7: Wire `showGraphSheet()`**

Change:

```javascript
let html = graphSheetDiagnosisCompactHtml(node, digest, pairs);
```

to:

```javascript
let html = graphSheetCompactHtml(node, digest, pairs);
```

- [ ] **Step 8: Run compact tests**

Run:

```powershell
pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_uses_tiered_compact_templates tests/test_mobile_product_experience.py::test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields -q
```

Expected: PASS.

- [ ] **Step 9: Commit compact implementation**

Run:

```powershell
git add static/app/index.html tests/test_mobile_persistence.py tests/test_mobile_product_experience.py
git commit -m "feat: add tiered graph node compact sheets"
```

---

### Task 4: Implement Tiered Expanded Detail Reports

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Route `graphSheetReportHtml()` by template**

Replace the body of `graphSheetReportHtml(node, digest, pairs=[])` with:

```javascript
function graphSheetReportHtml(node, digest, pairs=[]) {
  const template = graphNodeSheetTemplate(node);
  if (template === 'learning-state') return graphKnowledgeReportHtml(node, digest, pairs);
  if (template === 'context-source') return graphContextReportHtml(node, digest, pairs);
  return graphStructureReportHtml(node, digest, pairs);
}
```

- [ ] **Step 2: Add list and relation helpers for reports**

Add before `graphSheetReportHtml()`:

```javascript
function graphReportListHtml(items, emptyText) {
  const clean = graphUniqueClean(items || [], 5);
  const rows = clean.length ? clean : [emptyText];
  return `<ul class="list-disc pl-5 space-y-1">${rows.map(item => `<li>${renderRichText(String(item).slice(0, 260))}</li>`).join('')}</ul>`;
}

function graphGroupedRelationsReportHtml(node) {
  const groups = graphNodeRelationGroups(node);
  if (!groups.length) return '<div class="text-xs text-neutral-500">暂时没有可浏览的相邻节点。</div>';
  return groups.map(group => `<div class="graph-report-relation-group">
    <div class="text-[11px] font-semibold text-neutral-500 mb-1">${esc(group.label)}</div>
    <div class="graph-report-link-list">${group.relations.map(rel => `<button type="button" data-graph-node-jump="${esc(String(rel.node.key))}" class="graph-report-inline-link">
      [[${esc(graphNodeTitle(rel.node))}]]
      <span class="meta">${esc(graphNodeTypeLabel(rel.node))}</span>
    </button>`).join('')}</div>
  </div>`).join('');
}
```

- [ ] **Step 3: Add `graphKnowledgeReportHtml()`**

Add:

```javascript
function graphKnowledgeReportHtml(node, digest, pairs=[]) {
  const fragments = graphSemanticFragments(node, digest, pairs);
  const fragmentHtml = fragments.length ? graphFragmentDeckHtml(fragments, node?.sid || state.sid) : '';
  const weakPoint = graphNodeWeakPoint(node, digest);
  const known = graphNodeKnownItems(node, digest, pairs, 4);
  const evidence = graphNodeEvidenceItems(node, digest, 5);
  const nextSteps = graphNodeNextStepItems(node, digest, 4);
  return `<article class="graph-node-report" data-graph-report-template="learning-state">
    <header class="graph-report-head">
      <div class="text-[11px] text-neutral-500">${esc(graphNodeLightPath(node))}</div>
      <h2 class="graph-report-title">${esc(graphNodeTitle(node))}</h2>
      <blockquote class="graph-report-lead">${renderRichText(graphNodeDiagnosisText(node, digest, pairs))}</blockquote>
    </header>
    ${graphReportSectionHtml('当前判断', `<p>${renderRichText(graphReportLead(node, digest, pairs))}</p>`, 'data-graph-detail-section="current-judgment"')}
    ${graphReportSectionHtml('你已经会了什么', graphReportListHtml(known, '还需要更多对话，才能稳定展示已掌握部分。'), 'data-graph-detail-section="already-know"')}
    ${graphReportSectionHtml('主要卡点', `<p>${renderRichText(graphPanelPreviewText(weakPoint, '暂时还没有检测到明确卡点。'))}</p>`, 'data-graph-detail-section="main-stuck"')}
    ${graphReportSectionHtml('为什么会卡', `<p>${renderRichText(graphPanelPreviewText(weakPoint || digest?.status || node?.summary, '这个节点还需要更多证据，系统暂时不能解释具体卡因。'))}</p>`, 'data-graph-detail-section="why-stuck"')}
    ${graphReportSectionHtml('判断依据', `${fragmentHtml || graphReportListHtml(evidence, '暂时还没有收集到详细证据。')}`, 'data-graph-detail-section="evidence"')}
    ${graphReportSectionHtml('下一步', graphReportListHtml(nextSteps, '先围绕这个点追问一次，或完成一个短练习。'), 'data-graph-detail-section="strategy"')}
    ${graphReportSectionHtml('相关节点', graphGroupedRelationsReportHtml(node), 'data-graph-detail-section="relations"')}
    ${graphReportSectionHtml('来源资料', graphSourcesReportHtml(node), 'data-graph-detail-section="sources"')}
  </article>`;
}
```

- [ ] **Step 4: Add `graphStructureReportHtml()`**

Add:

```javascript
function graphStructureReportHtml(node, digest, pairs=[]) {
  const evidence = graphNodeEvidenceItems(node, digest, 4);
  const nextSteps = graphNodeNextStepItems(node, digest, 4);
  const sourceHtml = graphSourcesReportHtml(node);
  return `<article class="graph-node-report" data-graph-report-template="candidate-structure">
    <header class="graph-report-head">
      <div class="text-[11px] text-neutral-500">${esc(graphNodeLightPath(node))}</div>
      <h2 class="graph-report-title">${esc(graphNodeTitle(node))}</h2>
      <blockquote class="graph-report-lead">${renderRichText(graphNodeDiagnosisText(node, digest, pairs))}</blockquote>
    </header>
    ${graphReportSectionHtml('为什么出现', graphReportListHtml(evidence, '这个节点来自资料结构、内容提取或导入诊断。'), 'data-graph-detail-section="structure-reason"')}
    ${graphReportSectionHtml('来源片段', sourceHtml || graphEvidenceReportHtml(node, digest), 'data-graph-detail-section="evidence"')}
    ${graphReportSectionHtml('分析状态', graphLearningNarrativeHtml(node), 'data-graph-detail-section="learning-status"')}
    ${graphReportSectionHtml('可做动作', graphReportListHtml(nextSteps, '先围绕这个节点提问，或打开来源；不要在没有证据时把它当成已学习知识点。'), 'data-graph-detail-section="strategy"')}
    ${graphReportSectionHtml('相关节点', graphGroupedRelationsReportHtml(node), 'data-graph-detail-section="relations"')}
  </article>`;
}
```

- [ ] **Step 5: Add `graphContextReportHtml()`**

Add:

```javascript
function graphContextReportHtml(node, digest, pairs=[]) {
  const evidence = graphNodeEvidenceItems(node, digest, 5);
  const sourceHtml = graphSourcesReportHtml(node);
  return `<article class="graph-node-report" data-graph-report-template="context-source">
    <header class="graph-report-head">
      <div class="text-[11px] text-neutral-500">${esc(graphNodeLightPath(node))}</div>
      <h2 class="graph-report-title">${esc(graphNodeTitle(node))}</h2>
      <blockquote class="graph-report-lead">${renderRichText(graphNodeCoverageText(node))}</blockquote>
    </header>
    ${graphReportSectionHtml('来源与覆盖范围', `<p>${esc(graphNodeCoverageText(node))}</p>`, 'data-graph-detail-section="context-coverage"')}
    ${graphReportSectionHtml('内容预览', graphReportListHtml(evidence, '这个上下文节点暂时没有长预览。'), 'data-graph-detail-section="evidence"')}
    ${graphReportSectionHtml('关联学习节点', graphGroupedRelationsReportHtml(node), 'data-graph-detail-section="relations"')}
    ${graphReportSectionHtml('打开上下文', sourceHtml, 'data-graph-detail-section="sources"')}
  </article>`;
}
```

- [ ] **Step 6: Run detail and preservation tests**

Run:

```powershell
pytest tests/test_mobile_persistence.py::test_mobile_graph_sheet_expanded_detail_reads_like_report_with_semantic_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_expanded_detail_uses_tiered_reports tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_detail_sections_and_bidirectional_node_jumps -q
```

Expected: PASS.

- [ ] **Step 7: Commit detail implementation**

Run:

```powershell
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: add tiered graph node detail reports"
```

---

### Task 5: Verification, Browser Check, And Final Cleanup

**Files:**
- Verify: `static/app/index.html`
- Verify: `tests/test_mobile_persistence.py`
- Verify: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Run focused mobile tests**

Run:

```powershell
pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: PASS.

- [ ] **Step 2: Run graph-specific grep checks**

Run:

```powershell
rg -n "graphSheetDiagnosisCompactHtml|graphNodePanelCards|data-graph-panel-card|MAX_FOCUS_GRAPH_NEIGHBORS|slice\\(0, maxNeighbors\\)" static/app/index.html tests
```

Expected:

- no `graphSheetDiagnosisCompactHtml`,
- no `graphNodePanelCards`,
- no `data-graph-panel-card`,
- no neighbor cap constants or max-neighbor slices.

- [ ] **Step 3: Use the in-app browser for a mobile visual check**

Open the running local app at `http://localhost:65144/` in the in-app browser and inspect the graph sheet at a mobile viewport if the session already has graph nodes.

Check:

- compact sheet is not blank,
- compact content fits without obvious text overlap,
- detail expansion still hides compact content,
- semantic fragment cards still appear when evidence exists,
- source/node jump buttons remain clickable.

If the app does not currently have a graph node in the browser session, use tests as the authoritative verification and report that browser verification could not cover a populated graph.

- [ ] **Step 4: Check git status**

Run:

```powershell
git status --short --branch
```

Expected: clean worktree after commits.

- [ ] **Step 5: Final report**

Report:

- commits created,
- test commands and results,
- whether browser visual verification was populated or not,
- any remaining risk.
