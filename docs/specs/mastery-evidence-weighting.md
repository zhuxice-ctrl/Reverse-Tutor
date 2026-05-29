# SPEC for Codex — 掌握度证据模型对齐（client mastery evidence-gating）

> 作者：Cascade（架构）。先读 `AGENTS.md` + `docs/CODEX_HANDOFF.md`。
> 背景：后端 `db.upsert_mastery` 早已是**证据闸门 + 加权**模型（"嘴上说懂"不涨分），但 **APK 实际运行的 `static/app/index.html` 客户端 `upsert_mastery` 还是 V1 老公式**（`target = 0.5*correctness + 0.5*depth`，完全无视证据类型/状态）。
> **后果**：用户实机时"嘴上说懂就刷高掌握度"的洞一直存在。本任务 = **把后端已有的证据闸门模型搬到客户端**，不是做新后端功能。

## 0. 必须遵守
- 环境：只用 `py`（不是 `python`），不建 shim，PowerShell 不用 `cd`，不 push、不 tag、不动签名/版本号。
- 本任务**主要改客户端 `static/app/index.html`**；后端已正确，**不要改后端 `db.upsert_mastery` 的算法**（除非发现 bug，先报告再改）。
- 全量回归 `py -m pytest -q --ignore=tests/test_project_homepage.py` 必须绿，并加新测试。
- 向后兼容：旧 mastery 记录（只有 `level`、无证据字段）不能崩；新字段给默认值。
- 不删/不弱化已有测试；不增删无关注释。

## 1. 后端基线（照搬目标，勿改）
`db.py`：
- `_EVIDENCE_SCORES`（0–100）：`none=0, explanation=35, retrieval=55, transfer=72, delayed_retrieval=82, correction=90`。
- 闸门：**仅当** `evidence_type != "none"` **且** `verification_status in {"passed","partial"}` 才涨分；`partial` 时 `target *= 0.75`。
- 加权：`alpha=0.35`；`score = (1-alpha)*old + alpha*target`，clamp 到 `[0,100]`。
- `verification_status == "failed"`：是证据但不进步 → 回退 `8.0 if old>50 else 0.0`（分数下调，不增 review interval）。
- `none/其它`：不动分数（只记 attempts 等元信息）。
- 记录 `last_evidence_type` / `last_verification_status` / `attempts` / `last_correctness` / `last_depth`。

## 2. 客户端改造（`static/app/index.html`）

### 2.1 改 `upsert_mastery`（约 4900–4920，`async function upsert_mastery`）
- **签名扩展**：`async function upsert_mastery(sid, kp, correctness, depth, evidenceType='none', verificationStatus='none')`。
- 新增常量（客户端用 **0–1 归一**，与现有 `level` 量纲一致，= 后端分数 /100）：
  ```js
  const EVIDENCE_SCORES = { none:0, explanation:0.35, retrieval:0.55, transfer:0.72, delayed_retrieval:0.82, correction:0.90 };
  ```
- 逻辑严格镜像后端：
  - `evidenceType` 不在表中 → `'none'`。
  - 若 `evidenceType!=='none' && (verificationStatus==='passed' || verificationStatus==='partial')`：
    - `let target = EVIDENCE_SCORES[evidenceType]; if (verificationStatus==='partial') target *= 0.75;`
    - `row.level = clamp01((1-alpha)*oldLevel + alpha*target);`（`alpha=0.35`）
  - 否则若 `verificationStatus==='failed'`：`row.level = clamp01(oldLevel - (oldLevel>0.5 ? 0.08 : 0));`
  - 否则（`none`/其它）：**不改 `level`**，只更新 attempts/last_* 元信息。
- 行内新增/更新字段：`last_evidence_type`、`last_verification_status`（连同已有 `attempts/last_correctness/last_depth/updated_at`）。
- **保留 `level` 为 0–1 主字段**（别改成 0–100），避免破坏所有读 `level` 的显示/图谱/阈值代码。

### 2.2 改两处调用点传入证据
现有两处（前台 + 后台 turn 落库，约 4980 与 5036，紧挨 `upsert_error_log` 分支）：
```js
await upsert_mastery(sid, ac.knowledge_point, +ev.correctness||0, +ev.depth||0);
```
改为传入证据：
```js
await upsert_mastery(sid, ac.knowledge_point, +ev.correctness||0, +ev.depth||0,
                     ev.evidence_for_mastery?.type || 'none',
                     ev.evidence_for_mastery?.status || 'none');
```

### 2.3 保护现有"已掌握"阈值与显示
- 找到所有读 `mastery.level` 的地方（掌握度显示、`已掌握` 判定、知识图谱着色等），确认 0–1 语义未变、阈值仍合理。
- 关键效果（必须达成）：**纯 `explanation`（哪怕 correctness=1）也无法把 `level` 拉到"已掌握"阈值**；只有 `transfer/delayed_retrieval/correction` 这类强证据能拉高。

## 3. 测试

### 3.1 客户端静态断言（`tests/test_mobile_persistence.py`，沿用现有"扫 HTML 字符串"风格）
新增断言，确保 APK 端逻辑已落地：
- HTML 含 `EVIDENCE_SCORES`（或等价证据权重表）且包含 `delayed_retrieval` / `correction` 键。
- `upsert_mastery` 签名含 `evidenceType`/`verificationStatus`（或等价形参）。
- 两处调用点传入 `evidence_for_mastery?.type` / `evidence_for_mastery?.status`。

### 3.2 后端回归（确认未误伤）
- 现有 mastery 相关测试保持绿（例如 `test_settings_strategy.py`、掌握度相关用例）。
- 如后端无"嘴上说懂不涨分"的直接断言，新增 `tests/test_mastery_evidence_weighting.py`：
  - `evidence_type='explanation'` 高 correctness 多轮 → mastery_score 不达"已掌握"高位。
  - `delayed_retrieval`/`correction` 单轮提升幅度显著大于 `explanation`。
  - `verification_status='none'`（嘴上说懂）→ 分数不变。
  - `failed` → 分数按规则回退。

## 4. 验证 & 输出
```
py -m pytest tests/test_mobile_persistence.py -v
py -m pytest tests/test_mastery_evidence_weighting.py -v   # 若新建
py -m pytest -q --ignore=tests/test_project_homepage.py     # 全绿
```
报告：改了哪些文件、新测试数、pass 数、有无新 bug。**改了 index.html 需重打 APK 才能实机验证**（默认别自动打，等用户要）。

## 5. 自检（交付前）
1. 客户端 `upsert_mastery` 是否严格镜像后端闸门（none 不涨、partial×0.75、failed 回退、alpha=0.35）？
2. `level` 仍是 0–1，所有读它的显示/阈值未被破坏？
3. 两处调用点都传了证据类型/状态？
4. 纯 explanation 无法刷到"已掌握"？
5. 全量回归绿 + 新断言/测试通过？
