# Mobile Graph Node Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep automatic graph node creation for learning sessions, while removing field-like learning digest nodes from the mobile graph canvas.

**Architecture:** Leave the current `mastery`-driven graph source intact so opening turns and normal learning turns still create `kp` nodes automatically. Keep `buildKpMemoryDigests()` as a diagnosis data source, but stop `buildGraphData()` from converting digest rows such as evidence summary, source, and next step into `nodeType:'insight'` graph nodes. The bottom sheet and expanded detail continue to read `buildKpConversationDigest()` / semantic fragments for evidence and next-step cards.

**Tech Stack:** Static HTML/JavaScript in `static/app/index.html`, pytest text-contract tests in `tests/test_mobile_persistence.py` and `tests/test_mobile_product_experience.py`, Capacitor Android APK packaging.

---

## Scope Check

This plan covers one behavior layer: mobile graph node birth rules. It does not introduce a subject/module/chapter taxonomy, does not change LLM prompts, does not publish release metadata, and does not remove the diagnosis-first bottom sheet.

## File Structure

- Modify `tests/test_mobile_persistence.py`
  - Replace the old contract that required `nodeType:'insight'` digest nodes.
  - Add a contract that digest data remains available but is not appended to graph `nodes` or `links`.
  - Keep the panel contract that evidence, stuck point, next step, source, and semantic fragment cards remain available.
- Modify `tests/test_mobile_product_experience.py`
  - Add a product-level guard that field labels like `证据摘要`, `已有入口`, and `下一步` are not born as graph nodes.
- Modify `static/app/index.html`
  - Keep `buildKpMemoryDigests(ai, byKp)`.
  - Remove the `for (const digest of buildKpMemoryDigests(...))` node/link creation block from `buildGraphData()`.
  - Leave `buildKpConversationDigest()`, `graphNodePanelCards()`, `graphSemanticFragments()`, and `graphSheetDiagnosisCompactHtml()` intact.
- Build output only:
  - `release-artifacts/Reverse-Tutor-v0.19.6-node-rules-test.apk`

---

### Task 1: Replace The Old Insight-Node Test Contract

**Files:**
- Modify: `tests/test_mobile_persistence.py`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Change the old digest-node test into a digest-data test**

Replace `test_mobile_graph_organizes_chat_turns_into_learning_digest_nodes` with:

```python
def test_mobile_graph_keeps_learning_digest_data_out_of_canvas_nodes():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]

    assert "function buildKpMemoryDigests" in html
    assert "insightType:'error'" in html
    assert "insightType:'evidence'" in html
    assert "insightType:'next_step'" in html
    assert "chatMessageIds: ids" in html
    assert "nodeType:'insight'" not in build_graph_fn
    assert "kind:'memory'" not in build_graph_fn
    assert "chatMessageIds: digest.chatMessageIds" not in build_graph_fn
    assert "content:msg.content" not in html
    assert "nodeType: count%5===0?'support':'memory'" not in html
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_keeps_learning_digest_data_out_of_canvas_nodes -v
```

Expected: FAIL because `buildGraphData()` still creates `nodeType:'insight'` and `kind:'memory'` links.

- [ ] **Step 3: Commit the failing test**

Run:

```powershell
git add tests/test_mobile_persistence.py
git commit -m "test: specify mobile graph digest fields stay off canvas"
```

---

### Task 2: Guard The Product-Level Node Birth Rule

**Files:**
- Modify: `tests/test_mobile_product_experience.py`
- Test: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Add a product-level string contract**

Add this test near the existing mobile graph product tests:

```python
def test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    build_graph_fn = html.split("function buildGraphData", 1)[1].split("function memoryStatusLabel", 1)[0]
    panel_fn = html.split("function graphNodePanelCards", 1)[1].split("function graphNodePrimaryActionsHtml", 1)[0]

    assert "nodeType:'kp'" in build_graph_fn
    assert "nodeType:'latent'" in build_graph_fn
    assert "nodeType:'note'" in build_graph_fn
    assert "nodeType:'source'" in build_graph_fn
    assert "nodeType:'section'" in build_graph_fn
    assert "nodeType:'insight'" not in build_graph_fn
    assert "label:'证据摘要'" in html
    assert "label:'下一步'" in panel_fn
    assert "entryStatusLabel" in html
    assert "已有入口" in html
```

This deliberately allows field labels to exist in digest or panel code while preventing them from becoming graph nodes.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
py -m pytest tests/test_mobile_product_experience.py::test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields -v
```

Expected: FAIL because `buildGraphData()` still contains `nodeType:'insight'`.

- [ ] **Step 3: Commit the failing test**

Run:

```powershell
git add tests/test_mobile_product_experience.py
git commit -m "test: specify graph nodes are learning structure"
```

---

### Task 3: Remove Field-Like Insight Nodes From `buildGraphData`

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`, `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Remove the digest node/link creation block**

In `static/app/index.html`, inside `function buildGraphData(masteries, ai, anchors=[])`, delete this block:

```javascript
  for (const digest of buildKpMemoryDigests(ai, byKp)) {
    const parent = byKp.get(digest.kp);
    if (!parent) continue;
    const insight = {
      key: digest.key,
      nodeType:'insight',
      insightType: digest.insightType,
      kp: digest.kp,
      label: digest.label,
      summary: digest.summary,
      chatMessageIds: digest.chatMessageIds,
      meta: { action: { type:'recap', knowledge_point: digest.kp } },
    };
    nodes.push(insight);
    links.push({ a:parent, b:insight, weight:1.1, kind:'memory' });
  }
```

Do not delete `buildKpMemoryDigests()` itself. The digest remains useful as structured data and as a future source for diagnosis UI.

- [ ] **Step 2: Run focused graph node-rule tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_graph_keeps_learning_digest_data_out_of_canvas_nodes tests/test_mobile_product_experience.py::test_mobile_graph_nodes_come_from_learning_structure_not_panel_fields -v
```

Expected: PASS.

- [ ] **Step 3: Commit the implementation**

Run:

```powershell
git add static/app/index.html
git commit -m "fix: keep learning digest fields off graph canvas"
```

---

### Task 4: Preserve Diagnosis Panel Evidence And Existing Auto Nodes

**Files:**
- Modify only if tests expose a regression:
  - `static/app/index.html`
  - `tests/test_mobile_persistence.py`
- Test:
  - `tests/test_mobile_persistence.py`
  - `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Run graph panel and opening-node tests**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py::test_mobile_study_opening_turn_creates_initial_graph_node_source tests/test_mobile_persistence.py::test_mobile_graph_sheet_compact_panel_is_diagnosis_first_with_six_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_diagnosis_panel_preserves_existing_semantic_cards tests/test_mobile_persistence.py::test_mobile_graph_sheet_expanded_detail_reads_like_report_with_semantic_cards -v
```

Expected: PASS. These tests prove automatic opening nodes still exist and the bottom sheet still carries diagnosis/evidence UI.

- [ ] **Step 2: Run affected mobile test suites**

Run:

```powershell
py -m pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run broader regression tests**

Run:

```powershell
py -m pytest tests/test_engine.py tests/test_mode_skeleton.py tests/test_update_check_resilience.py tests/test_llm_provider_presets.py tests/test_websearch.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Check inline script syntax**

Run:

```powershell
node -e "const fs=require('fs'); const html=fs.readFileSync('static/app/index.html','utf8'); const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]); for (const [i,s] of scripts.entries()) new Function(s); console.log('checked '+scripts.length+' inline scripts');"
```

Expected: prints `checked <n> inline scripts` and exits with code 0.

---

### Task 5: Build, Install, And Verify On Device

**Files:**
- Build output:
  - `release-artifacts/Reverse-Tutor-v0.19.6-node-rules-test.apk`

- [ ] **Step 1: Build APK**

Run:

```powershell
$env:ANDROID_HOME='C:\Users\Lenovo\AppData\Local\Android\Sdk'
npm run build:apk
```

from:

```text
C:\Users\Lenovo\.config\superpowers\worktrees\reverse-tutor\knowledge-node-panel\mobile
```

Expected: Gradle prints `BUILD SUCCESSFUL`.

- [ ] **Step 2: Copy APK artifact and hash it**

Run:

```powershell
$src='C:\Users\Lenovo\.config\superpowers\worktrees\reverse-tutor\knowledge-node-panel\mobile\android\app\build\outputs\apk\release\app-release.apk'
$dst='C:\Users\Lenovo\.config\superpowers\worktrees\reverse-tutor\knowledge-node-panel\release-artifacts\Reverse-Tutor-v0.19.6-node-rules-test.apk'
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
Copy-Item -LiteralPath $src -Destination $dst -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $dst
```

Expected: file exists and SHA-256 is printed.

- [ ] **Step 3: Install APK**

Run:

```powershell
$adb='C:\Users\Lenovo\AppData\Local\Android\Sdk\platform-tools\adb.exe'
$apk='C:\Users\Lenovo\.config\superpowers\worktrees\reverse-tutor\knowledge-node-panel\release-artifacts\Reverse-Tutor-v0.19.6-node-rules-test.apk'
& $adb install -r -d $apk
& $adb shell dumpsys package com.reversetutor.app | Select-String -Pattern 'versionCode|versionName'
```

Expected: `Success`, `versionName=0.19.6`, and `versionCode=45`.

- [ ] **Step 4: Verify WebView graph nodes**

Use CDP to create or inspect a learning session with several learning turns. The verification JSON must show:

```json
{
  "hasKpNode": true,
  "insightNodes": 0,
  "fieldLabelsAsNodes": [],
  "diagnosisCards": 6
}
```

If temporary verification sessions are created, delete them through `ENGINE.delete_session()` before finishing.

---

## Self-Review

**Spec coverage:** This plan keeps automatic learning nodes through `mastery`, preserves the diagnosis panel and semantic evidence deck, and removes field-like digest nodes from the graph canvas. It explicitly avoids adding subject/module/chapter taxonomy.

**Placeholder scan:** The plan contains concrete test code, exact file names, exact commands, and expected outcomes. It does not rely on TBD/TODO placeholders.

**Type consistency:** `buildKpMemoryDigests`, `buildGraphData`, `graphNodePanelCards`, and `nodeType:'insight'` are referenced with their current names. The tests split the same function regions used by existing pytest contracts.
