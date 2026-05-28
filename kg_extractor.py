"""Knowledge-graph extractor for updating graph state from each tutor turn."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session as DbSession

import db
import llm


KIND_CONCEPT = "concept"
KIND_ERROR = "error_pattern"
KIND_PREFERENCE = "preference"
KIND_METHOD = "method"

REL_LEARNING = "学习中"
REL_MASTERED = "已掌握"
REL_CONFUSED = "容易混淆"
REL_MISUNDERSTOOD = "曾误解"
REL_PREREQ = "前置于"
REL_USED_FOR = "常用于"
REL_PREFERENCE = "偏好"
REL_ERROR_ON = "错在"


async def extract_from_turn(
    db_sess: DbSession,
    sid: str,
    *,
    evaluation: dict[str, Any],
    action: dict[str, Any],
    episode_id: int | None = None,
) -> list[dict[str, Any]]:
    """Extract knowledge-graph updates from a single conversation turn."""
    if llm.has_real_llm():
        return await _llm_extract(db_sess, sid, evaluation=evaluation, action=action, episode_id=episode_id)
    return _rule_extract(db_sess, sid, evaluation=evaluation, action=action, episode_id=episode_id)


def _rule_extract(
    db_sess: DbSession,
    sid: str,
    *,
    evaluation: dict[str, Any],
    action: dict[str, Any],
    episode_id: int | None = None,
) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    kp = (action.get("knowledge_point") or "").strip()
    if not kp:
        return ops

    entry_status = evaluation.get("entry_status", "has_entry")
    evidence = evaluation.get("evidence_for_mastery") or {}
    correctness = float(evaluation.get("correctness", 0.0) or 0.0)
    error_pattern = (evaluation.get("error_pattern") or "").strip()

    concept = db.upsert_kg_node(db_sess, sid, KIND_CONCEPT, kp, episode_id=episode_id)
    ops.append({"op": "upsert_node", "kind": KIND_CONCEPT, "name": kp})

    user_node = db.upsert_kg_node(db_sess, sid, "person", "用户", episode_id=episode_id)

    if correctness >= 0.7 and evidence.get("status") == "passed":
        db.supersede_kg_edge(
            db_sess,
            sid,
            user_node.id,
            concept.id,
            REL_LEARNING,
            new_weight=0.0,
            episode_id=episode_id,
        )
        db.upsert_kg_edge(
            db_sess,
            sid,
            user_node.id,
            concept.id,
            REL_MASTERED,
            weight=correctness,
            episode_id=episode_id,
        )
        ops.append({"op": "mastered", "kp": kp})
    elif entry_status == "no_entry":
        db.upsert_kg_edge(
            db_sess,
            sid,
            user_node.id,
            concept.id,
            REL_LEARNING,
            weight=0.1,
            episode_id=episode_id,
        )
        ops.append({"op": "learning_no_entry", "kp": kp})
    else:
        db.upsert_kg_edge(
            db_sess,
            sid,
            user_node.id,
            concept.id,
            REL_LEARNING,
            weight=max(0.2, correctness),
            episode_id=episode_id,
        )
        ops.append({"op": "learning", "kp": kp})

    if error_pattern:
        err_node = db.upsert_kg_node(
            db_sess,
            sid,
            KIND_ERROR,
            error_pattern,
            properties={"kp": kp, "correctness": correctness},
            episode_id=episode_id,
        )
        db.upsert_kg_edge(
            db_sess,
            sid,
            user_node.id,
            err_node.id,
            REL_ERROR_ON,
            weight=1.0,
            properties={"kp": kp},
            episode_id=episode_id,
        )
        ops.append({"op": "error", "pattern": error_pattern, "kp": kp})

    if (
        evidence.get("status") == "passed"
        and evidence.get("type") in ("correction", "delayed_retrieval")
        and error_pattern
    ):
        err_node = db.find_kg_node(db_sess, sid, KIND_ERROR, error_pattern)
        if err_node:
            for edge in db.list_kg_edges(db_sess, sid, node_id=err_node.id, relation=REL_ERROR_ON):
                db.invalidate_kg_edge(db_sess, sid, edge.id)
            ops.append({"op": "resolve_error", "pattern": error_pattern})

    if entry_status == "recall_decay":
        db.upsert_kg_edge(
            db_sess,
            sid,
            user_node.id,
            concept.id,
            REL_MISUNDERSTOOD,
            weight=0.5,
            properties={"reason": "recall_decay"},
            episode_id=episode_id,
        )
        ops.append({"op": "recall_decay", "kp": kp})

    db_sess.flush()
    return ops


KG_EXTRACT_SYSTEM = """你是一个知识图谱抽取器。根据以下学习对话的评估结果，输出需要更新的图谱节点和边。

输出严格 JSON：
{
  "nodes": [
    {"kind": "concept|error_pattern|preference|method", "name": "...", "properties": {}}
  ],
  "edges": [
    {"source_kind": "...", "source_name": "...", "target_kind": "...", "target_name": "...",
     "relation": "学习中|已掌握|容易混淆|曾误解|前置于|常用于|偏好|错在",
     "weight": 0.0-1.0, "properties": {}}
  ],
  "invalidate_edges": [
    {"source_name": "...", "target_name": "...", "relation": "..."}
  ]
}

规则：
- 每轮最多输出 5 个节点、5 条边
- 如果没有值得抽取的内容，输出空数组
- 不要编造用户没有表达过的关系
"""


async def _llm_extract(
    db_sess: DbSession,
    sid: str,
    *,
    evaluation: dict[str, Any],
    action: dict[str, Any],
    episode_id: int | None = None,
) -> list[dict[str, Any]]:
    context = json.dumps({"evaluation": evaluation, "action": action}, ensure_ascii=False)
    try:
        raw = await llm.chat_json(
            KG_EXTRACT_SYSTEM,
            [{"role": "user", "content": context}],
            temperature=0.2,
            max_tokens=400,
        )
    except Exception:
        return _rule_extract(db_sess, sid, evaluation=evaluation, action=action, episode_id=episode_id)

    ops: list[dict[str, Any]] = []

    for n in (raw.get("nodes") or [])[:5]:
        kind = (n.get("kind") or "concept").strip()
        name = (n.get("name") or "").strip()
        if not name:
            continue
        db.upsert_kg_node(
            db_sess,
            sid,
            kind,
            name,
            properties=n.get("properties"),
            episode_id=episode_id,
        )
        ops.append({"op": "upsert_node", "kind": kind, "name": name})

    for e in (raw.get("edges") or [])[:5]:
        src = db.find_kg_node(db_sess, sid, e.get("source_kind", "concept"), e.get("source_name", ""))
        tgt = db.find_kg_node(db_sess, sid, e.get("target_kind", "concept"), e.get("target_name", ""))
        if src and tgt:
            db.upsert_kg_edge(
                db_sess,
                sid,
                src.id,
                tgt.id,
                (e.get("relation") or "related").strip(),
                weight=float(e.get("weight", 1.0) or 1.0),
                properties=e.get("properties"),
                episode_id=episode_id,
            )
            ops.append({"op": "upsert_edge", "src": src.name, "tgt": tgt.name, "rel": e.get("relation")})

    for inv in (raw.get("invalidate_edges") or [])[:5]:
        src = db.find_kg_node(db_sess, sid, "concept", inv.get("source_name", ""))
        tgt = db.find_kg_node(db_sess, sid, "concept", inv.get("target_name", ""))
        if src and tgt:
            for edge in db.list_kg_edges(db_sess, sid, node_id=src.id, relation=inv.get("relation")):
                if edge.target_id == tgt.id:
                    db.invalidate_kg_edge(db_sess, sid, edge.id)
                    ops.append({"op": "invalidate", "src": src.name, "tgt": tgt.name, "rel": inv.get("relation")})

    db_sess.flush()
    return ops
