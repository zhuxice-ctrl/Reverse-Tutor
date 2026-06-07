# Mobile Natural Graph Relations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the mobile Focus Graph so relation count is determined by existing learning logic, not by a fixed neighbor cap or by adding extra backend data.

**Architecture:** Keep `buildGraphData()` as the only graph relation source and continue deriving links from existing client data: mastery rows, assistant `related_kps`, learning sequence, source anchors, source outlines, latent source topics, and notes. Change `buildFocusedGraphData()` from "center plus top N neighbors" to "center plus all directly connected logical neighbors"; the focus view may hide unrelated components, but it must not prune any one-hop relationship of the selected center. Do not add DB stores, backend tables, release metadata, or artificial relation records.

**Tech Stack:** Static mobile app in `static/app/index.html`, existing client graph rendering, pytest string-contract tests.

---

### Task 1: Specify Natural One-Hop Focus Behavior

**Files:**
- Modify: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Replace the fixed-cap helper contract test**

Update `test_mobile_graph_has_focus_dataset_helpers()` to assert that fixed caps are absent and one-hop links are kept by logic:

```python
def test_mobile_graph_has_focus_dataset_helpers():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "function graphFocusCenterNode(nodes=[], links=[], preferredKey='')" in html
    focus_region = html.split("function graphFocusCenterNode", 1)[1].split("function setActiveGraphDataset", 1)[0]

    assert "function buildFocusedGraphData(nodes=[], links=[], opts={})" in html
    assert "function graphFormationStateHtml(nodes=[], links=[], opts={})" in html
    assert "node.nodeType === 'kp'" in focus_region
    assert "const oneHopLinks = links.filter" in focus_region
    assert "const neighborItems = oneHopLinks.map" in focus_region
    assert "sort(graphCompareNeighbor)" in focus_region
    assert "return { nodes: focusedNodes, links: focusedLinks, center, focused:true" in focus_region
    assert "MAX_FOCUS_GRAPH_NEIGHBORS" not in focus_region
    assert "maxNeighbors" not in focus_region
    assert "slice(0, maxNeighbors)" not in focus_region
```

- [ ] **Step 2: Add a no-extra-backend-data guard**

Add this test near the graph helper tests:

```python
def test_mobile_graph_natural_relations_do_not_add_backend_storage():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]
    focus_region = html.split("function graphFocusCenterNode", 1)[1].split("function setActiveGraphDataset", 1)[0]

    assert "related_kps" in build_graph_fn
    assert "kind:'related'" in build_graph_fn
    assert "kind:'sequence'" in build_graph_fn
    assert "kind:'foundation'" in build_graph_fn
    assert "kind:'note'" in build_graph_fn
    assert "indexedDB" not in focus_region
    assert "DB.add(" not in focus_region
    assert "DB.put(" not in focus_region
    assert "objectStoreNames" not in focus_region
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_has_focus_dataset_helpers tests/test_mobile_persistence.py::test_mobile_graph_natural_relations_do_not_add_backend_storage -q
```

Expected: `test_mobile_graph_has_focus_dataset_helpers` fails because the current implementation still has `MAX_FOCUS_GRAPH_NEIGHBORS`, `maxNeighbors`, and `slice(0, maxNeighbors)`.

- [ ] **Step 4: Commit failing tests**

```powershell
git add tests/test_mobile_persistence.py
git commit -m "test: specify natural graph relation focus"
```

### Task 2: Remove Fixed Neighbor Cap From Focus Adapter

**Files:**
- Modify: `static/app/index.html`

- [ ] **Step 1: Remove fixed-cap code**

Delete:

```javascript
const MAX_FOCUS_GRAPH_NEIGHBORS = 6;
```

Inside `buildFocusedGraphData()`, remove `maxNeighbors` and change the early return:

```javascript
  const center = graphFocusCenterNode(nodes, links, opts.centerKey || '');
  if (!center) {
    return { nodes, links, center, focused:false, totalNodes:nodes.length };
  }
```

Change neighbor item collection to keep every one-hop relation:

```javascript
  const neighborItems = oneHopLinks.map(link => {
    const aKey = graphLinkEndpointKey(link, 'a');
    const bKey = graphLinkEndpointKey(link, 'b');
    const otherKey = aKey === centerKey ? bKey : aKey;
    return { link, node: nodes.find(n => String(n.key) === otherKey) };
  }).filter(item => item.node).sort(graphCompareNeighbor);
```

- [ ] **Step 2: Keep the focus banner accurate**

Leave the focused banner as "one-hop relation" language. It can still show `focus.nodes.length / focus.totalNodes`, because the view hides unrelated components but does not prune direct relations.

- [ ] **Step 3: Run focused tests and verify GREEN**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_has_focus_dataset_helpers tests/test_mobile_persistence.py::test_mobile_graph_natural_relations_do_not_add_backend_storage tests/test_mobile_product_experience.py::test_mobile_graph_canvas_uses_focus_subset_but_detail_keeps_full_dataset -q
```

Expected: all three tests pass.

- [ ] **Step 4: Commit implementation**

```powershell
git add static/app/index.html
git commit -m "fix: keep all logical one-hop graph relations"
```

### Task 3: Verify No Relationship Regression

**Files:**
- No source edits expected.

- [ ] **Step 1: Run mobile regression tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader regression tests**

Run:

```powershell
py -m pytest tests/test_engine.py tests/test_mode_skeleton.py tests/test_update_check_resilience.py tests/test_llm_provider_presets.py tests/test_websearch.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run inline JavaScript syntax verification**

Run:

```powershell
node -e "const fs=require('fs'); const files=['static/app/index.html','static/index.html']; let total=0; for (const file of files) { const html=fs.readFileSync(file,'utf8'); const scripts=[...html.matchAll(/<script\\b(?![^>]*\\bsrc=)[^>]*>([\\s\\S]*?)<\\/script>/gi)].map(m=>m[1]); let ok=0; for (const [i,code] of scripts.entries()) { try { new Function(code); ok++; } catch(e) { console.error(file+' script '+(i+1)+' failed'); console.error(e && e.stack || e); process.exit(1); } } total+=ok; console.log(file+': checked '+ok+' inline scripts'); } console.log('checked '+total+' inline scripts');"
```

Expected: all inline scripts parse.

- [ ] **Step 4: Build/install test APK and WebView-check natural one-hop behavior**

Build without changing version/update metadata:

```powershell
$env:ANDROID_HOME='C:\Users\Lenovo\AppData\Local\Android\Sdk'; $env:ANDROID_SDK_ROOT=$env:ANDROID_HOME; npm run build:apk
```

Copy to:

```powershell
release-artifacts\Reverse-Tutor-v0.19.6-natural-relations-test.apk
```

Install:

```powershell
adb install -r release-artifacts\Reverse-Tutor-v0.19.6-natural-relations-test.apk
```

In WebView, evaluate a center node with eight direct neighbors. Expected: `buildFocusedGraphData()` returns center plus all eight direct neighbors, with no `MAX_FOCUS_GRAPH_NEIGHBORS` symbol.

- [ ] **Step 5: Final status**

Report commits, tests, APK path/SHA if built, and confirm no backend data/storage/release metadata changes.

---

## Self-Review Notes

- Scope coverage: The plan directly addresses the user's correction: relation quantity comes from graph logic, not fixed rendering caps.
- Data guard: The plan explicitly prevents new backend storage or artificial relation records.
- Existing boundaries: Automatic node creation, graph node rules, diagnosis panel, evidence cards, update feed, and version metadata remain out of scope.
