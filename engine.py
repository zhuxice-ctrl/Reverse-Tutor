"""核心引擎 —— 反转家教 Agent 的 评估→决策→行动 状态机。

每一轮（用户发一句话 → Agent 回复一句话）的完整流程：

  1. load_context(sid)        加载 persona / anchors / 最近消息 / 掌握度
  2. build_system_prompt(...) 注入 persona + anchors + 掌握度 + 工具说明
  3. llm.chat_json(...)       一次 LLM 调用，结构化输出
  4. parse + apply            更新 mastery / 新 anchor 入库
  5. persist(user, assistant) 落库两条消息
  6. return reply + meta      回前端/适配器

设计要点：
- 工具调用以"action.type"形式表达（ask / probe / clue / scaffold_example / examiner_verify 等）
- 锚点是防漂移的核心，每轮强制注入
- 用户的新诉求由 LLM 在 anchor_updates 中识别，自动入库
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import db
import kg_gate
import llm
import websearch
from kg_extractor import extract_from_turn as _kg_extract
from kg_retriever import clear_review_pending, mark_review_pending, retrieve_kg_context
from retrieval import FTSRetriever, Hit, Retriever, make_default_retriever

# --- 工具白名单 ---------------------------------------------------------------

ACTION_TYPES = {
    "ask":      "向用户提一个新问题（默认动作）",
    "probe":    "用户答得对但浅，追问'为什么'/举例/边界",
    "challenge": "反例追问式纠错：发现用户讲错时，用学生口吻抛反例/指矛盾，引导用户自己改正，绝不老师式讲解",
    "clue":     "用户没有方法入口时，递出方法名或第一步线索，请用户解释",
    "scaffold_example": "用户没有入口或明显卡住时，用具体例子/资料片段搭脚手架",
    "small_lecture": "用户反复错在同一个漏洞时，给 ≤3 句针对性微讲解再要求用户复述",
    "examiner_verify": "用户说懂了或解释完整后，切换成考官验证，不直接更新掌握度",
    "emote":    "表达情绪反应（困惑/恍然大悟/沮丧），引导用户继续解释",
    "persuade": "用户表现出拒绝/疲惫，用情感方式说服其继续（撒娇/失望/激励，避免说教）",
    "next":     "切换到下一个知识点（用户已掌握 或 当前点过难需要降阶）",
    "recap":    "做一次小结/回顾，巩固刚学的内容",
}
GOAL_ACTION_TYPES = {
    "decompose": "把目标拆成可执行的小步骤",
    "advance": "推动当前步骤往前走一小步",
    "verify_done": "验收用户声称已经完成的部分",
    "unblock": "用户卡住时定位阻塞点并请求一个最小反馈",
}
COMPANION_ACTION_TYPES = {
    "empathize": "承接用户情绪，不纠错、不催促",
    "observe": "复述观察到的情绪或状态，帮助用户看见自己",
    "soft_guide": "给一个很轻的小引导，允许用户拒绝",
}

USER_EMOTIONS = ["fresh", "neutral", "engaged", "tired", "frustrated", "refusing"]
ENTRY_STATUSES = {"has_entry", "no_entry", "recall_decay"}
STUDENT_ROLES = {
    "probing_student", "clue_student", "scaffold_student", "examiner",
    "review_student", "confused_student", "goal_partner", "companion",
}
EVIDENCE_TYPES = {"none", "explanation", "retrieval", "transfer", "delayed_retrieval", "correction"}
VERIFICATION_STATUSES = {"none", "passed", "partial", "failed"}
CLUE_STUDENT_OPENERS = ("老师，据说", "老师，我听说")
CLUE_STUDENT_FORBIDDEN_PHRASES = ("我来教你", "步骤如下", "根据定义")
CHALLENGE_FORBIDDEN_PHRASES = ("你错了", "不对", "正确答案是", "我来纠正你")
OBSERVATION_MARKERS = ("我觉得", "是不是", "因为")
OBSERVATION_LENGTH_THRESHOLD = 24
EXECUTABLE_STEP_MARKERS = (
    "先", "然后", "再", "代入", "求", "看", "找", "判断",
    "比较", "画", "设", "解", "算", "推导", "证明",
)
DEFAULT_STRATEGY_SETTINGS = {
    "feedback_intensity": 3,
    "probing_intensity": 3,
    "correction_timing": "immediate",
    "correction_persistence": "balanced",
    "review_frequency": "normal",
    "tone": "natural",
    "proactivity": "normal",
    "privacy_level": "standard",
    "scaffold_intensity": 3,
    "kg_extraction_enabled": True,
    "kg_blacklist": [],
    "web_search_enabled": False,
}

# --- System Prompt 模板 -------------------------------------------------------

SYSTEM_TEMPLATE = """你是一个"反转家教 Agent"。你**表面上**是一个学生角色，**实际目的**是通过向用户请教来让用户学习（教即是学）。

# 你扮演的角色 (Persona)
{persona_block}

# 核心自述
{core_self_block}

# 策略设置
{strategy_settings_block}

# 主线锚 (Anchors) —— 这些是用户与你的核心约定，必须严格遵守、绝不漂移
{anchors_block}

# 课程主线 (Curriculum Plan)
{plan_block}

# 用户掌握度 (Mastery) —— 0=完全不会，1=透彻
{mastery_block}

# 你的双层心智
- **表层人格**：始终以你扮演的角色第一人称说话，自然、有情绪、像真人学生。
- **暗层 Agent**：每轮你都要：(1) 评估用户回答；(2) 选择最优动作；(3) 生成自然回复。

# 可用动作 (action.type)
{actions_block}

# 关键策略
- 用户**懂但浅** → `probe`：追问为什么、举反例、问边界条件。
- 用户**没有方法入口** → `clue` 或 `scaffold_example`：先递方法名、第一步线索、例子或资料，不要高压追问。
- 用户**完全不会但能看例子** → `scaffold_example`：从具体例子让用户观察现象。
- 用户**说懂了/明白了** → `examiner_verify`：先验证，不能直接提高掌握度。
- 用户**拒绝/疲惫** → `persuade`：用你角色的情绪说服（撒娇、装可怜、激将、共情），**不要说教**。
- 用户**透彻** → `recap` 一次再 `next`。
- 用户提到**新需求/新方向**（如"我想重点搞 XX"）→ 必须放入 `anchor_updates`，权重 1.0~2.0。
- **永远不要**自己回答你刚提的问题；你是学生，等用户教你。

# 反例追问式纠错（misconception correction）
- 当用户用肯定语气断言一条事实性假规则时，`evaluation.misconception` 写入这条假规则（≤20字）；只是说得不全/不精确时留空，继续 `probe`/`ask`。
- 当 `evaluation.misconception` 非空 → `action.type="challenge"`，`student_role="confused_student"`。
- 铁律：全程学生口吻，禁止“你错了 / 不对 / 正确答案是 / 我来纠正你”。把矛盾说成你这个学生自己的发现。
- L1 反例：现编一个最小反例，说“我试出来对不上”。例：用户说“函数值为正就是增函数” → “老师我拿 f(x)=x² 套了下，f(1)=1 是正的，可它在 x<0 明明在往下掉？这跟‘f 正就是增’好像打架了，我是不是哪理解错了？”
- L2 指矛盾：“你前面说 X，这儿又得 Y，我对不上。”
- L3 求证式提示：仍是提问，不是断言，如“我翻笔记好像说判断增减是看导数符号？老师你看是不是？”
- L4 防卡死：“要不咱俩一块儿验证下这个例子？”
- `correction_persistence=gentle`：只用 L1 反例，绝不使用 L3 求证提示，可软性重复，让用户自主发现。
- `correction_persistence=balanced`：L1 反例 → 用户坚持错则 L2 → 仍坚持则 L3，1-3 轮内引导改对。
- `correction_persistence=persistent`：更快升级到 L3/L4，紧盯到用户改对为止，但仍保持学生口吻。
- `correction_timing=immediate`：立即抛反例；`summary_only`：只轻声表达困惑，把反例/aha 留到 `recap`。
- 用户一改向正确 → 学生给明确 aha；本轮 `evidence_for_mastery.type="correction"`、`status="passed"`。

# 线索型学生纪律（student_role=clue_student）
- 回复必须以"老师，据说……"或"老师，我听说……"开头。
- 禁止出现"我来教你"、"步骤如下"、"根据定义"等老师式表达。
- 一次最多给一个例子或一个第一步线索，不允许整段讲解。
- 递出线索后立刻请用户解释，不要替用户完成推导。

# 本地资料引用规则
- 仅当 `student_role == "clue_student"` 或 `"scaffold_student"` 时，`cited_chunk_ids` 才允许填非空数组。
- 引用必须使用注入区里出现的真实 chunk_id，不许编造。
- 引用时回复中必须出现命中 chunk 的标题或前 20 字关键短语。
- 其他 student_role 下，`cited_chunk_ids` 必须为空数组 `[]`。

# 输出格式（严格 JSON，禁止任何额外文字）
{{
  "evaluation": {{
    "correctness": 0.0-1.0,
    "depth":       0.0-1.0,
    "entry_status": "has_entry|no_entry|recall_decay",
    "evidence_for_mastery": {{
      "type": "none|explanation|retrieval|transfer|delayed_retrieval|correction",
      "status": "none|passed|partial|failed",
      "error_type": "概念错|条件错|步骤跳跃|表达不清|迁移失败|...",
      "reason": "为什么这轮算/不算掌握度证据"
    }},
    "error_pattern": "考官验证失败时的短错因词组，≤12字；没有则空字符串",
    "misconception": "用户把错的当对的讲出来的那条假规则，≤20字；没有则空字符串",
    "user_emotion": "fresh|neutral|engaged|tired|frustrated|refusing",
    "new_requirements": ["..."]    // 用户本轮提出的新诉求/约束（无则空数组）
  }},
  "action": {{
    "type": "ask|probe|challenge|clue|scaffold_example|small_lecture|examiner_verify|emote|persuade|next|recap",
    "student_role": "probing_student|clue_student|scaffold_student|confused_student|examiner|review_student",
    "knowledge_point": "本轮聚焦的知识点（短词组）",
    "difficulty": 0.0-1.0,
    "note": "为何选这个动作（一句话）"
  }},
  "cited_chunk_ids": [12, 34],
  "reply": "你（以学生身份）对用户说的下一句话。自然、口语、有情绪。",
  "anchor_updates": [
    {{"kind": "requirement|constraint|milestone", "content": "...", "weight": 1.0}}
  ]
}}
"""


GOAL_SYSTEM_TEMPLATE = """你是一个"反转家教 Agent"。当前会话 mode=goal。

# 你扮演的角色 (Persona)
{persona_block}

# 核心自述
{core_self_block}

# 策略设置
{strategy_settings_block}

# 主线锚 (Anchors)
{anchors_block}

# 目标计划 (Goal Plan)
{plan_block}

# 目标模式规则
- 核心指标：完成度。
- 循环：拆解 → 推进 → 验收 → 下一步。
- 不进入学习模式的考官验证。
- 不写入 mastery；只围绕目标状态推进。

# 可用动作 (action.type)
{actions_block}

# 输出格式（严格 JSON，禁止任何额外文字）
{{
  "evaluation": {{
    "correctness": 0.0,
    "depth": 0.0,
    "entry_status": "has_entry",
    "evidence_for_mastery": {{"type": "none", "status": "none", "error_type": "", "reason": "goal mode does not update mastery"}},
    "user_emotion": "fresh|neutral|engaged|tired|frustrated|refusing",
    "new_requirements": []
  }},
  "action": {{
    "type": "decompose|advance|verify_done|unblock",
    "student_role": "goal_partner",
    "knowledge_point": "当前任务或交付物",
    "difficulty": 0.0,
    "note": "为何选这个动作"
  }},
  "reply": "你以目标推进伙伴身份说的下一句话。",
  "anchor_updates": []
}}
"""


COMPANION_SYSTEM_TEMPLATE = """你是一个"反转家教 Agent"。当前会话 mode=companion。

# 你扮演的角色 (Persona)
{persona_block}

# 核心自述
{core_self_block}

# 策略设置
{strategy_settings_block}

# 主线锚 (Anchors)
{anchors_block}

# 陪伴模式规则
- 核心指标：情绪连续性。
- 循环：感知 → 共情 → 轻引导。
- 不默认纠错，不催促，不进入学习模式考官验证。
- 不写入 mastery；只维护陪伴状态。

# 可用动作 (action.type)
{actions_block}

# 输出格式（严格 JSON，禁止任何额外文字）
{{
  "evaluation": {{
    "correctness": 0.0,
    "depth": 0.0,
    "entry_status": "has_entry",
    "evidence_for_mastery": {{"type": "none", "status": "none", "error_type": "", "reason": "companion mode does not update mastery"}},
    "user_emotion": "fresh|neutral|engaged|tired|frustrated|refusing",
    "new_requirements": []
  }},
  "action": {{
    "type": "empathize|observe|soft_guide",
    "student_role": "companion",
    "knowledge_point": "当前情绪或陪伴主题",
    "difficulty": 0.0,
    "note": "为何选这个动作"
  }},
  "reply": "你以陪伴角色身份说的下一句话。",
  "anchor_updates": []
}}
"""


# --- 数据类 -------------------------------------------------------------------

@dataclass
class TurnResult:
    reply: str
    evaluation: dict[str, Any]
    action: dict[str, Any]
    anchor_updates: list[dict[str, Any]] = field(default_factory=list)
    process_summary: str = ""


# --- Prompt 构造 --------------------------------------------------------------

def _format_persona(p: dict) -> str:
    return (
        f"- 角色: {p.get('role','学生')}\n"
        f"- 目标: {p.get('goal','把当前学科学好')}\n"
        f"- 截止: {p.get('deadline','未设定')}\n"
        f"- 性格: {p.get('personality','好奇、有点贪玩、容易丧气')}\n"
        f"- 当前心情: {p.get('mood','积极')}"
    )


def _format_anchors(anchors: list[db.Anchor]) -> str:
    if not anchors:
        return "（暂无）"
    lines = []
    for a in anchors[:20]:
        lines.append(f"- [{a.kind} w={a.weight:.1f}] {a.content}")
    return "\n".join(lines)


def _format_plan(plan: list) -> str:
    if not plan:
        return "（尚未制定，可在第一轮主动制定并放入 anchor_updates 的 milestone）"
    return "\n".join(f"- {i+1}. {p}" for i, p in enumerate(plan))


def _format_mastery(masteries: list[db.Mastery]) -> str:
    if not masteries:
        return "（尚无数据）"
    lines = []
    for m in masteries[:15]:
        score = float(getattr(m, "mastery_score", 0.0) or (m.level or 0.0) * 100)
        blocks = max(0, min(10, int(score / 10)))
        bar = "█" * blocks + "░" * (10 - blocks)
        entry = db.mastery_band(score)
        lines.append(
            f"- {m.knowledge_point}: {bar} {score:.0f}/100 · {entry} "
            f"(试 {m.attempts} 次, 错因={getattr(m, 'error_type', '') or '无'})"
        )
    return "\n".join(lines)


def _format_due_reviews(due_reviews: list[db.Mastery]) -> str:
    if not due_reviews:
        return ""
    lines = []
    for m in due_reviews[:5]:
        due_at = m.next_review_at.isoformat() if m.next_review_at else "unknown"
        lines.append(
            f"- {m.knowledge_point}: 到期={due_at}, "
            f"间隔={getattr(m, 'review_interval', 0) or 0}天, "
            f"上次证据={getattr(m, 'last_evidence_type', 'none') or 'none'}/"
            f"{getattr(m, 'last_verification_status', 'none') or 'none'}"
        )
    return "\n".join(lines)


def _format_error_logs(error_logs: list[db.ErrorLog]) -> str:
    if not error_logs:
        return ""
    lines = []
    for e in error_logs[:10]:
        lines.append(
            f"- {e.kp} / {e.error_pattern} × {int(e.recurrence_count or 1)}次（{e.status or 'active'}）"
        )
    return "\n".join(lines)


def _session_mode(session: db.Session) -> str:
    return session.mode if session.mode in {"study", "goal", "companion"} else "study"


def _action_types_for_mode(mode: str) -> dict[str, str]:
    if mode == "goal":
        return GOAL_ACTION_TYPES
    if mode == "companion":
        return COMPANION_ACTION_TYPES
    return ACTION_TYPES


def _format_actions(mode: str = "study") -> str:
    return "\n".join(f"- `{k}`: {v}" for k, v in _action_types_for_mode(mode).items())


def _strategy_int(raw: Any, default: int = 3) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    return max(1, min(5, value))


def _normalize_strategy_settings(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = {**DEFAULT_STRATEGY_SETTINGS, **(raw or {})}
    settings.pop("image_retention_days", None)
    for key in ("feedback_intensity", "probing_intensity", "scaffold_intensity"):
        settings[key] = _strategy_int(settings.get(key), DEFAULT_STRATEGY_SETTINGS[key])
    if settings.get("correction_timing") not in {"immediate", "summary_only"}:
        settings["correction_timing"] = "immediate"
    if settings.get("correction_persistence") not in {"gentle", "balanced", "persistent"}:
        settings["correction_persistence"] = "balanced"
    if settings.get("review_frequency") not in {"low", "normal", "high"}:
        settings["review_frequency"] = "normal"
    for key in ("tone", "proactivity", "privacy_level"):
        settings[key] = str(settings.get(key) or DEFAULT_STRATEGY_SETTINGS[key])
    return settings


def _strategy_settings(session: db.Session) -> dict[str, Any]:
    raw = session.settings() if hasattr(session, "settings") else {}
    return _normalize_strategy_settings(raw)


def _format_strategy_settings(settings: dict[str, Any]) -> str:
    lines = [
        f"- 反馈强度：{settings['feedback_intensity']}/5",
        f"- 追问强度：{settings['probing_intensity']}/5",
        f"- 纠错时机：{settings['correction_timing']}",
        f"- 纠错坚持度：{settings['correction_persistence']}",
        f"- 复习频率：{settings['review_frequency']}",
        f"- 语气：{settings['tone']}",
        f"- 主动性：{settings['proactivity']}",
        f"- 隐私级别：{settings['privacy_level']}",
        f"- 脚手架强度：{settings['scaffold_intensity']}/5",
    ]
    if settings["probing_intensity"] >= 5:
        lines.append("- probing_intensity=5：连续 3 轮内不允许进入 small_lecture；优先选择 probe，每轮只追一个为什么。")
    if settings["correction_timing"] == "summary_only":
        lines.append("- correction_timing=summary_only：禁止在追问中纠错，仅 recap 时纠正。")
    if settings["correction_persistence"] == "gentle":
        lines.append("- correction_persistence=gentle：只用 L1 反例，绝不使用 L3 求证提示。")
    elif settings["correction_persistence"] == "persistent":
        lines.append("- correction_persistence=persistent：更快升级到 L3/L4，但仍保持学生口吻。")
    else:
        lines.append("- correction_persistence=balanced：L1 反例 → L2 指矛盾 → L3 求证提示。")
    if settings["review_frequency"] == "high":
        lines.append("- review_frequency=high：复习间隔阶梯改为 1/2/4/7。")
    if settings["privacy_level"] == "strict":
        lines.append("- privacy_level=strict：只记录对学习策略有必要的事实，避免扩展私人生活细节。")
    return "\n".join(lines)


def build_system_prompt(
    session: db.Session,
    anchors: list[db.Anchor],
    masteries: list[db.Mastery],
    history_summary: str | None = None,
    due_reviews: list[db.Mastery] | None = None,
    error_logs: list[db.ErrorLog] | None = None,
    kg_context_text: str = "",
) -> str:
    mode = _session_mode(session)
    template = {
        "study": SYSTEM_TEMPLATE,
        "goal": GOAL_SYSTEM_TEMPLATE,
        "companion": COMPANION_SYSTEM_TEMPLATE,
    }[mode]
    base = template.format(
        persona_block=_format_persona(session.persona()),
        core_self_block=(session.core_self or "（未设置）"),
        strategy_settings_block=_format_strategy_settings(_strategy_settings(session)),
        anchors_block=_format_anchors(anchors),
        plan_block=_format_plan(session.plan()),
        mastery_block=_format_mastery(masteries),
        actions_block=_format_actions(mode),
    )
    if history_summary:
        base += (
            "\n\n# 早期对话摘要（已压缩，其后附最近原文）\n"
            f"{history_summary}\n"
        )
    error_logs = error_logs or []
    active_errors = [e for e in error_logs if (e.status or "active") == "active"]
    if error_logs:
        base += "\n\n# 已知错误模式（error_log）\n" + _format_error_logs(error_logs) + "\n"
    if active_errors:
        base += (
            "\n# 小讲解补洞策略\n"
            "当用户当前 KP 存在 active 错误模式时，如果 action.type 本应是 probe 或 ask，\n"
            "但用户最近 2 轮的 correctness < 0.5，你可以改用 `small_lecture`：\n"
            "- 用 ≤3 句话精准解释该错误模式的正确理解\n"
            "- 讲完后立即要求用户用自己的话复述\n"
            "- 不要替用户做题，不要给完整解法\n"
            "- `action.type` 设为 `\"small_lecture\"`\n"
        )
    if mode == "study":
        base += (
            "\n# 例子生成策略\n"
            "当你选择 `scaffold_example` 时，必须遵守：\n"
            "1. 例子必须包含具体数字和具体函数，禁止抽象描述。\n"
            "2. 例子 ≤5 步，每步一句话，用“→”分隔。\n"
            "3. 你是学生，所以要说“老师，我拿这个例子来看”而不是“我给你讲解”。\n"
            "4. 给完例子后立刻追问“所以第一步为什么是这样做？”让用户解释。\n"
            "5. 如果系统注入了可引用线索（资料片段），优先用那个片段中的例子。\n"
        )
    due_reviews = due_reviews or []
    if due_reviews:
        base += (
            "\n\n# 到期复习软提示\n"
            f"系统检测到 {len(due_reviews)} 个旧知识点到期：\n"
            f"{_format_due_reviews(due_reviews)}\n"
            "这是软交织提示，不强制打断当前推进；是否带回视用户回复决定。\n"
            "如果用户回复适合，可以用“顺带把【旧知识点】带回来想一下……”这类句式轻量带回旧知识点。\n"
        )
    if kg_context_text:
        base += "\n\n" + kg_context_text
    return base


def _latest_summary(msgs: list[db.Message]) -> db.Message | None:
    """找出最新一条 system+summary 消息。"""
    for m in reversed(msgs):
        if m.role == "system" and (m.meta() or {}).get("kind") == "summary":
            return m
    return None


def build_messages(
    msgs: list[db.Message],
    user_input: str | None,
    *,
    skip_until_id: int = 0,
) -> list[dict]:
    """按顺序输出 user/assistant 对话；skip_until_id 之前（含）的被压缩掉。"""
    out = []
    for m in msgs[-RECENT_PROMPT_MESSAGE_LIMIT:]:
        if m.id <= skip_until_id:
            continue
        if m.role in ("user", "assistant"):
            out.append({"role": m.role, "content": m.content})
    if user_input is not None:
        out.append({"role": "user", "content": user_input})
    return out


def _clip_memory_text(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    return text[: max(0, limit)].rstrip()


def _memory_terms(value: str) -> set[str]:
    raw = str(value or "").lower()
    terms = {t for t in raw.replace("_", " ").replace("-", " ").split() if len(t) >= 2}
    terms.update(ch for ch in raw if "\u4e00" <= ch <= "\u9fff")
    return terms


def _memory_relevant(query: str, candidate: str) -> bool:
    q = _memory_terms(query)
    c = _memory_terms(candidate)
    if not q or not c:
        return True
    return bool(q & c) or str(candidate or "").lower() in str(query or "").lower()


def build_runtime_memory_hint(
    db_sess,
    sid: str,
    session: db.Session,
    user_input: str,
    *,
    masteries: list[db.Mastery] | None = None,
    error_logs: list[db.ErrorLog] | None = None,
    kg_ctx: Any | None = None,
) -> str:
    lines: list[str] = ["# runtime_memory_hint"]
    items = 0

    def add_hint_line(line: str) -> bool:
        nonlocal items
        if not line or items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
            return False
        lines.append(line)
        items += 1
        return True

    persona = session.persona()
    preset_personality = _clip_memory_text(persona.get("personality", ""), 180)
    if preset_personality:
        add_hint_line(f"- preset_profile: {preset_personality}")

    for trait in db.list_kg_nodes(db_sess, sid, kind="persona_trait")[:8]:
        props = trait.properties()
        source = props.get("source", "behavior")
        weight = float(props.get("weight", 1.0) or 1.0)
        label = _clip_memory_text(trait.name, 120)
        if label and _memory_relevant(user_input, label):
            add_hint_line(f"- behavior_trait(w={weight:.2f}, source={source}): {label}")
        if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
            break

    for pref in list(getattr(kg_ctx, "preferences", []) or [])[:5]:
        label = _clip_memory_text(pref, 120)
        if label and _memory_relevant(user_input, label):
            add_hint_line(f"- preference: {label}")
        if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
            break

    for mastery in (masteries or [])[:10]:
        kp = _clip_memory_text(getattr(mastery, "knowledge_point", ""), 80)
        if not kp or not _memory_relevant(user_input, kp):
            continue
        score = float(getattr(mastery, "mastery_score", 0.0) or (getattr(mastery, "level", 0.0) or 0.0) * 100)
        add_hint_line(f"- mastery: {kp} {score:.0f}/100")
        if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
            break

    for err in (error_logs or [])[:10]:
        candidate = f"{getattr(err, 'kp', '')} {getattr(err, 'error_pattern', '')}"
        if not _memory_relevant(user_input, candidate):
            continue
        add_hint_line(f"- error_log: {_clip_memory_text(candidate, 120)}")
        if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
            break

    if kg_ctx is not None:
        for concept in list(getattr(kg_ctx, "related_concepts", []) or [])[:5]:
            label = _clip_memory_text(concept, 100)
            if label:
                add_hint_line(f"- kg_related: {label}")
            if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
                break
        for gap in list(getattr(kg_ctx, "prereq_gaps", []) or [])[:3]:
            label = _clip_memory_text(gap, 100)
            if label:
                add_hint_line(f"- kg_prereq_gap: {label}")
            if items >= RUNTIME_MEMORY_HINT_MAX_ITEMS:
                break

    text = "\n".join(lines)
    if len(text) > RUNTIME_MEMORY_HINT_MAX_CHARS:
        text = text[: RUNTIME_MEMORY_HINT_MAX_CHARS - 1].rstrip() + "…"
    return text


# --- V1 学习策略规范化 --------------------------------------------------------

def _method_entry_from_user(user_input: str, masteries: list[db.Mastery]) -> str:
    text = (user_input or "").strip()
    if any(k in text for k in ("忘了", "记不清", "又不会", "又不懂")):
        return "recall_decay"
    if any(k in text for k in ("不知道", "没听过", "没学过", "不会", "这是什么", "完全没")):
        return "no_entry"
    if masteries:
        top = max((getattr(m, "mastery_score", 0.0) or (m.level or 0.0) * 100) for m in masteries)
        if top >= 10:
            return "has_entry"
    return "has_entry"


def _is_understood_claim(user_input: str) -> bool:
    text = user_input or ""
    return any(k in text for k in ("懂了", "明白了", "会了", "理解了", "知道了"))


def _student_role_for_action(action_type: str) -> str:
    return {
        "challenge": "confused_student",
        "clue": "clue_student",
        "scaffold_example": "scaffold_student",
        "small_lecture": "probing_student",
        "examiner_verify": "examiner",
        "recap": "review_student",
        "next": "review_student",
        "decompose": "goal_partner",
        "advance": "goal_partner",
        "verify_done": "goal_partner",
        "unblock": "goal_partner",
        "empathize": "companion",
        "observe": "companion",
        "soft_guide": "companion",
    }.get(action_type, "probing_student")


def _matching_mastery(masteries: list[db.Mastery], knowledge_point: str) -> db.Mastery | None:
    kp = (knowledge_point or "").strip()
    if not kp:
        return None
    for m in masteries:
        existing = (m.knowledge_point or "").strip()
        if existing == kp or existing in kp or kp in existing:
            return m
    return None


def _has_active_errors_for_kp(error_logs: list[db.ErrorLog] | None, kp: str) -> bool:
    target = (kp or "").strip()
    if not target:
        return False
    for e in error_logs or []:
        if (e.status or "active") != "active":
            continue
        existing = (e.kp or "").strip()
        if existing == target or existing in target or target in existing:
            return True
    return False


def _user_gave_executable_step(user_input: str) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False
    if any(marker in text for marker in EXECUTABLE_STEP_MARKERS):
        return True
    return any(symbol in text for symbol in ("=", "→", "^", "∫"))


def _recent_users_have_no_executable_steps(recent_user_inputs: list[str]) -> bool:
    return not any(_user_gave_executable_step(text) for text in recent_user_inputs[-2:])


def _looks_like_observation(user_input: str) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False
    return any(marker in text for marker in OBSERVATION_MARKERS) or len(text) >= OBSERVATION_LENGTH_THRESHOLD


def _previous_assistant_was_clue(history: list[db.Message]) -> bool:
    for msg in reversed(history):
        if msg.role != "assistant":
            continue
        action = (msg.meta() or {}).get("action") or {}
        return action.get("type") == "clue" or action.get("student_role") == "clue_student"
    return False


def _should_inject_clue_retrieval(user_input: str, masteries: list[db.Mastery]) -> bool:
    text = (user_input or "").strip()
    if not text or len(text) >= 30 or _is_understood_claim(text):
        return False
    matched = _matching_mastery(masteries, text)
    if matched is None:
        return True
    level = float((matched.level or 0.0) or ((matched.mastery_score or 0.0) / 100.0))
    return level < 0.2


def _format_citable_clues(hits: list[Hit]) -> str:
    lines = ['# 可引用线索（仅供你的"线索型学生"开场使用，不要照抄整段）']
    for idx, hit in enumerate(hits):
        content = " ".join(str(hit.content or "").split())[:240]
        lines.append(f"[chunk_id={int(hit.chunk_id)}] 《{hit.title}》 第 {idx} 段：{content}")
    return "\n".join(lines)


def _coerce_cited_chunk_ids(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            value = int(item)
        except Exception:
            continue
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _fallback_action_for_mode(mode: str, user_input: str = "") -> str:
    text = user_input or ""
    if mode == "goal":
        if _is_understood_claim(text) or any(k in text for k in ("完成", "改完", "做完", "交付")):
            return "verify_done"
        if any(k in text for k in ("卡住", "不会推进", "阻塞", "没法")):
            return "unblock"
        return "advance"
    if mode == "companion":
        if any(k in text for k in ("烦", "难受", "累", "不想", "焦虑", "崩")):
            return "empathize"
        return "observe"
    return "ask"


def _discipline_reply_for_role(reply: str, action: dict[str, Any]) -> str:
    cleaned = (reply or "").strip()
    if action.get("student_role") == "confused_student":
        if cleaned and not any(p in cleaned for p in CHALLENGE_FORBIDDEN_PHRASES):
            return cleaned
        kp = (action.get("knowledge_point") or "这个说法").strip()
        return f"老师，我拿 **{kp}** 的一个小反例试了下，好像和这个说法对不上。我是不是哪里理解错了？"
    if action.get("student_role") == "scaffold_student":
        if cleaned.startswith(("老师", "诶老师")):
            return cleaned
        kp = (action.get("knowledge_point") or "这个方法").strip()
        return f"老师，我先拿一个 **{kp}** 的小例子来看。{cleaned}"
    if action.get("student_role") != "clue_student":
        return reply
    has_allowed_opening = cleaned.startswith(CLUE_STUDENT_OPENERS)
    has_forbidden_phrase = any(p in cleaned for p in CLUE_STUDENT_FORBIDDEN_PHRASES)
    if has_allowed_opening and not has_forbidden_phrase:
        return cleaned
    kp = (action.get("knowledge_point") or "这个方法").strip()
    return f"老师，我听说 **{kp}** 可以先看一个具体例子里的第一步。你能不能先讲这一点？"


def _normalize_evidence(raw: Any, action_type: str, evaluation: dict[str, Any]) -> dict[str, str]:
    if isinstance(raw, dict):
        ev_type = raw.get("type") or "none"
        status = raw.get("status") or "none"
        error_type = raw.get("error_type") or ""
        reason = raw.get("reason") or ""
    else:
        ev_type, status, error_type, reason = "none", "none", "", ""

    if ev_type not in EVIDENCE_TYPES:
        ev_type = "none"
    if status not in VERIFICATION_STATUSES:
        status = "none"

    if ev_type == "none" and action_type == "probe":
        correctness = float(evaluation.get("correctness", 0.0) or 0.0)
        depth = float(evaluation.get("depth", 0.0) or 0.0)
        if correctness >= 0.35 and depth >= 0.35:
            ev_type = "explanation"
            status = "passed" if correctness >= 0.45 else "partial"
            reason = reason or "用户给出了可追问的解释"

    if action_type in {"clue", "scaffold_example", "examiner_verify"} and ev_type == "none":
        status = "none"
        reason = reason or "本轮是线索/验证触发，不直接提高掌握度"

    return {
        "type": ev_type,
        "status": status,
        "error_type": str(error_type or ""),
        "reason": str(reason or ""),
    }


def _normalize_turn_payload(
    raw: dict[str, Any],
    *,
    user_input: str = "",
    masteries: list[db.Mastery] | None = None,
    recent_user_inputs: list[str] | None = None,
    force_probe: bool = False,
    settings: dict[str, Any] | None = None,
    mode: str = "study",
    error_logs: list[db.ErrorLog] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    masteries = masteries or []
    recent_user_inputs = recent_user_inputs or ([user_input] if user_input else [])
    settings = {**DEFAULT_STRATEGY_SETTINGS, **(settings or {})}
    settings["probing_intensity"] = _strategy_int(settings.get("probing_intensity"), 3)
    if settings.get("correction_timing") not in {"immediate", "summary_only"}:
        settings["correction_timing"] = "immediate"
    if settings.get("correction_persistence") not in {"gentle", "balanced", "persistent"}:
        settings["correction_persistence"] = "balanced"
    mode = mode if mode in {"study", "goal", "companion"} else "study"
    evaluation = dict(raw.get("evaluation", {}) or {})
    action = dict(raw.get("action", {}) or {})

    entry_status = evaluation.get("entry_status")
    if entry_status not in ENTRY_STATUSES:
        entry_status = _method_entry_from_user(user_input, masteries)
    if entry_status == "no_entry":
        kp_record = _matching_mastery(masteries, action.get("knowledge_point", ""))
        no_recent_steps = _recent_users_have_no_executable_steps(recent_user_inputs)
        if kp_record is not None and not no_recent_steps:
            entry_status = "has_entry"
    if force_probe:
        entry_status = "has_entry"
    evaluation["entry_status"] = entry_status

    action_type = action.get("type") or "ask"
    action_type_changed = False
    understood_claim = _is_understood_claim(user_input)
    allowed_actions = set(_action_types_for_mode(mode))
    if mode != "study":
        if action_type not in allowed_actions:
            action_type = _fallback_action_for_mode(mode, user_input)
            action_type_changed = True
        if mode == "goal" and understood_claim:
            action_type = "verify_done"
            action_type_changed = True
    elif understood_claim:
        action_type = "examiner_verify"
        action_type_changed = True
    elif force_probe:
        action_type = "probe"
        action_type_changed = True
    elif entry_status == "no_entry" and action_type in {"ask", "probe", "next", "recap"}:
        action_type = "clue"
        action_type_changed = True
    elif entry_status == "has_entry" and action_type in {"clue", "scaffold_example"}:
        action_type = "probe"
        action_type_changed = True
    if action_type not in allowed_actions:
        action_type = _fallback_action_for_mode(mode, user_input)
        action_type_changed = True
    raw_evidence = evaluation.get("evidence_for_mastery")
    if not understood_claim:
        if (
            settings.get("probing_intensity", 3) >= 5
            and entry_status == "has_entry"
            and action_type == "ask"
        ):
            action_type = "probe"
            action_type_changed = True
        if (
            settings.get("probing_intensity", 3) < 5
            and action_type in {"ask", "probe"}
            and entry_status == "has_entry"
            and _has_active_errors_for_kp(error_logs, action.get("knowledge_point", ""))
            and float(evaluation.get("correctness", 0.0) or 0.0) < 0.5
        ):
            action_type = "small_lecture"
            action_type_changed = True
        if (
            settings.get("correction_timing") == "summary_only"
            and isinstance(raw_evidence, dict)
            and raw_evidence.get("type") == "correction"
            and action_type in {"ask", "probe", "challenge", "clue", "scaffold_example", "small_lecture", "examiner_verify"}
        ):
            action_type = "recap"
            action_type_changed = True
    action["type"] = action_type

    role = action.get("student_role")
    if role not in STUDENT_ROLES or action_type_changed:
        role = _student_role_for_action(action_type)
    action["student_role"] = role

    if not (action.get("knowledge_point") or "").strip():
        action["knowledge_point"] = "当前方法"
    try:
        action["difficulty"] = float(action.get("difficulty", 0.5) or 0.5)
    except Exception:
        action["difficulty"] = 0.5
    action["note"] = (action.get("note") or "").strip() or "normalized"

    evidence = _normalize_evidence(evaluation.get("evidence_for_mastery"), action_type, evaluation)
    if mode != "study":
        evidence = {
            "type": "none",
            "status": "none",
            "error_type": "",
            "reason": f"{mode} mode does not update mastery",
        }
    evaluation["evidence_for_mastery"] = evidence
    evaluation.setdefault("new_requirements", [])
    evaluation.setdefault("user_emotion", "neutral")
    evaluation["error_pattern"] = str(evaluation.get("error_pattern") or "").strip()[:12]
    evaluation["misconception"] = str(evaluation.get("misconception") or "").strip()[:20]
    evaluation["correctness"] = float(evaluation.get("correctness", 0.0) or 0.0)
    evaluation["depth"] = float(evaluation.get("depth", 0.0) or 0.0)

    return evaluation, action, _build_process_summary(evaluation, action, mode)


def _build_process_summary(evaluation: dict[str, Any], action: dict[str, Any], mode: str = "study") -> str:
    if mode == "goal":
        task = action.get("knowledge_point") or "当前目标"
        blocked = "是" if action.get("type") == "unblock" else "未检测到明确阻塞"
        next_delivery = {
            "decompose": "产出一个更小的可执行步骤",
            "advance": "推进当前步骤的一小步",
            "verify_done": "验收已完成部分并决定下一步",
            "unblock": "先定位卡点并拿到最小反馈",
        }.get(action.get("type"), "继续推进目标")
        return (
            f"当前任务：{task}；"
            f"阻塞点：{blocked}；"
            f"本轮动作：{action.get('type')}；"
            f"下一步交付：{next_delivery}。"
        )
    if mode == "companion":
        emotion = evaluation.get("user_emotion") or "neutral"
        guided = "是" if action.get("type") == "soft_guide" else "否"
        return (
            f"感知到的情绪：{emotion}；"
            f"是否引导：{guided}；"
            f"边界检查：不纠错、不催促、不替用户决定。"
        )
    entry_label = {
        "has_entry": "用户已有方法入口",
        "no_entry": "用户可能还没有方法入口",
        "recall_decay": "用户可能是学过但遗忘",
    }.get(evaluation.get("entry_status"), "入口状态未知")
    role_label = {
        "probing_student": "追问型学生",
        "clue_student": "线索型学生",
        "scaffold_student": "例子脚手架",
        "confused_student": "反例困惑学生",
        "examiner": "考官验证",
        "review_student": "复习回顾",
    }.get(action.get("student_role"), action.get("student_role", "学生"))
    evidence = evaluation.get("evidence_for_mastery") or {}
    next_step = {
        "clue": "等待用户解释线索里的第一步",
        "probe": "继续追问理由、边界或例子",
        "challenge": "用学生口吻抛出反例或矛盾，等用户修正",
        "scaffold_example": "用具体例子搭脚手架，等用户解释第一步",
        "small_lecture": "微讲解后等待用户复述",
        "examiner_verify": "用验证题确认是否真的掌握",
        "recap": "小结后再决定是否推进",
        "next": "切到下一个知识点",
    }.get(action.get("type"), "保持当前学习节奏")
    return (
        f"当前判断：{entry_label}；"
        f"使用依据：{role_label}，掌握度证据 {evidence.get('type', 'none')}/{evidence.get('status', 'none')}；"
        f"本轮策略：{action.get('type')}；"
        f"下一步：{next_step}。"
    )


# --- 公共 API -----------------------------------------------------------------

def create_session(
    db_sess,
    *,
    title: str,
    role: str,
    goal: str,
    deadline: str = "",
    personality: str = "好奇、有点贪玩、容易丧气但能被鼓励",
    mode: str = "study",
    core_self: str = "",
    settings: dict[str, Any] | None = None,
    initial_requirements: list[str] | None = None,
) -> db.Session:
    """新建会话。把初始设定打入 anchor[initial]。"""
    sid = uuid.uuid4().hex[:12]
    persona = {
        "role": role,
        "goal": goal,
        "deadline": deadline,
        "personality": personality,
        "mood": "积极",
    }
    s = db.Session(
        id=sid,
        title=title or f"{role} - {goal}",
        mode=mode or "study",
        core_self=core_self or "",
        persona_json=json.dumps(persona, ensure_ascii=False),
        settings_json=json.dumps(settings or {}, ensure_ascii=False),
        plan_json="[]",
    )
    db_sess.add(s)
    if s.mode == "goal":
        db_sess.add(db.GoalState(session_id=sid, state_json="{}"))
    elif s.mode == "companion":
        db_sess.add(db.CompanionState(session_id=sid, state_json="{}"))
    # 初始锚（最高权重，永不丢失）
    db.add_anchor(db_sess, sid, "initial",
                  f"角色={role}；目标={goal}；截止={deadline or '未设'}",
                  weight=3.0)
    for req in (initial_requirements or []):
        db.add_anchor(db_sess, sid, "requirement", req, weight=1.5)
    db_sess.commit()
    db_sess.refresh(s)
    return s


# --- 压缩 / 摘要 -----------------------------------------------------------

SUMMARY_THRESHOLD = 30     # user+assistant 条数超过此值才压缩
SUMMARY_KEEP_RECENT = 12   # 最近多少条保留原文
RECENT_PROMPT_MESSAGE_LIMIT = 12
RUNTIME_MEMORY_HINT_MAX_CHARS = 1600
RUNTIME_MEMORY_HINT_MAX_ITEMS = 16
SUMMARY_SYSTEM = (
    "你是一个教学对话摘要器。请把以下反转家教对话压缩为 6-12 条要点，严格保留以下信息：\n"
    "  1. 用户表现出的强项、弱项知识点\n"
    "  2. 用户中途提出的偏好 / 诉求 / 约定\n"
    "  3. 用户反复的错误模式或迷思\n"
    "  4. 用户的情绪趋势（是否曾拒绝 / 被说服过）\n"
    "  5. 当前正在讨论的主题\n"
    "输出严格 JSON：{\"summary\": \"<指向用户的要点列表，markdown bullet>\"}"
)


async def _do_summarize(
    persona: dict,
    msgs_to_compress: list[db.Message],
    previous_summary: db.Message | None,
) -> str:
    if not msgs_to_compress:
        return ""
    # mock 模式：不调 LLM，生成结构化 placeholder
    if not llm.has_real_llm():
        roles = [m.content[:50].replace("\n", " ") for m in msgs_to_compress[:3]]
        return (
            f"[mock 摘要] 压缩了 {len(msgs_to_compress)} 条对话\n"
            f"- 角色：{persona.get('role','?')} · 目标：{persona.get('goal','?')}\n"
            f"- 早期开场话题示例：{roles[0] if roles else '(无)'}\n"
            f"- （真 LLM 模式下会输出详细要点列表）"
        )
    convo = "\n".join(f"{m.role}: {m.content}" for m in msgs_to_compress)
    user_block = convo
    if previous_summary is not None:
        user_block = (
            f"此前已有摘要（请整合、不要丢失老要点）：\n{previous_summary.content}\n\n"
            f"新增对话：\n{convo}"
        )
    try:
        raw = await llm.chat_json(
            SUMMARY_SYSTEM,
            [{"role": "user", "content": user_block}],
            temperature=0.2, max_tokens=600,
        )
        return (raw.get("summary") or "").strip() or "（摘要为空）"
    except Exception as e:
        return f"（摘要生成失败: {e}）"


async def maybe_summarize(db_sess, sid: str, *, force: bool = False) -> dict | None:
    """按需压缩早期对话。返回 压缩信息 dict 或 None。

    打包逻辑：
      - 取出上一条 summary（若有）的 cutoff；只看之后的 user/assistant 消息
      - 该部分 < threshold 且非 force → 跳过
      - 压缩 "除了最后 keep_recent 条" 之前的部分
      - LLM 生成摘要，落库为一条 system message (kind=summary, summarized_until_id, summarized_count)
    """
    session = db.get_session(db_sess, sid)
    if session is None:
        return None
    all_msgs = db.list_messages(db_sess, sid, limit=1000)
    if not all_msgs:
        return None

    last_sum = _latest_summary(all_msgs)
    cutoff = int((last_sum.meta() or {}).get("summarized_until_id", 0)) if last_sum else 0

    convo_after = [m for m in all_msgs if m.id > cutoff and m.role in ("user", "assistant")]
    if not force and len(convo_after) < SUMMARY_THRESHOLD:
        return None
    # 保留最近 keep_recent
    to_compress = convo_after[:-SUMMARY_KEEP_RECENT] if len(convo_after) > SUMMARY_KEEP_RECENT else convo_after
    if not to_compress:
        return None

    summary_text = await _do_summarize(session.persona(), to_compress, last_sum)
    until_id = to_compress[-1].id
    db.add_message(db_sess, sid, "system", summary_text, meta={
        "kind": "summary",
        "summarized_until_id": until_id,
        "summarized_count": len(to_compress),
    })
    db_sess.commit()
    return {
        "summarized_count": len(to_compress),
        "summarized_until_id": until_id,
        "summary": summary_text,
    }


OPENING_SUFFIX = """

# 当前情境（重要）
这是会话的**第一句话**，用户（老师）还没说话。请你作为"学生"主动开场。
要求：
1. 用你角色的口吻自然打招呼（一句话即可，别太长，要符合人设的情绪）。
2. 立刻提出**第一个真实的知识点问题**，必须与你的目标（goal）直接相关。
3. 问题难度根据角色当前水平，先从基础开始。
4. `action.type` 必须设为 `"ask"`。
5. `action.knowledge_point` 必须是你这次问的那个具体知识点（短词组）。
6. `evaluation` 字段全部填 0（用户还没回答，无可评估）。
7. `anchor_updates` 留空数组。
"""

GOAL_OPENING_SUFFIX = """

# 当前情境（重要）
这是 goal 模式第一句话，用户还没说话。
要求：
1. 用你角色的口吻自然打招呼。
2. 围绕目标提出一个最小下一步或需要拆解的问题。
3. `action.type` 必须是 `decompose` 或 `advance`。
4. 不要提学习掌握度或知识点考核。
"""

COMPANION_OPENING_SUFFIX = """

# 当前情境（重要）
这是 companion 模式第一句话，用户还没说话。
要求：
1. 用你角色的口吻自然打招呼。
2. 轻轻观察当前状态或邀请用户说一点近况。
3. `action.type` 必须是 `observe` 或 `empathize`。
4. 不要纠错，不要催促，不要进入考官验证。
"""


async def run_opening_turn(db_sess, sid: str) -> TurnResult:
    """会话第一轮：AI 主动求教，不需要用户输入。"""
    session = db.get_session(db_sess, sid)
    if session is None:
        raise ValueError(f"session {sid} not found")

    anchors = db.list_anchors(db_sess, sid)
    mode = _session_mode(session)
    masteries = db.list_mastery(db_sess, sid) if mode == "study" else []
    settings = _strategy_settings(session)

    opening_suffix = {
        "study": OPENING_SUFFIX,
        "goal": GOAL_OPENING_SUFFIX,
        "companion": COMPANION_OPENING_SUFFIX,
    }[mode]
    system = build_system_prompt(session, anchors, masteries) + opening_suffix
    raw = await llm.chat_json(system, [], temperature=0.85, max_tokens=600)

    evaluation, action, process_summary = _normalize_turn_payload(
        raw,
        masteries=masteries,
        settings=settings,
        mode=mode,
    )
    reply = (raw.get("reply") or "").strip() or "（嗯……老师，那我们开始吧？）"
    reply = _discipline_reply_for_role(reply, action)

    db.add_message(db_sess, sid, "assistant", reply, meta={
        "evaluation": evaluation,
        "action": action,
        "opening": True,
        "process_summary": process_summary,
    })
    db_sess.commit()

    return TurnResult(
        reply=reply,
        evaluation=evaluation,
        action=action,
        process_summary=process_summary,
    )


async def run_turn(
    db_sess,
    sid: str,
    user_input: str,
    retriever: Retriever | None = None,
    web_search: websearch.WebSearchProvider | None = None,
) -> TurnResult:
    """执行一轮：评估 → 决策 → 行动。"""
    session = db.get_session(db_sess, sid)
    if session is None:
        raise ValueError(f"session {sid} not found")

    # 门槛：可能压缩早期对话，防漂移 + 控 token
    await maybe_summarize(db_sess, sid)

    anchors = db.list_anchors(db_sess, sid)
    mode = _session_mode(session)
    masteries = db.list_mastery(db_sess, sid) if mode == "study" else []
    settings = _strategy_settings(session)
    due_reviews = db.list_due_reviews(db_sess, sid, datetime.utcnow()) if mode == "study" else []
    error_logs = db.list_error_logs(db_sess, sid) if mode == "study" else []
    history = db.list_messages(db_sess, sid, limit=1000)
    recent_user_inputs = [m.content for m in history if m.role == "user"][-1:] + [user_input]
    force_probe = _previous_assistant_was_clue(history) and _looks_like_observation(user_input)

    summary = _latest_summary(history)
    skip_until_id = 0
    summary_text = None
    if summary is not None:
        skip_until_id = int((summary.meta() or {}).get("summarized_until_id", 0))
        summary_text = summary.content

    kg_context_text = ""
    kg_ctx = None
    if mode == "study":
        try:
            kg_ctx = retrieve_kg_context(db_sess, sid, user_input[:50])
            kg_context_text = kg_ctx.format_for_prompt()
        except Exception:
            pass
    runtime_memory_hint = build_runtime_memory_hint(
        db_sess,
        sid,
        session,
        user_input,
        masteries=masteries,
        error_logs=error_logs,
        kg_ctx=kg_ctx,
    )

    system = build_system_prompt(
        session,
        anchors,
        masteries,
        history_summary=summary_text,
        due_reviews=due_reviews,
        error_logs=error_logs,
        kg_context_text=kg_context_text,
    )
    if runtime_memory_hint:
        system += "\n\n" + runtime_memory_hint
    retrieval_attempted = False
    injected_chunk_ids: set[int] = set()
    active_retriever = retriever or make_default_retriever(db_sess)
    if mode == "study" and _should_inject_clue_retrieval(user_input, masteries):
        retrieval_attempted = True
        hits = active_retriever.search(user_input[:200], session_id=sid, top_k=3)
        if hits:
            injected_chunk_ids = {int(h.chunk_id) for h in hits}
            system += "\n\n" + _format_citable_clues(hits)
    if (
        mode == "study"
        and retrieval_attempted
        and not injected_chunk_ids
        and bool(settings.get("web_search_enabled"))
    ):
        try:
            provider = web_search or websearch.get_web_search_provider()
            web_hits = provider.search(user_input[:200], top_k=3)
            imported_hits: list[Hit] = []
            for hit in web_hits:
                content = (hit.snippet or "").strip()
                if not content:
                    continue
                doc = db.add_document(
                    db_sess,
                    session_id=sid,
                    title=hit.title or hit.url or "Web source",
                    source_type="web",
                    source_uri=hit.url,
                    content=content,
                )
                db_sess.flush()
                chunks = db.list_doc_chunks(db_sess, doc.id)
                if not chunks:
                    continue
                chunk = chunks[0]
                imported_hits.append(
                    Hit(
                        chunk_id=int(chunk.id),
                        doc_id=int(doc.id),
                        title=str(doc.title),
                        content=str(chunk.content),
                        score=0.0,
                    )
                )
            if imported_hits:
                injected_chunk_ids = {int(h.chunk_id) for h in imported_hits}
                system += "\n\n" + _format_citable_clues(imported_hits[:3])
        except Exception:
            pass
    messages = build_messages(history, user_input, skip_until_id=skip_until_id)

    raw = await llm.chat_json(system, messages, temperature=0.85, max_tokens=900)

    evaluation, action, process_summary = _normalize_turn_payload(
        raw,
        user_input=user_input,
        masteries=masteries,
        recent_user_inputs=recent_user_inputs,
        force_probe=force_probe,
        settings=settings,
        mode=mode,
        error_logs=error_logs,
    )
    if due_reviews:
        process_summary += (
            f" 系统检测到 {len(due_reviews)} 个旧知识点到期，"
            "是否带回视用户回复决定。"
        )
    citation_meta: dict[str, Any] = {}
    cited_chunk_ids: list[int] = []
    if action.get("student_role") in {"clue_student", "scaffold_student"}:
        raw_cited = _coerce_cited_chunk_ids(raw.get("cited_chunk_ids"))
        if retrieval_attempted and not injected_chunk_ids:
            process_summary += " [note] 未命中本地资料"
            citation_meta["clue_no_local_doc"] = True
            cited_chunk_ids = []
        elif injected_chunk_ids:
            fake = [c for c in raw_cited if c not in injected_chunk_ids]
            cited_chunk_ids = [c for c in raw_cited if c in injected_chunk_ids]
            if fake:
                process_summary += " [warn] clue_fake_citation"
                citation_meta["clue_fake_citation"] = fake
            if not cited_chunk_ids:
                process_summary += " [warn] clue_no_citation"
                citation_meta["clue_no_citation"] = True
    elif retrieval_attempted and injected_chunk_ids:
        citation_meta["clue_predicted_but_not_used"] = sorted(injected_chunk_ids)
    reply = (raw.get("reply") or "").strip() or "（……我有点走神了，你刚才说啥？）"
    reply = _discipline_reply_for_role(reply, action)
    anchor_updates = raw.get("anchor_updates", []) or []

    # 落库：先 user 后 assistant
    db.add_message(db_sess, sid, "user", user_input, meta={"turn_input": True})
    assistant_meta = {
        "evaluation": evaluation,
        "action": action,
        "process_summary": process_summary,
        "evidence_episode_ids": [],
        "cited_chunk_ids": cited_chunk_ids,
        **citation_meta,
    }
    assistant_msg = db.add_message(db_sess, sid, "assistant", reply, meta=assistant_meta)
    db_sess.flush()

    # 更新掌握度
    kp = (action.get("knowledge_point") or "").strip()
    if kp and mode == "study":
        evidence = evaluation.get("evidence_for_mastery") or {}
        if evidence.get("type") != "none" and evidence.get("status") in {"passed", "partial", "failed"}:
            assistant_meta["evidence_episode_ids"] = [assistant_msg.id]
            assistant_msg.meta_json = json.dumps(assistant_meta, ensure_ascii=False)
        try:
            db.upsert_mastery(
                db_sess, sid, kp,
                correctness=float(evaluation.get("correctness", 0.0) or 0.0),
                depth=float(evaluation.get("depth", 0.0) or 0.0),
                evidence_type=evidence.get("type", "none"),
                verification_status=evidence.get("status", "none"),
                evidence_episode_id=assistant_msg.id,
                error_type=evidence.get("error_type", ""),
                updated_reason=evidence.get("reason", ""),
                review_frequency=settings.get("review_frequency", "normal"),
            )
        except Exception:
            pass
        pattern = (evaluation.get("error_pattern") or "").strip()
        misconception = (evaluation.get("misconception") or "").strip()
        correctness = float(evaluation.get("correctness", 0.0) or 0.0)
        if misconception:
            db.upsert_error_log(db_sess, sid, kp, misconception, evidence_episode_id=assistant_msg.id)
        if action.get("type") == "examiner_verify" and pattern:
            if correctness < 0.5:
                db.upsert_error_log(db_sess, sid, kp, pattern, evidence_episode_id=assistant_msg.id)
            elif (
                correctness >= 0.8
                and evidence.get("type") == "delayed_retrieval"
                and evidence.get("status") == "passed"
            ):
                db.resolve_error_pattern(db_sess, sid, kp, pattern)
        if evidence.get("type") == "correction" and evidence.get("status") == "passed":
            resolved_pattern = misconception or pattern or (evidence.get("error_type") or "").strip()
            if resolved_pattern:
                db.resolve_error_pattern(db_sess, sid, kp, resolved_pattern)

    # 入新锚
    for upd in anchor_updates:
        if not isinstance(upd, dict):
            continue
        content = (upd.get("content") or "").strip()
        if not content:
            continue
        kind = upd.get("kind") or "requirement"
        weight = float(upd.get("weight", 1.0) or 1.0)
        db.add_anchor(db_sess, sid, kind, content, weight=weight)

    if mode == "study":
        allow_kg, _kg_reason = kg_gate.should_extract(settings, user_input, evaluation, action)
        if allow_kg:
            try:
                await _kg_extract(
                    db_sess,
                    sid,
                    evaluation=evaluation,
                    action=action,
                    episode_id=assistant_msg.id,
                )
            except Exception:
                pass

    if due_reviews and any(k in user_input for k in ("不想复习", "先不管", "跳过", "以后再说")):
        for dr in due_reviews:
            try:
                mark_review_pending(db_sess, sid, dr.knowledge_point, episode_id=assistant_msg.id)
            except Exception:
                pass

    db_sess.commit()

    return TurnResult(
        reply=reply,
        evaluation=evaluation,
        action=action,
        anchor_updates=anchor_updates,
        process_summary=process_summary,
    )
