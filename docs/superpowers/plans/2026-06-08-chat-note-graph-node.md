# Chat Note Graph Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build chat-note graph nodes that record learning hints from light chat as sticky notes, not mastery nodes.

**Architecture:** Reuse the existing `anchors` IndexedDB store with a new `kind: 'chat_note'`, then let `buildGraphData()` render those anchors as `nodeType: 'chat_note'`. Light chat turns persist chat notes through local extraction after the assistant reply is saved. Graph bottom sheet/report routing gets a new sticky-note template that avoids mastery, 0%, evidence-shortage, and status-panel language.

**Tech Stack:** Static mobile app in `static/app/index.html`, IndexedDB wrapper `DB`, existing graph renderer, pytest string-structure tests.

---

### Task 1: Persist Chat Notes From Light Chat

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_persistence.py`

- [ ] **Step 1: Write the failing test**

Add a test asserting that the mobile HTML contains:

```python
def test_mobile_light_chat_persists_chat_note_anchors_without_mastery():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    light_fn = html.split("async function runLightChatTurn", 1)[1].split("async function tryQueueNativeTurnEarly", 1)[0]
    extraction_region = html.split("function extractChatNoteCandidates", 1)[1].split("async function persistChatNoteAnchors", 1)[0]
    persist_region = html.split("async function persistChatNoteAnchors", 1)[1].split("function inferTurnRoute", 1)[0]

    assert "function extractChatNoteCandidates" in html
    assert "async function persistChatNoteAnchors" in html
    assert "kind: 'chat_note'" in persist_region
    assert "chat_note_title" in persist_region
    assert "chat_note_outline" in persist_region
    assert "chat_note_quote" in persist_region
    assert "privacy_level || 'standard'" in persist_region
    assert "kg_extraction_enabled === false" in persist_region
    assert "师生角色定位" in extraction_region
    assert "shadowing" in extraction_region
    assert "て形" in extraction_region
    assert "聞こえる / 聞かれる" in extraction_region
    assert "persistChatNoteAnchors(session, sid, {" in light_fn
    assert "upsert_mastery" not in light_fn
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_light_chat_persists_chat_note_anchors_without_mastery -q
```

Expected: FAIL because `extractChatNoteCandidates` is not defined.

- [ ] **Step 3: Implement persistence**

In `static/app/index.html`, add helpers before `inferTurnRoute()`.

`extractChatNoteCandidates({ userInput='', reply='', session=null }={})` returns an array of objects shaped as:

```js
{
  title: 'て形总是写乱',
  body: '你在闲聊里提到，动词变形混在一起时容易写错。',
  quote: 'する、くる 和五段动词混在一起时，我总下意识写错。',
  outline: '日语 N2 / 语法 / 动词变形',
  keywords: ['て形', '动词变形'],
}
```

`persistChatNoteAnchors(session, sid, { userInput='', reply='', userMessageId=null, assistantMessageId=null }={})` writes each candidate to `anchors` unless a same-title `chat_note` already exists in the same session.

The helpers must:

- respect `settings.kg_extraction_enabled !== false`;
- skip strict privacy unless there is an explicit learning phrase;
- block role meta topics such as `师生角色定位`;
- extract high-value terms such as `て形`, `shadowing`, `聞こえる / 聞かれる`, `N2 听力快语速`;
- store anchors as `kind: 'chat_note'`;
- avoid writing mastery.

Call `persistChatNoteAnchors()` in `runLightChatTurn()` after the assistant message is saved.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_persistence.py::test_mobile_light_chat_persists_chat_note_anchors_without_mastery -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add static/app/index.html tests/test_mobile_persistence.py
git commit -m "feat: persist chat note anchors from light chat"
```

### Task 2: Render Chat Notes As Sticky Graph Nodes

**Files:**
- Modify: `static/app/index.html`
- Test: `tests/test_mobile_product_experience.py`

- [ ] **Step 1: Write the failing test**

Add a test asserting that graph generation and panels route chat notes separately:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_chat_note_graph_nodes_use_sticky_note_template -q
```

Expected: FAIL because `graphChatNoteCompactHtml` is not defined.

- [ ] **Step 3: Implement graph rendering**

Modify `buildGraphData()` to convert `chat_note` anchors to graph nodes:

```js
const chatNotes = anchors.filter(a => a.kind === 'chat_note');
const chatNoteNode = {
  key: `chat-note-${note.id || i}`,
  nodeType:'chat_note',
  kp: note.chat_note_title || note.content || '闲聊便签',
  label: note.chat_note_title || note.content || '闲聊便签',
  content: note.chat_note_body || note.content || '',
  outlinePath: note.chat_note_outline || '',
  quote: note.chat_note_quote || '',
  messageId: note.chat_note_user_message_id || note.chat_note_assistant_message_id || null,
};
```

Add `chat_note` labels to `graphNodeTypeLabel()`, `graphLinkKindLabel()`, `graphRelationGroupLabel()`, `graphNodeSheetTemplate()`, and `graphFocusNodeRank()`.

Add `graphChatNoteCompactHtml()` and `graphChatNoteReportHtml()` and route them from `graphSheetCompactHtml()` / `graphSheetReportHtml()`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_mobile_product_experience.py::test_mobile_chat_note_graph_nodes_use_sticky_note_template -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add static/app/index.html tests/test_mobile_product_experience.py
git commit -m "feat: render chat notes as graph sticky notes"
```

### Task 3: Verify Mobile App and Install APK

**Files:**
- Modify: none beyond generated mobile sync output

- [ ] **Step 1: Run focused and mobile regression tests**

Run:

```bash
pytest tests/test_mobile_persistence.py tests/test_mobile_product_experience.py -q
```

Expected: all collected tests pass.

- [ ] **Step 2: Run static JS syntax check**

Run:

```bash
node -e "const fs=require('fs');const html=fs.readFileSync('static/app/index.html','utf8');const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);for(const [i,s] of scripts.entries()){new Function(s);console.log('script '+(i+1)+' ok')}"
```

Expected: all script blocks print `ok`.

- [ ] **Step 3: Sync, build, and install**

Run:

```bash
cd mobile
npm run sync
cd android
.\gradlew.bat assembleRelease
cd ..\..
adb install -r mobile\android\app\build\outputs\apk\release\app-release.apk
adb shell monkey -p com.reversetutor.app -c android.intent.category.LAUNCHER 1
```

Expected: sync succeeds, Gradle succeeds, install prints `Success`.

- [ ] **Step 4: Verify on-device data path**

Use WebView DevTools to create or inspect chat note anchors and confirm:

```js
(await DB.bySid('anchors', state.sid)).filter(a => a.kind === 'chat_note')
```

Expected: learning-related light-chat phrases can appear as `chat_note` anchors, while role-meta topics do not.

- [ ] **Step 5: Final commit if sync changed tracked source**

If only Android line-ending files are dirty, leave them uncommitted. If source or tests changed after verification, commit them with:

```bash
git add static/app/index.html tests/test_mobile_persistence.py tests/test_mobile_product_experience.py
git commit -m "test: verify chat note graph nodes"
```
