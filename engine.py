"""核心引擎 —— 反转家教 Agent 的 评估→决策→行动 状态机。

每一轮（用户发一句话 → Agent 回复一句话）的完整流程：

  1. load_context(sid)        加载 persona / anchors / 最近消息 / 掌握度
  2. build_system_prompt(...) 注入 persona + anchors + 掌握度 + 工具说明
  3. llm.chat_json(...)       一次 LLM 调用，结构化输出
  4. parse + apply            更新 mastery / 新 anchor 入库
  5. persist(user, assistant) 落库两条消息
  6. return reply + meta      回前端/适配器

设计要点：
- 工具调用以"action.type"形式表达（ask / probe / emote / persuade / next / recap）
- 锚点是防漂移的核心，每轮强制注入
- 用户的新诉求由 LLM 在 anchor_updates 中识别，自动入库
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import db
import llm

# --- 工具白名单 ---------------------------------------------------------------

ACTION_TYPES = {
    "ask":      "向用户提一个新问题（默认动作）",
    "probe":    "用户答得对但浅，追问'为什么'/举例/边界",
    "emote":    "表达情绪反应（困惑/恍然大悟/沮丧），引导用户继续解释",
    "persuade": "用户表现出拒绝/疲惫，用情感方式说服其继续（撒娇/失望/激励，避免说教）",
    "next":     "切换到下一个知识点（用户已掌握 或 当前点过难需要降阶）",
    "recap":    "做一次小结/回顾，巩固刚学的内容",
}

USER_EMOTIONS = ["fresh", "neutral", "engaged", "tired", "frustrated", "refusing"]

# --- System Prompt 模板 -------------------------------------------------------

SYSTEM_TEMPLATE = """你是一个"反转家教 Agent"。你**表面上**是一个学生角色，**实际目的**是通过向用户请教来让用户学习（教即是学）。

# 你扮演的角色 (Persona)
{persona_block}

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
- 用户**完全不会** → `next` 或降难度；不要让用户尴尬。
- 用户**拒绝/疲惫** → `persuade`：用你角色的情绪说服（撒娇、装可怜、激将、共情），**不要说教**。
- 用户**透彻** → `recap` 一次再 `next`。
- 用户提到**新需求/新方向**（如"我想重点搞 XX"）→ 必须放入 `anchor_updates`，权重 1.0~2.0。
- **永远不要**自己回答你刚提的问题；你是学生，等用户教你。

# 输出格式（严格 JSON，禁止任何额外文字）
{{
  "evaluation": {{
    "correctness": 0.0-1.0,
    "depth":       0.0-1.0,
    "user_emotion": "fresh|neutral|engaged|tired|frustrated|refusing",
    "new_requirements": ["..."]    // 用户本轮提出的新诉求/约束（无则空数组）
  }},
  "action": {{
    "type": "ask|probe|emote|persuade|next|recap",
    "knowledge_point": "本轮聚焦的知识点（短词组）",
    "difficulty": 0.0-1.0,
    "note": "为何选这个动作（一句话）"
  }},
  "reply": "你（以学生身份）对用户说的下一句话。自然、口语、有情绪。",
  "anchor_updates": [
    {{"kind": "requirement|constraint|milestone", "content": "...", "weight": 1.0}}
  ]
}}
"""


# --- 数据类 -------------------------------------------------------------------

@dataclass
class TurnResult:
    reply: str
    evaluation: dict[str, Any]
    action: dict[str, Any]
    anchor_updates: list[dict[str, Any]] = field(default_factory=list)


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
        bar = "█" * int(m.level * 10) + "░" * (10 - int(m.level * 10))
        lines.append(f"- {m.knowledge_point}: {bar} {m.level:.2f} (试 {m.attempts} 次)")
    return "\n".join(lines)


def _format_actions() -> str:
    return "\n".join(f"- `{k}`: {v}" for k, v in ACTION_TYPES.items())


def build_system_prompt(
    session: db.Session,
    anchors: list[db.Anchor],
    masteries: list[db.Mastery],
    history_summary: str | None = None,
) -> str:
    base = SYSTEM_TEMPLATE.format(
        persona_block=_format_persona(session.persona()),
        anchors_block=_format_anchors(anchors),
        plan_block=_format_plan(session.plan()),
        mastery_block=_format_mastery(masteries),
        actions_block=_format_actions(),
    )
    if history_summary:
        base += (
            "\n\n# 早期对话摘要（已压缩，其后附最近原文）\n"
            f"{history_summary}\n"
        )
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
    for m in msgs[-30:]:  # 取最近 30 条作为滑动窗口
        if m.id <= skip_until_id:
            continue
        if m.role in ("user", "assistant"):
            out.append({"role": m.role, "content": m.content})
    if user_input is not None:
        out.append({"role": "user", "content": user_input})
    return out


# --- 公共 API -----------------------------------------------------------------

def create_session(
    db_sess,
    *,
    title: str,
    role: str,
    goal: str,
    deadline: str = "",
    personality: str = "好奇、有点贪玩、容易丧气但能被鼓励",
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
        persona_json=json.dumps(persona, ensure_ascii=False),
        plan_json="[]",
    )
    db_sess.add(s)
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


async def run_opening_turn(db_sess, sid: str) -> TurnResult:
    """会话第一轮：AI 主动求教，不需要用户输入。"""
    session = db.get_session(db_sess, sid)
    if session is None:
        raise ValueError(f"session {sid} not found")

    anchors = db.list_anchors(db_sess, sid)
    masteries = db.list_mastery(db_sess, sid)

    system = build_system_prompt(session, anchors, masteries) + OPENING_SUFFIX
    raw = await llm.chat_json(system, [], temperature=0.85, max_tokens=600)

    evaluation = raw.get("evaluation", {}) or {}
    action = raw.get("action", {}) or {}
    reply = (raw.get("reply") or "").strip() or "（嗯……老师，那我们开始吧？）"

    db.add_message(db_sess, sid, "assistant", reply, meta={
        "evaluation": evaluation,
        "action": action,
        "opening": True,
    })
    db_sess.commit()

    return TurnResult(reply=reply, evaluation=evaluation, action=action)


async def run_turn(db_sess, sid: str, user_input: str) -> TurnResult:
    """执行一轮：评估 → 决策 → 行动。"""
    session = db.get_session(db_sess, sid)
    if session is None:
        raise ValueError(f"session {sid} not found")

    # 门槛：可能压缩早期对话，防漂移 + 控 token
    await maybe_summarize(db_sess, sid)

    anchors = db.list_anchors(db_sess, sid)
    masteries = db.list_mastery(db_sess, sid)
    history = db.list_messages(db_sess, sid, limit=1000)

    summary = _latest_summary(history)
    skip_until_id = 0
    summary_text = None
    if summary is not None:
        skip_until_id = int((summary.meta() or {}).get("summarized_until_id", 0))
        summary_text = summary.content

    system = build_system_prompt(session, anchors, masteries, history_summary=summary_text)
    messages = build_messages(history, user_input, skip_until_id=skip_until_id)

    raw = await llm.chat_json(system, messages, temperature=0.85, max_tokens=900)

    evaluation = raw.get("evaluation", {}) or {}
    action = raw.get("action", {}) or {}
    reply = (raw.get("reply") or "").strip() or "（……我有点走神了，你刚才说啥？）"
    anchor_updates = raw.get("anchor_updates", []) or []

    # 落库：先 user 后 assistant
    db.add_message(db_sess, sid, "user", user_input, meta={"turn_input": True})
    db.add_message(db_sess, sid, "assistant", reply, meta={
        "evaluation": evaluation,
        "action": action,
    })

    # 更新掌握度
    kp = (action.get("knowledge_point") or "").strip()
    if kp:
        try:
            db.upsert_mastery(
                db_sess, sid, kp,
                correctness=float(evaluation.get("correctness", 0.0) or 0.0),
                depth=float(evaluation.get("depth", 0.0) or 0.0),
            )
        except Exception:
            pass

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

    db_sess.commit()

    return TurnResult(
        reply=reply,
        evaluation=evaluation,
        action=action,
        anchor_updates=anchor_updates,
    )
