# SPEC for Codex — 客户端知识图谱对齐 + 前置补缺（client KG parity & prerequisite gap-filling）

> 作者：Cascade（架构）。先读 `AGENTS.md` + `docs/CODEX_HANDOFF.md`。
> 背景：后端有完整 KG 子系统（`kg_nodes/kg_edges`、抽取 `kg_extractor.py`、闸门 `kg_gate.py`、检索 `kg_retriever.py`），并在 `engine.run_turn` 里逐轮更新 + 注入 prompt。**但 APK 实际运行的客户端 `static/app/index.html` 没有持久化 KG**——只临时从 `related_kps` 拼可视化图，后端 KG/前置能力在 APK 里完全没跑。
> 用户已拍板：**彻底解决**——在客户端建真正的 KG，并在其上做"前置补缺"。
> 这是大工程，**必须分阶段 A→B→C→D 实现，每阶段单独 commit + 测试**，不要一把梭。

## 0. 必须遵守
- 环境：只用 `py`（不是 `python`），不建 shim，PowerShell 不用 `cd`，不 push、不 tag、不动签名/版本号。
- **本任务核心是给客户端补齐后端已有能力**，后端 KG 代码作为权威规格镜像，**不要改后端 KG 逻辑**（除非发现 bug，先报告）。
- 客户端 KG 抽取**只用规则版（确定性），不调 LLM**（镜像后端 `_rule_extract` 路径即可，避免额外延迟/费用/不确定性）。
- 全量回归 `py -m pytest -q --ignore=tests/test_project_homepage.py` 必须绿；每阶段加客户端静态断言测试。
- 向后兼容：IndexedDB 升级不能丢用户旧数据；study 模式才抽取/注入，goal/companion 不动。
- 不删/不弱化已有测试；不增删无关注释。

## 1. 后端权威规格（镜像目标，勿改）

### 1.1 表结构（`db.py`）
- `kg_nodes`：`{id, session_id, kind, name, properties(json), source_episode_ids(json[]), first_seen_at, last_seen_at, status}`，唯一约束 `(session_id, kind, name)`。
- `kg_edges`：`{id, session_id, source_id, target_id, relation, weight, properties(json), source_episode_ids(json[]), valid_from, invalidated_at, status}`。
- `kind` 取值：`concept | error_pattern | preference | method | person`。
- `relation` 取值：`学习中 | 已掌握 | 容易混淆 | 曾误解 | 前置于 | 常用于 | 偏好 | 错在 | 挂起复习`。

### 1.2 CRUD（`db.py`）
`upsert_kg_node / find_kg_node / get_kg_node / list_kg_nodes / invalidate_kg_node`；
`upsert_kg_edge / get_kg_edge / list_kg_edges / invalidate_kg_edge / supersede_kg_edge`。

### 1.3 抽取（`kg_extractor.py` 的 `_rule_extract`）
从 `evaluation` + `action` 规则化更新节点/边（concept/error_pattern/preference/method 节点；学习中/已掌握/容易混淆/曾误解/前置于/常用于/偏好/错在 边；含 supersede 旧边、invalidate 等）。**逐行读懂 `_rule_extract` 并 1:1 移植到 JS。**

### 1.4 闸门（`kg_gate.py` 的 `should_extract`）
顺序：`kg_extraction_enabled==False`→拦；空 kp→拦；黑名单命中（`KG_DEFAULT_BLACKLIST` + `settings.kg_blacklist`，查 user_input 与 kp）→拦；`privacy_level=="strict"` 且无学习证据→拦；否则放行。`KG_DEFAULT_BLACKLIST` 原样移植。

### 1.5 检索 + 注入（`kg_retriever.py`）
`retrieve_kg_context(sid, current_kp)` → `KGContext{related_concepts(含 [前置] 前缀), historical_errors, misunderstandings, preferences, pending_review_kps}`；`format_for_prompt()` 产出 `# 知识图谱上下文` 文本块。后端在 `run_turn`（约 1159-1174）检索并拼进 system prompt。

### 1.6 抽取挂载点（`engine.run_turn`，约 1332-1344）
study 模式、turn 落库后：`should_extract(...)` 放行则 `extract_from_turn(..., episode_id=assistant_msg.id)`。

## 2. 阶段 A — 客户端 KG 存储 + CRUD

- `static/app/index.html`：`DB_VERSION` 从 `2` 升到 `3`（约 2973）；`onupgradeneeded` 里新增两个 object store：
  - `kg_nodes`：`keyPath:'id', autoIncrement:true`；建索引 `sid`、复合 `[sid+kind+name]`（用于唯一查找）。
  - `kg_edges`：`keyPath:'id', autoIncrement:true`；建索引 `sid`、`source_id`、`target_id`、`relation`。
  - 把 `kg_nodes`、`kg_edges` 加入 `STORES` 数组（约 2974）。
- 实现 JS 版 CRUD（命名对齐后端）：`upsert_kg_node / find_kg_node / get_kg_node / list_kg_nodes / invalidate_kg_node / upsert_kg_edge / list_kg_edges / invalidate_kg_edge / supersede_kg_edge`。语义、status 流转、唯一性 `(sid,kind,name)` 与后端一致。
- **阶段验收**：升级后旧数据完好；新店可增删查；`(sid,kind,name)` 唯一 upsert 正确。
- **测试**：`tests/test_mobile_persistence.py` 加断言：HTML 含 `DB_VERSION = 3`、`createObjectStore('kg_nodes'`、`createObjectStore('kg_edges'`、各 CRUD 函数名存在。
- **单独 commit**。

## 3. 阶段 B — 客户端闸门 + 抽取，并挂载到 turn

- 移植 `kg_gate.should_extract` → JS（含 `KG_DEFAULT_BLACKLIST`、`settings.kg_blacklist`、`privacy_level==='strict'` 证据判定）。
- 移植 `kg_extractor._rule_extract` → JS `extract_from_turn(sid, {evaluation, action, episodeId})`，1:1 对齐节点/边更新规则。
- **挂载**：在客户端两处 turn 落库路径（约 4980 / 5036，`upsert_mastery`/`upsert_error_log` 之后），当 `mode==='study'` 且闸门放行时调用 `extract_from_turn(...)`，`episodeId=assistantEpisodeId`。
- **阶段验收**：一轮 study 对话后，IndexedDB 里出现对应 concept 节点与关系边；黑名单/strict/空 kp 场景被拦。
- **测试**：`tests/test_mobile_persistence.py` 加断言：HTML 含闸门函数（`should_extract` 等价）、`KG_DEFAULT_BLACKLIST` 关键词、`extract_from_turn` 调用挂在 study 落库路径。
- **单独 commit**。

## 4. 阶段 C — 客户端检索 + prompt 注入

- 移植 `retrieve_kg_context` + `KGContext.format_for_prompt` → JS（related_concepts 含 `[前置]` 前缀、historical_errors、misunderstandings、preferences、pending_review_kps）。
- **注入**：在客户端构建 system prompt 处（`ENGINE` prompt 组装，参考后端 `kg_context_text` 拼接位置；客户端约 4355-4429 prompt 组装区）retrieve 当前 kp 的 KG context，拼到 prompt（与后端 `# 知识图谱上下文` 块一致）。
- **阶段验收**：当 KG 有相关节点时，客户端 prompt 含"# 知识图谱上下文"块；空时不注入。
- **测试**：HTML 含 `format_for_prompt` 等价逻辑与 `# 知识图谱上下文` 文案；prompt 组装处引用 KG 检索。
- **单独 commit**。

## 5. 阶段 D — 前置补缺（新能力，两端都加）

> 这是本任务"新功能"部分：检测当前 kp 的**前置知识点掌握不足**，引导 AI 先以学生口吻回补前置，而非直接往下走。

- **后端**：
  - `kg_retriever.py`：新增 `detect_prereq_gaps(db_sess, sid, current_kp, mastery_threshold=0.5)` → 沿 `前置于` 边找前置节点，交叉 `mastery` 表（`level`/`mastery_score`），返回"未学或掌握度 < 阈值"的前置点列表。
  - 把缺口并入 `KGContext`（新增字段 `prereq_gaps: list[str]`）+ `format_for_prompt`（新增"## 前置缺口"段，指导 AI 先确认/回补这些前置点，保持学生口吻）。
  - `mastery_threshold` 设为模块常量并加注释。
- **客户端**：同样实现 `detect_prereq_gaps`（基于阶段 A 的 KG + 客户端 mastery 表）并注入"## 前置缺口"段，文案与后端一致。
- **prompt 指导文案**（两端一致）：当存在前置缺口 → AI 应先以学生身份就该前置点提问/确认（"老师，要学这个我是不是得先搞懂 X？我对 X 还有点虚"），确认后再继续；不要变成老师讲解。
- **阶段验收**：构造"用户跳过前置直接讲高级概念、且前置掌握度低"场景 → prompt 出现"## 前置缺口"，AI 先回到前置点；前置已掌握 → 不触发。
- **测试**：
  - 后端 `tests/test_prereq_gap.py`：有缺口→注入、无缺口→不注入、前置已掌握→不注入、空 kp→空。
  - 客户端 `tests/test_mobile_persistence.py` 断言：HTML 含 `detect_prereq_gaps` 与"前置缺口"文案。
- **单独 commit**。

## 6. 验证 & 输出（全部阶段完成后）
```
py -m pytest tests/test_prereq_gap.py -v
py -m pytest tests/test_mobile_persistence.py -v
py -m pytest -q --ignore=tests/test_project_homepage.py     # 全绿
```
报告：每阶段改了哪些文件、新测试数、pass 数、有无新 bug。**改了 index.html + 升了 DB_VERSION，需重打 APK 才能实机验证**（默认别自动打，等用户要；提醒用户 DB 升级会触发 onupgradeneeded）。

## 7. 自检（交付前）
1. 客户端 KG 表结构/CRUD/status 流转/唯一性是否与后端一致？
2. 抽取规则是否 1:1 镜像 `_rule_extract`（只用规则版，不调 LLM）？
3. 闸门黑名单/strict/空 kp/开关 是否全部移植？
4. 检索注入文案与后端"# 知识图谱上下文"一致？仅 study 模式？
5. 前置补缺两端逻辑/阈值/文案一致，且"前置已掌握不触发"？
6. IndexedDB 升级不丢旧数据？
7. 每阶段单独 commit，全量回归绿？
8. `static/app/index.html` 与后端逻辑对齐？
