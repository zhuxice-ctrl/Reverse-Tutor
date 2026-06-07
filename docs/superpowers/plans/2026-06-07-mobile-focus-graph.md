# Mobile Focus Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first Focus Graph that renders the selected node plus its strongest one-hop learning relations, while keeping the full graph data available for the node sheet and detail page.

**Architecture:** Keep `buildGraphData()` as the canonical learning-structure graph builder. Add a small focused-view adapter between graph data construction and `ForceGraph.setData()`: `setActiveGraphDataset()` stores the full dataset for detail navigation, while the canvas receives `buildFocusedGraphData(...).nodes/links`. Add concise empty/forming state markup inside the graph containers for no-node and one/two-node sessions.

**Tech Stack:** Static mobile app in `static/app/index.html`, existing IndexedDB-backed graph data flow, existing Python pytest string-contract tests.

---

### Task 1: Specify Focus Graph Helpers

**Files:**
- Modify: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Write the failing helper contract test**

Add this test near the existing mobile graph tests:

```python
def test_mobile_graph_has_focus_dataset_helpers():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    focus_region = html.split("function graphFocusCenterNode", 1)[1].split("function setActiveGraphDataset", 1)[0]

    assert "const MAX_FOCUS_GRAPH_NEIGHBORS = 6" in html
    assert "function graphFocusCenterNode(nodes=[], links=[], preferredKey='')" in html
    assert "function buildFocusedGraphData(nodes=[], links=[], opts={})" in html
    assert "function graphFormationStateHtml(nodes=[], links=[], opts={})" in html
    assert "node.nodeType === 'kp'" in focus_region
    assert "const oneHopLinks = links.filter" in focus_region
    assert "slice(0, maxNeighbors)" in focus_region
    assert "return { nodes: focusedNodes, links: focusedLinks, center, focused:true" in focus_region
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_has_focus_dataset_helpers -q
```

Expected: FAIL because `graphFocusCenterNode` is not defined yet.

- [ ] **Step 3: Commit the failing test**

```powershell
git add tests/test_mobile_persistence.py
git commit -m "test: specify mobile focus graph helpers"
```

### Task 2: Specify Focused Rendering Without Losing Detail Data

**Files:**
- Modify: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Write the failing render wiring test**

Add this test near `test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields`:

```python
def test_mobile_graph_canvas_uses_focus_subset_but_detail_keeps_full_dataset():
    html = mobile_html()
    context_graph_fn = html.split("async function renderContextGraph", 1)[1].split("async function renderContextAnchors", 1)[0]
    insights_fn = html.split("async function renderInsights", 1)[1].split("// --- Settings ---", 1)[0]

    assert "setActiveGraphDataset(nodes, links);" in context_graph_fn
    assert "const focused = buildFocusedGraphData(nodes, links, { centerKey: state.graphSelected });" in context_graph_fn
    assert "ForceGraph.setData(focused.nodes, focused.links);" in context_graph_fn
    assert "graphFormationStateHtml(nodes, links, { context: 'session', focus: focused })" in context_graph_fn

    assert "setActiveGraphDataset(allNodes, allLinks);" in insights_fn
    assert "const focused = buildFocusedGraphData(allNodes, allLinks, { centerKey: state.graphSelected });" in insights_fn
    assert "ForceGraph.setData(focused.nodes, focused.links);" in insights_fn
    assert "graphFormationStateHtml(allNodes, allLinks, { context: 'global', focus: focused })" in insights_fn
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
py -m pytest tests/test_mobile_product_experience.py::test_mobile_graph_canvas_uses_focus_subset_but_detail_keeps_full_dataset -q
```

Expected: FAIL because both render paths still pass full datasets directly to `ForceGraph.setData()`.

- [ ] **Step 3: Commit the failing test**

```powershell
git add tests/test_mobile_product_experience.py
git commit -m "test: specify mobile focus graph rendering"
```

### Task 3: Implement Focus Dataset Adapter and Forming State

**Files:**
- Modify: `static/app/index.html`

- [ ] **Step 1: Add forming-state CSS**

Add styles near `.graph-hint`:

```css
  .graph-focus-banner {
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 12px;
    z-index: 2;
    pointer-events: none;
    border: 1px solid rgba(148, 163, 184, .18);
    background: color-mix(in srgb, var(--panel) 88%, transparent);
    color: var(--muted);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 12px;
    line-height: 1.45;
    box-shadow: 0 12px 34px rgba(0, 0, 0, .2);
  }
  .graph-focus-banner strong {
    display: block;
    color: var(--text);
    font-size: 13px;
    font-weight: 650;
    margin-bottom: 2px;
  }
  .graph-focus-banner[data-graph-state="empty"] {
    top: 50%;
    bottom: auto;
    transform: translateY(-50%);
    text-align: center;
  }
```

- [ ] **Step 2: Add helper functions before `setActiveGraphDataset()`**

Insert after `buildGraphData()`:

```javascript
const MAX_FOCUS_GRAPH_NEIGHBORS = 6;

function graphLinkEndpointKey(link, side) {
  const node = link?.[side] || link?.[side === 'a' ? 'source' : 'target'];
  return String(node?.key || '');
}

function graphFocusNodeRank(node) {
  const typeRank = node?.nodeType === 'kp' ? 0
    : node?.nodeType === 'latent' ? 1
    : node?.nodeType === 'section' ? 2
    : node?.nodeType === 'source' ? 3
    : node?.nodeType === 'diagnostic' ? 4
    : node?.nodeType === 'note' ? 5
    : 9;
  const levelRank = -Number(node?.level || 0);
  const recencyRank = -Number(node?.updated_at || node?.created_at || 0);
  return [typeRank, levelRank, recencyRank, graphNodeTitle(node)];
}

function graphCompareRank(a, b) {
  const ar = graphFocusNodeRank(a);
  const br = graphFocusNodeRank(b);
  for (let i = 0; i < ar.length; i++) {
    if (ar[i] < br[i]) return -1;
    if (ar[i] > br[i]) return 1;
  }
  return 0;
}

function graphFocusCenterNode(nodes=[], links=[], preferredKey='') {
  const preferred = nodes.find(n => String(n.key) === String(preferredKey || ''));
  if (preferred) return preferred;
  return [...nodes].sort(graphCompareRank)[0] || null;
}

function graphNeighborRank(item) {
  const kindRank = item.link?.kind === 'related' ? 0
    : item.link?.kind === 'sequence' ? 1
    : item.link?.kind === 'foundation' ? 2
    : item.link?.kind === 'note' ? 3
    : item.link?.kind === 'outline' ? 4
    : item.link?.kind === 'diagnostic' ? 5
    : 9;
  return [kindRank, -Number(item.link?.weight || 0), ...graphFocusNodeRank(item.node)];
}

function graphCompareNeighbor(a, b) {
  const ar = graphNeighborRank(a);
  const br = graphNeighborRank(b);
  for (let i = 0; i < ar.length; i++) {
    if (ar[i] < br[i]) return -1;
    if (ar[i] > br[i]) return 1;
  }
  return 0;
}

function buildFocusedGraphData(nodes=[], links=[], opts={}) {
  const maxNeighbors = Math.max(1, Number(opts.maxNeighbors || MAX_FOCUS_GRAPH_NEIGHBORS));
  const center = graphFocusCenterNode(nodes, links, opts.centerKey || '');
  if (!center || nodes.length <= maxNeighbors + 1) {
    return { nodes, links, center, focused:false, totalNodes:nodes.length };
  }
  const centerKey = String(center.key || '');
  const oneHopLinks = links.filter(link => graphLinkEndpointKey(link, 'a') === centerKey || graphLinkEndpointKey(link, 'b') === centerKey);
  const neighborItems = oneHopLinks.map(link => {
    const aKey = graphLinkEndpointKey(link, 'a');
    const bKey = graphLinkEndpointKey(link, 'b');
    const otherKey = aKey === centerKey ? bKey : aKey;
    return { link, node: nodes.find(n => String(n.key) === otherKey) };
  }).filter(item => item.node).sort(graphCompareNeighbor).slice(0, maxNeighbors);
  const keep = new Set([centerKey, ...neighborItems.map(item => String(item.node.key))]);
  const focusedNodes = nodes.filter(node => keep.has(String(node.key)));
  const focusedLinks = links.filter(link => keep.has(graphLinkEndpointKey(link, 'a')) && keep.has(graphLinkEndpointKey(link, 'b')));
  return { nodes: focusedNodes, links: focusedLinks, center, focused:true, totalNodes:nodes.length };
}

function graphFormationStateHtml(nodes=[], links=[], opts={}) {
  const count = Array.isArray(nodes) ? nodes.length : 0;
  const context = opts.context === 'global' ? 'global' : 'session';
  const focus = opts.focus || {};
  if (!count) {
    const text = context === 'global'
      ? '开始对话、导入资料或保存随笔后，这里会形成学习图谱。'
      : '继续对话、导入资料或保存随笔后，这里会形成学习图谱。';
    return `<div class="graph-focus-banner" data-graph-state="empty"><strong>图谱正在形成</strong>${text}</div>`;
  }
  if (count <= 2) {
    const title = focus.center ? graphNodeTitle(focus.center) : '当前节点';
    return `<div class="graph-focus-banner" data-graph-state="forming"><strong>${esc(title)}</strong>图谱正在形成 · ${count} 个节点</div>`;
  }
  if (focus.focused && focus.totalNodes > focus.nodes.length) {
    return `<div class="graph-focus-banner" data-graph-state="focused"><strong>${esc(graphNodeTitle(focus.center))}</strong>已聚焦一跳关系 · ${focus.nodes.length}/${focus.totalNodes} 个节点</div>`;
  }
  return '';
}
```

- [ ] **Step 3: Wire `renderContextGraph()`**

Replace the no-node direct empty block with a graph container plus empty banner, then render focused data for non-empty sessions:

```javascript
  if (!masteries.length && !anchors.length) {
    setActiveGraphDataset([], []);
    ForceGraph.destroy();
    body.innerHTML = '<div id="context-knowledge-graph" class="knowledge-graph knowledge-graph-fullscreen">' + graphFormationStateHtml([], [], { context: 'session' }) + '</div>';
    return;
  }
```

After `setActiveGraphDataset(nodes, links);`, add:

```javascript
  const focused = buildFocusedGraphData(nodes, links, { centerKey: state.graphSelected });
```

Replace:

```javascript
  ForceGraph.setData(nodes, links);
```

with:

```javascript
  ForceGraph.setData(focused.nodes, focused.links);
  $('#context-knowledge-graph')?.insertAdjacentHTML('beforeend', graphFormationStateHtml(nodes, links, { context: 'session', focus: focused }));
```

- [ ] **Step 4: Wire `renderInsights()`**

Replace the all-node empty state with:

```javascript
    mastDiv.innerHTML = '<div id="knowledge-graph" class="knowledge-graph knowledge-graph-fullscreen">' + graphFormationStateHtml([], [], { context: 'global' }) + '</div>';
```

Before `ForceGraph.setData(...)`, add:

```javascript
    const focused = buildFocusedGraphData(allNodes, allLinks, { centerKey: state.graphSelected });
```

Replace:

```javascript
    ForceGraph.setData(allNodes, allLinks);
```

with:

```javascript
    ForceGraph.setData(focused.nodes, focused.links);
    container.querySelector('.graph-focus-banner')?.remove();
    container.insertAdjacentHTML('beforeend', graphFormationStateHtml(allNodes, allLinks, { context: 'global', focus: focused }));
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_has_focus_dataset_helpers tests/test_mobile_product_experience.py::test_mobile_graph_canvas_uses_focus_subset_but_detail_keeps_full_dataset -q
```

Expected: PASS.

- [ ] **Step 6: Commit the implementation**

```powershell
git add static/app/index.html
git commit -m "feat: focus mobile graph canvas"
```

### Task 4: Regression Coverage and App Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused mobile graph regression tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader app regression tests**

Run:

```powershell
py -m pytest tests/test_engine.py tests/test_mode_skeleton.py tests/test_update_check_resilience.py tests/test_llm_provider_presets.py tests/test_websearch.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run inline JavaScript syntax verification**

Run the existing inline script checker command used by the project. Expected: all inline scripts parse without syntax errors.

- [ ] **Step 4: Build and install a test APK**

Build a local test APK without changing release/update metadata. Install it on the connected device.

Expected: `adb shell dumpsys package ...` reports the same `versionName/versionCode` as the local build target, and installation succeeds.

- [ ] **Step 5: WebView seeded verification**

Seed a session with more than seven graph nodes and evaluate the new helpers in WebView:

```javascript
const graph = buildGraphData(masteries, ai, anchors);
const focused = buildFocusedGraphData(graph.nodes, graph.links, {});
({
  allNodes: graph.nodes.length,
  focusedNodes: focused.nodes.length,
  centered: !!focused.center,
  respectsLimit: focused.nodes.length <= MAX_FOCUS_GRAPH_NEIGHBORS + 1,
  emptyState: graphFormationStateHtml([], [], { context: 'session' }).includes('data-graph-state="empty"'),
  formingState: graphFormationStateHtml(graph.nodes.slice(0, 1), [], { context: 'session', focus: { center: graph.nodes[0] } }).includes('data-graph-state="forming"')
});
```

Expected: `allNodes > focusedNodes`, `respectsLimit === true`, and both state checks are true.

- [ ] **Step 6: Final status**

Summarize commits, tests, APK path/SHA if built, and any residual risk. Do not claim completion until the verification commands above have been run and read.

---

## Self-Review Notes

- Spec coverage: This plan covers Focus Graph selection, one-hop limiting, detail-data preservation, no-node state, one/two-node forming state, and regression verification.
- Scope guard: It does not add subject/module/chapter taxonomy, does not change node creation sources, does not remove the existing diagnosis/evidence detail cards, and does not modify release/update metadata.
- Placeholder scan: No unresolved placeholders remain; the APK and WebView commands are intentionally environment-specific verification steps because they depend on the connected Android build tooling and device state.
