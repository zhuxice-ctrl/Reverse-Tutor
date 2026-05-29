"""Knowledge-graph retrieval for prompt context and strategy hints."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session as DbSession

import db


PREREQ_MASTERY_THRESHOLD = 0.5


@dataclass
class KGContext:
    """Retrieved graph context ready for system-prompt injection."""
    related_concepts: list[str] = field(default_factory=list)
    prereq_gaps: list[str] = field(default_factory=list)
    historical_errors: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    misunderstandings: list[str] = field(default_factory=list)
    mastery_edges: list[dict[str, Any]] = field(default_factory=list)
    pending_review_kps: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([
            self.related_concepts,
            self.prereq_gaps,
            self.historical_errors,
            self.preferences,
            self.misunderstandings,
            self.mastery_edges,
            self.pending_review_kps,
        ])

    def format_for_prompt(self) -> str:
        if self.is_empty():
            return ""
        lines = ["# 知识图谱上下文"]
        if self.related_concepts:
            lines.append("## 相关/前置概念")
            for c in self.related_concepts[:8]:
                lines.append(f"- {c}")
        if self.prereq_gaps:
            lines.append("## 前置缺口")
            for gap in self.prereq_gaps[:5]:
                lines.append(f"- {gap}")
            first_gap = self.prereq_gaps[0]
            lines.append(
                "当存在前置缺口时，AI 应先以学生身份确认/回补前置点，例如："
                f"老师，要学这个我是不是得先搞懂 {first_gap}？我对 {first_gap} 还有点虚。"
                "确认后再继续；不要变成老师讲解。"
            )
        if self.historical_errors:
            lines.append("## 用户历史错因")
            for e in self.historical_errors[:5]:
                lines.append(f"- {e}")
            lines.append("请在策略选择时参考这些错因，避免用户再犯。")
        if self.misunderstandings:
            lines.append("## 用户曾误解")
            for m in self.misunderstandings[:5]:
                lines.append(f"- {m}")
            lines.append("如果当前 KP 与上述误解相关，优先澄清而非直接追问。")
        if self.preferences:
            lines.append("## 用户学习偏好")
            for p in self.preferences[:3]:
                lines.append(f"- {p}")
        if self.pending_review_kps:
            lines.append("## 挂起待复习")
            for k in self.pending_review_kps[:3]:
                lines.append(f"- {k}（用户之前拒绝复习，可在合适时机轻量带回）")
        return "\n".join(lines) + "\n"


def detect_prereq_gaps(
    db_sess: DbSession,
    sid: str,
    current_kp: str,
    mastery_threshold: float = PREREQ_MASTERY_THRESHOLD,
) -> list[str]:
    """Return prerequisite concepts for current_kp that are not mastered enough."""
    kp = (current_kp or "").strip()
    if not kp:
        return []

    kp_node = db.find_kg_node(db_sess, sid, "concept", kp)
    if not kp_node:
        return []

    masteries = {m.knowledge_point: m for m in db.list_mastery(db_sess, sid)}
    gaps: list[str] = []
    seen: set[str] = set()
    prereq_edges = db.list_kg_edges(db_sess, sid, node_id=kp_node.id, relation="前置于")
    for edge in prereq_edges:
        if edge.target_id != kp_node.id:
            continue
        prereq_node = db.get_kg_node(db_sess, sid, edge.source_id)
        if not prereq_node or prereq_node.name in seen:
            continue
        mastery = masteries.get(prereq_node.name)
        level = float(mastery.level or 0.0) if mastery else 0.0
        score_level = float(mastery.mastery_score or 0.0) / 100.0 if mastery else 0.0
        if max(level, score_level) < mastery_threshold:
            gaps.append(prereq_node.name)
            seen.add(prereq_node.name)
    return gaps


def retrieve_kg_context(
    db_sess: DbSession,
    sid: str,
    current_kp: str,
    *,
    include_pending_review: bool = True,
) -> KGContext:
    """Retrieve graph context related to the current knowledge point."""
    ctx = KGContext()
    kp = (current_kp or "").strip()
    if not kp:
        return ctx

    kp_node = db.find_kg_node(db_sess, sid, "concept", kp)
    ctx.prereq_gaps = detect_prereq_gaps(db_sess, sid, kp)

    all_concepts = db.list_kg_nodes(db_sess, sid, kind="concept")
    connected_ids: set[int] = set()
    if kp_node:
        edges = db.list_kg_edges(db_sess, sid, node_id=kp_node.id)
        connected_ids = {e.source_id for e in edges} | {e.target_id for e in edges}
    for c in all_concepts:
        if c.name == kp:
            continue
        if kp_node and c.id in connected_ids:
            ctx.related_concepts.append(c.name)
            continue
        if kp in c.name or c.name in kp:
            ctx.related_concepts.append(c.name)

    if kp_node:
        prereq_edges = db.list_kg_edges(db_sess, sid, node_id=kp_node.id, relation="前置于")
        for e in prereq_edges:
            prereq_node = db.get_kg_node(db_sess, sid, e.source_id if e.target_id == kp_node.id else e.target_id)
            if prereq_node:
                marked = f"[前置] {prereq_node.name}"
                if marked not in ctx.related_concepts:
                    ctx.related_concepts.insert(0, marked)

    user_node = db.find_kg_node(db_sess, sid, "person", "用户")
    if user_node:
        error_edges = db.list_kg_edges(db_sess, sid, node_id=user_node.id, relation="错在")
        for e in error_edges:
            err_node = db.get_kg_node(db_sess, sid, e.target_id)
            if err_node:
                props = e.properties()
                err_kp = props.get("kp", "")
                if not err_kp or err_kp == kp or kp in err_kp or err_kp in kp:
                    ctx.historical_errors.append(err_node.name)

    if user_node and kp_node:
        misunderstand_edges = db.list_kg_edges(db_sess, sid, node_id=kp_node.id, relation="曾误解")
        for e in misunderstand_edges:
            props = e.properties()
            reason = props.get("reason", "")
            ctx.misunderstandings.append(f"{kp}: {reason}" if reason else kp)

    if user_node:
        pref_edges = db.list_kg_edges(db_sess, sid, node_id=user_node.id, relation="偏好")
        for e in pref_edges:
            pref_node = db.get_kg_node(db_sess, sid, e.target_id)
            if pref_node:
                ctx.preferences.append(pref_node.name)

    if include_pending_review:
        pending_edges = db.list_kg_edges(db_sess, sid, relation="挂起复习")
        for e in pending_edges:
            target = db.get_kg_node(db_sess, sid, e.target_id)
            if target:
                ctx.pending_review_kps.append(target.name)

    return ctx


def mark_review_pending(db_sess: DbSession, sid: str, kp: str, *, episode_id: int | None = None) -> None:
    """Mark a review as pending when the user declines to review it now."""
    user_node = db.upsert_kg_node(db_sess, sid, "person", "用户")
    kp_node = db.upsert_kg_node(db_sess, sid, "concept", kp)
    db.upsert_kg_edge(
        db_sess,
        sid,
        user_node.id,
        kp_node.id,
        "挂起复习",
        weight=0.5,
        properties={"reason": "用户拒绝复习"},
        episode_id=episode_id,
    )


def clear_review_pending(db_sess: DbSession, sid: str, kp: str) -> None:
    """Clear a pending-review marker after the review is handled."""
    user_node = db.find_kg_node(db_sess, sid, "person", "用户")
    kp_node = db.find_kg_node(db_sess, sid, "concept", kp)
    if user_node and kp_node:
        for edge in db.list_kg_edges(db_sess, sid, node_id=kp_node.id, relation="挂起复习"):
            if edge.source_id == user_node.id:
                db.invalidate_kg_edge(db_sess, sid, edge.id)
