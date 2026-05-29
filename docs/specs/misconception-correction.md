# SPEC for Codex — 反例追问式纠错（in-character misconception correction）

> 作者：Cascade（架构）。先读 `AGENTS.md` + `docs/CODEX_HANDOFF.md`。
> 用户实机测出的严重问题：**用户（老师）把一条假规则当真理讲出来时，AI 学生只会和稀泥式追问（"那它算增还是减呀?"），从不让用户意识到自己错。** 需要一个**全程保持学生人设**、却能让用户自己发现并改正错误的机制。
> 用户已拍板：**做成可调档，默认"平衡"。**

## 0. 必须遵守
- 环境：只用 `py`（不是 `python`），不建 shim，PowerShell 不用 `cd`，不 push。
- **双实现同步**：本功能必须同时改 **后端 `engine.py`/`server.py`（带测试）** 和 **APK 实际运行的客户端 `static/app/index.html` 的 JS**。两边逻辑对齐。漏改 index.html = 用户实机看不到修复。
- 全量回归 `py -m pytest -q --ignore=tests/test_project_homepage.py` 必须绿（基线 320 passed），并加新测试。
- 新参数带默认值、向后兼容；不删/不弱化已有测试；不增删无关注释。

## 1. 根因（已定位，供你理解，不必重新调研）
- 评估里 `correctness`/`error_type` 只衡量"答得好不好"，**没有"用户断言了一条事实性假规则"这个信号**，模型默认走温和 `probe`/`ask`。
- 唯一强力纠错是 `small_lecture`，但它是**老师口吻**（破角色）且被 `correction_timing` 卡住——**本 spec 不能用它**。
- `probe` 的"举反例"只在"懂但浅"触发，且**没有升级→收尾闭环**。
- 错误只在 `examiner_verify` 失败时进 `error_log`（`engine.py` 与 `static/app/index.html` 约 4944/4994 行），追问中教出来的错规则没被记录。

## 2. 新增可调设置：`correction_persistence`
取值 `gentle | balanced | persistent`，**默认 `balanced`**。

- 加入 `engine.py` 的 `DEFAULT_STRATEGY_SETTINGS`（约 75 行）和 `static/app/index.html` 的 `DEFAULT_STRATEGY_SETTINGS`（约 4080 行）。
- 归一化：`engine._strategy_settings` 里把它 clamp 到三档之一（非法值回退 `balanced`）；index.html 的设置归一化（约 4304 行 `correction_timing` 校验附近）同样处理。
- **设置面板 UI**（index.html 约 7519-7522，紧挨"纠错时机"那个 `<select>`）：新增一个 `<select data-strategy-setting="correction_persistence">`，用现成的 `strategyOption(value, current, label)` 生成三个选项：
  - `gentle` → 标签"温和（只给反例）"
  - `balanced` → 标签"平衡（反例+求证提示）"
  - `persistent` → 标签"较真（紧盯改对）"

## 3. 评估 schema 增字段：`evaluation.misconception`
在两份 prompt 的 `evaluation` 输出格式里新增（`engine.py` 约 143-155，`static/app/index.html` 约 4374-4386）：
```
"misconception": "用户把错的当对的讲出来的那条假规则，≤20字；没有则空字符串"
```
含义：**用户以肯定语气断言了一条事实性错误**（区别于"说得不全/不精确"——后者 misconception 留空，仍走 probe/ask）。prompt 要用一两个例子教会模型这个区分。

## 4. 新增动作 `challenge` + 学生角色 `confused_student`
- **动作集**：在 study 模式可用动作里加 `challenge`（`engine._action_types_for_mode`；index.html 的 `actionLabels` 约 4070 + 输出格式 type 枚举 4388）。描述："反例追问式纠错：发现用户讲错时，用学生口吻抛反例/指矛盾，引导用户自己改正，绝不老师式讲解。"
- **角色**：加 `confused_student`。**关键**：两份代码都有"白名单校验"会把未知 type/role 强行改写——必须把 `challenge` 和 `confused_student` 加进：
  - `engine.py`：`_action_types_for_mode("study")`、`_student_role_for_action`（map `challenge`→`confused_student`）、以及 `run_turn` 里 `allowed_actions`/role 归一化逻辑。
  - `static/app/index.html`：约 2845 `allowed` 动作数组、约 2856 `roles` 数组 + `roleByAction` 映射（`challenge: 'confused_student'`）。
  - **若漏加，动作会被静默改成 ask/probe，功能等于没做。**
- pill 样式：index.html 已有 `.pill-correction`（485 行），让 `challenge` 复用它或加 `.pill-challenge`。

## 5. Prompt 策略段（两份都加，文案一致）
在两份 system prompt 里加一段"# 反例追问式纠错（misconception correction）"，要点：

1. 当 `evaluation.misconception` 非空 → `action.type` 设为 `"challenge"`，`student_role="confused_student"`。
2. **铁律**：全程学生口吻，**禁止**"你错了 / 不对 / 正确答案是 / 我来纠正你"。把矛盾说成**学生自己的发现**。
3. 升级阶梯，受 `correction_persistence` 控制：
   - **L1 反例**：现编一个最小反例当成"我试出来对不上"。例：用户说"f 在某点为正就是增函数"→"老师我拿 f(x)=x² 套了下，f(1)=1 是正的，可它在 x<0 明明在往下掉？这跟'f 正就是增'好像打架了，我是不是哪理解错了？"
   - **L2 指矛盾**："你前面说 X，这儿又得 Y，我对不上。"
   - **L3 求证式提示**（仍是提问，不是断言）："我翻笔记好像说判断增减是看*导数*符号？老师你看是不是？"
   - **L4 防卡死**："要不咱俩一块儿验证下这个例子?"
   - 档位映射：
     - `gentle`：只用 L1（反例），**绝不**给 L3 求证提示，可软性重复；让用户完全自主发现。
     - `balanced`（默认）：L1 反例 → 用户坚持错则 L2 → 仍坚持则 L3 求证提示。1-3 轮内引导改对。
     - `persistent`：更快升级到 L3/L4（一起验证），紧盯到用户改对为止——但仍学生口吻。
4. 受 `correction_timing` 约束：`immediate` 立即抛反例；`summary_only` 只轻声表达困惑、把反例/aha 留到 `recap`。
5. **收尾（"意识到自己错"的高光）**：用户一改向正确 → 学生给明确 aha，例"哦——原来看*导数*正负！我之前一直以为是函数值，被你一带就通了，谢谢老师。" 同时本轮 `evidence_for_mastery.type="correction"`、`status="passed"`。

## 6. error_log 捕获（两份）
- 当 `evaluation.misconception` 非空：把它作为错因写入/更新 `error_log`（不再只在 examiner_verify 失败时）。
  - `engine.py`：在 `run_turn` 落库逻辑里，misconception 非空时 upsert error_log（KP=action.knowledge_point，pattern=misconception）。
  - `static/app/index.html`：约 4944/4994，新增分支——misconception 非空时 `upsert_error_log(...)`。
- 当 `evidence_for_mastery.type=="correction" && status=="passed"`：把对应 error_log 标记 resolved/clear（两份都要）。

## 7. 测试（`tests/`，用 `py -m pytest`）
新建 `tests/test_misconception_correction.py`：
- **检测→动作**：mock LLM 返回 `evaluation.misconception` 非空 + `action.type="challenge"` → `run_turn` 不把它改写掉，保留 `challenge` / `confused_student`（验证白名单已放行）。
- **动作集**：`challenge` 在 study 模式 allowed，不在 goal/companion 模式。
- **设置档生效**：`correction_persistence` 三档分别出现在 `_format_strategy_settings` 输出里（断言策略块文案随档位变化）；非法值回退 `balanced`。
- **error_log 捕获**：misconception 非空 → 该 KP 出现 active error_log。
- **收尾闭环**：mock 返回 `evidence_for_mastery.type="correction"` status="passed" → 记 correction 证据 + 对应 error_log 被 resolved。
- **不误伤**：misconception 为空但 correctness 低（说得不全）→ 仍走 probe/ask，不触发 challenge。
- **向后兼容**：`DEFAULT_STRATEGY_SETTINGS` 含 `correction_persistence="balanced"`；旧会话无此字段时读默认。

参考现有 mock/fixture 写法：`tests/conftest.py`（`db_sess`、autouse mock LLM）、`tests/test_clue_with_retrieval.py`（`monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)`）、`tests/test_sources_api.py`（httpx ASGITransport）。

## 8. 验证 & 输出
```
py -m pytest tests/test_misconception_correction.py -v
py -m pytest -q --ignore=tests/test_project_homepage.py     # 必须 >=320 + 新增，全绿
```
完成后报告：改了哪些文件、新测试数、pass 数、有没有发现新 bug。**改了 index.html 需重打 APK 才能实机验证**——默认别自动打，等用户要（流程见 `docs/CODEX_HANDOFF.md` §3）。

## 9. 自检（交付前）
1. `challenge`/`confused_student` 是否已加进**两份**白名单校验（否则静默失效）？
2. 设置档在 UI、两份 DEFAULT、两份归一化里都加了？
3. 升级阶梯严格不破学生人设、不报正确答案（gentle 档连求证提示都不给）？
4. 全量绿 + 新测试通过？
5. `static/app/index.html` 和 `engine.py` 逻辑对齐？
