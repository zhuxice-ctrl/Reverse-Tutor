# Codex 交接文档 · Reverse Tutor（反转家教）

> 配套 `AGENTS.md`（硬规则）。本文件给完整背景：架构、技术细节、测试方向、踩过的坑。
> 用户的工作流：**实机测 v0.18.0 APK → 反馈问题 → 先让 Codex 修 → 回归测试**。本文档就是让你（Codex）修得准、不返工。

---

## 1. 项目是什么

「反转家教」：AI 扮演**不会的学生**，让用户（真人）通过"教 AI"来巩固知识。核心是一套**学生角色 + 学习状态机**：

- **学生角色**：`clue_student`（线索型，请教口吻）/ `probing_student`（追问型）/ `scaffold_student`（脚手架型）/ examiner（考核）等。
- **学习状态**：掌握度 `mastery`、置信度、错题 `error_log`、到期复习 `next_review_at`（1/3/7/14 天阶梯）。
- **知识图谱**：概念/前置/错因/误解/偏好节点 + 边，注入 prompt 做个性化。
- **资料检索**：本地文档 FTS 检索 + （可选）联网搜索，作为"线索"喂给线索型学生，并带来源引用。

---

## 2. 架构：两份独立实现（务必先懂）

### 2A. Python 后端（`tests/` 覆盖在此）
FastAPI + SQLAlchemy + SQLite。是"参考实现 / 开发主线 / 测试基线"。

| 文件 | 职责 |
|---|---|
| `server.py` | FastAPI 路由（sessions / chat / documents / images / memory / sources …） |
| `engine.py` | 核心：`run_turn()` 评估→决策→行动；prompt 构建；掌握度/复习/错题更新 |
| `db.py` | ORM 模型 + CRUD + FTS5 虚表 + schema 轻量迁移（`ensure_schema`） |
| `retrieval.py` | `Hit` / `Retriever` 协议 / `FTSRetriever` / `HybridRetriever` / `make_default_retriever` |
| `websearch.py` | 联网搜索可注入抽象：`WebHit` / `WebSearchProvider` / `Null`/`Mock`/`Http` + `get_web_search_provider()` |
| `kg_extractor.py` `kg_retriever.py` `kg_gate.py` | 知识图谱：抽取 / 检索注入 / 内容闸门 |
| `llm.py` | LLM 调用封装（`chat_json` 等），测试时被 mock |
| `chunker.py` | 文档分块（`chunk_text`） |

### 2B. 客户端 PWA（APK 打包的就是它）
`static/app/index.html`，**单文件 ~441KB**，内含：
- 一套 **JS 版引擎**：`chat_json` / `chat_json_eval_only` / 评估·动作·`knowledge_point` 逻辑、prompt 模板、离线 mock。
- **直连 LLM**（前端有 provider 预设：GLM/Kimi/OpenRouter/Ollama/LMStudio…，配置页可填 base_url/key）。
- **客户端知识图谱**：canvas 渲染、节点详情弹窗、编辑保存（`.knowledge-graph`）。
- `web_search_enabled` 等设置项也在前端复制了一份。
- V2.3 我加了 `renderCitedSources(message, meta)`：读 `message.cited_sources` 或 `meta.cited_sources`，无来源时返回 `''`（已做降级，不会报错）。

> **关键判断**：用户反馈的现象如果是**实机 APK 上的行为**（角色口吻、UI、图谱画布、离线对话），99% 要改 `static/app/index.html` 的 JS；如果是 **API/数据/检索/后端测试**，改 Python。两边都涉及时要同步改并说明。

### 2C. 移动端打包链（Capacitor）
```
static/app/  --(mobile/sync-web.js)-->  mobile/www/  --(cap sync)-->  mobile/android/app/src/main/assets/public/
```
- `mobile/capacitor.config.json`：`appId=com.reversetutor.app`，`appName=反转家教`。
- 还有 `mobile/android/.../BackgroundLlmService.java`：安卓后台 LLM 服务 + fallback JSON，schema 要和前端引擎对齐。

---

## 3. 重新打 APK 的标准流程

环境已就绪：JDK 17、Android SDK（`local.properties` 已设 `sdk.dir`）、`release.jks`、`gradlew`。版本在 `mobile/android/app/build.gradle`（`versionName`/`versionCode`）和 `mobile/package.json`。

```powershell
# 1) 同步 web 资产
#    cwd = F:\xw\reverse-tutor\mobile
npm run sync                      # = node sync-web.js && cap sync android

# 2) 编译签名 release（cwd = mobile\android）
gradlew.bat assembleRelease       # 产物: app/build/outputs/apk/release/app-release.apk

# 3) 校验签名（必须匹配，否则不能覆盖安装）
$apksigner = "$env:LOCALAPPDATA\Android\Sdk\build-tools\34.0.0\apksigner.bat"
& $apksigner verify --print-certs <apk>
#   必须含: DN: CN=Reverse Tutor, OU=App, O=ReverseTeacher, L=CN, ST=CN, C=CN
#           SHA-256: d21ff63c6b75494dd2229caccd6977ec763c8b17d95807ff1d7c455d39ac41c2

# 4) 复制重命名
Copy-Item app-release.apk ..\..\Reverse-Tutor-v{versionName}.apk
```
**签名铁律**（见 `mobile/BUILD_APK.md`）：固定用 `release.jks` + alias `reverse-tutor`，不重新生成、不发 debug 包、不改 `applicationId`，否则老用户无法覆盖升级。

---

## 4. 技术细节：本轮（V2.x）我在后端做了什么

> 这些是 **Python 后端** 的实现，作为 spec 基准；若要把同等能力做进 APK，需要在 `static/app/index.html` 的 JS 引擎里对齐。

### 4.1 引用白名单机制（`engine.run_turn`，最易出 bug）
- 线索型/脚手架学生回合，向 prompt 注入 `_format_citable_clues(hits)`，每条带 `[chunk_id=N]`。
- LLM 返回 `cited_chunk_ids`，引擎**只保留命中"已注入 chunk 白名单"的 id**，伪造的进 `citation_meta.clue_fake_citation`。
- `injected_chunk_ids` 为空 + 检索尝试过 → 标 `clue_no_local_doc`。
- 结果写进 assistant message 的 `meta.cited_chunk_ids`。

### 4.2 HybridRetriever（V2.3 "更强本地索引"）
`retrieval.py`：在 FTS bm25 内容得分上叠加**标题词命中加权** `TITLE_BOOST(=2.0) * 命中词/总词`，并按文档去重（`per_doc` 上限）。`make_default_retriever()` 返回它；`FTSRetriever` 保留兼容；`run_turn(retriever=...)` 可注入。

### 4.3 联网搜索（V2.3，可注入 + mock）
`websearch.py`：
- `WebSearchProvider` 协议；`NullWebSearchProvider`（默认，返回 `[]`）；`MockWebSearchProvider(hits)`（测试用）；`HttpWebSearchProvider`（仅当 `WEB_SEARCH_API_KEY`+`WEB_SEARCH_ENDPOINT` 都配置才发请求，全程 try/except + 8s 超时）。
- `get_web_search_provider()` 看 `WEB_SEARCH_PROVIDER` 环境变量，默认 Null。
- 集成：`DEFAULT_STRATEGY_SETTINGS["web_search_enabled"]=False`；`run_turn(web_search=None)`；仅当**本地检索无命中**且开关开时回退联网，结果以 `source_type="web"` 导入会话文档，复用 §4.1 引用机制。**测试用 Mock，绝不真实联网。**

### 4.4 来源展示（V2.3）
- `db.resolve_cited_chunks(db, chunk_ids)` → `[{chunk_id, doc_id, title, source_type, source_uri, snippet}]`（本地/联网文档通用，缺失 id 跳过）。
- `GET /api/sessions/{sid}/messages/{mid}/sources`；chat 响应加 `cited_sources`。
- 前端 `renderCitedSources` 渲染（见 §2B）。

### 4.5 知识图谱后端（V2.1/2.2/2.4/2.5）
- `kg_nodes`/`kg_edges` 两表，边支持 `valid_from`/`invalidated_at`/`superseded` 时间演化；`source_episode_ids` 溯源。
- `kg_gate.py` 抽取前四级过闸：开关 / 无 KP / 敏感词黑名单 / strict 需学习证据。
- 一致性测试 `tests/test_kg_consistency.py`（多会话隔离 / 重复抽取幂等 / 失效覆盖 / 学习状态↔图谱）。
- **修过的真实 bug**：`db.upsert_kg_node` 的"复活分支"在 `autoflush=False` 下漏了 `db.flush()`，导致同事务内重激活失效节点查不到——补一行 flush 即可（教训：新建/复活两条分支的 flush 行为要一致）。

> 注意：以上 KG/websearch **在 CHANGELOG 里仍是 `Unreleased`**，**不在 v0.18.0 APK 里**。APK 客户端用的是自己的 JS 图谱实现。

---

## 5. 测试规范（怎么写、怎么跑）

`tests/conftest.py` 已提供：
- **自动 mock LLM**：import 前清空 `LLM_*` 环境变量 + `llm._HAS_REAL=False`；每个测试临时 SQLite。
- `fresh_db`（autouse）：每个用例 drop+create 全表 + seed 内置模板 + 复位 LLM。
- `db_sess` fixture：给一个干净的 `db.SessionLocal()`。

**Mock 单轮 LLM 输出**（最常用）：
```python
async def fake_chat_json(system, messages, **kwargs):
    return {"reply": "...", "evaluation": {...}, "action": {"student_role": "clue_student",
            "knowledge_point": "...", ...}, "cited_chunk_ids": [<注入的chunk_id>]}
monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)
```

**HTTP 端点测试**（httpx ASGI，无需起服务）：
```python
import httpx
from server import app
transport = httpx.ASGITransport(app=app)
async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
    r = await c.post(f"/api/sessions/{sid}/chat", json={"message": "..."})
```

跑：`py -m pytest tests/test_xxx.py -v`；全量 `py -m pytest -q --ignore=tests/test_project_homepage.py`（基线 **320 passed**，`test_project_homepage.py` 单独跑、易受外部影响所以全量时 ignore）。

---

## 6. 提交 / 版本规范

- commit 信息：`feat: ...` / `fix: ...` / `release: vX.Y.Z ...`，写清范围。
- **不要 push、不要打 tag**，除非用户要求；改完留工作树。
- 版本号三处要同步：`mobile/package.json`、`mobile/android/app/build.gradle`（`versionName`+`versionCode`）、`CHANGELOG.md`（GBK 编码！）。
- 文档同步：根目录 `F:\product-philosophy\反转家教\24-版本计划与完成证明.md` 是版本计划与完成证明（含 changelog 表），完成项要回填"改动文件/验证方式/验证结果/备注"并把 `- [ ]` 改 `- [x]`。

---

## 7. v0.18.0 APK 实机测试方向（给用户的清单 = 你修复时的验收点）

> v0.18.0 客户端实际范围 = **V1 学习闭环加固** + 我加的 V2.3 来源展示片段。按下面定位/验收。

1. **线索型学生纪律（本版重点）**：新会话抛一个完全不会的题 → AI 必须**学生请教口吻**开场，禁止老师式讲解；用户给出观察后**强制切回追问**。出问题 → 改 `index.html` 的角色/口吻逻辑。
2. **no_entry 二次校验**：已有学习记录且最近给过可执行步骤的会话继续追问 → **不应**误判零基础重拉线索模式。
3. **"本轮判断"折叠区**：气泡下折叠区应有 **依据/策略/下一步/证据 episodes** 四块，证据可定位消息。
4. **到期复习 1/3/7/14**：到期主动提示；答对升级间隔，**答错重置 1 天**。
5. **离线引擎 / 后台 fallback**：不配 LLM 或断网也能返回结构化结果，字段（`entry_status`/`student_role`/`evidence_for_mastery`）不报错不崩。
6. **客户端知识图谱（回归）**：图谱页 canvas 渲染、节点详情、编辑保存正常。
7. **LLM 配置 + 免费 GLM 兜底（回归）**：切 provider；不填 key 走内置免费 GLM，失败回退本地 mock。

**反馈应包含**：现象 + 哪一步 + 截图/报错文本。重点盯：线索型是否"破功"用老师口吻、"本轮判断"字段是否齐全、离线下有无红色失败气泡/崩溃。

---

## 8. 修 bug 标准动作（Codex 请照此走）

1. **先分类**：现象在 APK/前端 → `static/app/index.html`；在 API/数据/后端 → Python 模块。
2. **定位根因**：用 `rg` 搜符号；前端搜 JS 函数名，后端搜函数/路由。
3. **最小修复**：改一处根因，别重构。新参数带默认值。
4. **补/改测试**（后端）：先写能复现的失败用例，再修到绿；前端改动在回复里说明手测方式。
5. **回归**：`py -m pytest -q --ignore=tests/test_project_homepage.py` 必须绿。
6. **收尾**：不 push；回复列出改动文件、pass 数、是否发现新 bug。若改了客户端且需重打 APK，按 §3 说明（默认不自动打，等用户要）。
