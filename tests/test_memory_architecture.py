from __future__ import annotations

from datetime import datetime

import httpx
import pytest

import db
import engine
import kg_extractor as kg
from server import app


def _session(db_sess, *, personality: str = "preset-calm-long-tag") -> db.Session:
    s = engine.create_session(
        db_sess,
        title="memory architecture",
        role="student",
        goal="learn calculus",
        personality=personality,
    )
    db_sess.commit()
    return s


def _assistant_payload(kp: str = "chain rule") -> dict:
    return {
        "reply": "teacher, I am still testing the idea.",
        "evaluation": {
            "entry_status": "has_entry",
            "correctness": 0.2,
            "depth": 0.2,
            "misconception": "",
            "error_pattern": "",
            "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
        },
        "action": {
            "type": "probe",
            "student_role": "probing_student",
            "knowledge_point": kp,
            "target": "explain",
            "reason": "test",
            "next_prompt": "why?",
        },
        "anchor_updates": [],
    }


@pytest.mark.asyncio
async def test_long_chat_prompt_uses_summary_and_recent_window(db_sess, monkeypatch):
    s = _session(db_sess)
    for i in range(10):
        db.add_message(db_sess, s.id, "user", f"OLD_RAW_USER_{i}")
        db.add_message(db_sess, s.id, "assistant", f"OLD_RAW_ASSISTANT_{i}")
    db_sess.flush()
    cutoff_id = db.list_messages(db_sess, s.id, limit=1000)[-1].id
    db.add_message(
        db_sess,
        s.id,
        "system",
        "SUMMARY_CARRIES_OLD_CHAT",
        meta={"kind": "summary", "summarized_until_id": cutoff_id, "summarized_count": 20},
    )
    for i in range(16):
        role = "user" if i % 2 == 0 else "assistant"
        db.add_message(db_sess, s.id, role, f"RECENT_RAW_{i}")
    db_sess.commit()

    async def no_summarize(*args, **kwargs):
        return None

    captured: dict = {}

    async def fake_chat_json(system, messages, **kwargs):
        captured["system"] = system
        captured["messages"] = messages
        return _assistant_payload()

    monkeypatch.setattr(engine, "maybe_summarize", no_summarize)
    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "CURRENT_INPUT")

    assert "SUMMARY_CARRIES_OLD_CHAT" in captured["system"]
    assert len(captured["messages"]) <= engine.RECENT_PROMPT_MESSAGE_LIMIT + 1
    assert not any("OLD_RAW" in m["content"] for m in captured["messages"])
    assert captured["messages"][-1] == {"role": "user", "content": "CURRENT_INPUT"}


@pytest.mark.asyncio
async def test_runtime_memory_hint_is_bounded_and_uses_behavior_profile(db_sess, monkeypatch):
    s = _session(db_sess, personality="preset anxious but persistent")
    user = db.upsert_kg_node(db_sess, s.id, "person", "用户")
    for i in range(40):
        db.upsert_mastery(
            db_sess,
            s.id,
            f"unrelated mastery {i}",
            correctness=0.9,
            depth=0.8,
            evidence_type="retrieval",
            verification_status="passed",
        )
        db.upsert_error_log(db_sess, s.id, f"unrelated kp {i}", f"err-{i}", evidence_episode_id=None)
    trait = db.upsert_kg_node(
        db_sess,
        s.id,
        "persona_trait",
        "needs diagram-first hints",
        properties={"source": "behavior", "weight": 0.8},
    )
    pref = db.upsert_kg_node(db_sess, s.id, kg.KIND_PREFERENCE, "diagram-first explanation")
    db.upsert_kg_edge(db_sess, s.id, user.id, trait.id, "profile_trait", weight=0.8)
    db.upsert_kg_edge(db_sess, s.id, user.id, pref.id, kg.REL_PREFERENCE, weight=0.9)
    db_sess.commit()

    captured: dict = {}

    async def fake_chat_json(system, messages, **kwargs):
        captured["system"] = system
        return _assistant_payload("chain rule")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "chain rule diagram")

    hint = captured["system"].split("# runtime_memory_hint", 1)[1]
    assert len(hint) <= engine.RUNTIME_MEMORY_HINT_MAX_CHARS + 80
    assert "needs diagram-first hints" in hint
    assert "diagram-first explanation" in hint
    assert db.get_session(db_sess, s.id).persona()["personality"] == "preset anxious but persistent"


@pytest.mark.asyncio
async def test_kg_cleaner_filters_process_nodes_and_keeps_semantic_nodes(db_sess, monkeypatch):
    s = _session(db_sess)

    monkeypatch.setattr(kg.llm, "has_real_llm", lambda: True)

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "nodes": [
                {"kind": "background_reply", "name": "后台回复", "properties": {}},
                {"kind": "free_reply", "name": "模型自由回复", "properties": {}},
                {"kind": "concept", "name": "chain rule", "properties": {}},
                {"kind": "preference", "name": "diagram-first explanation", "properties": {}},
            ],
            "edges": [],
            "invalidate_edges": [],
        }

    monkeypatch.setattr(kg.llm, "chat_json", fake_chat_json)

    await kg.extract_from_turn(
        db_sess,
        s.id,
        evaluation={"correctness": 0.2, "entry_status": "has_entry", "evidence_for_mastery": {}},
        action={"knowledge_point": "chain rule"},
        episode_id=None,
    )

    nodes = db.list_kg_nodes(db_sess, s.id, status="")
    assert {n.kind for n in nodes}.isdisjoint({"background_reply", "free_reply"})
    assert db.find_kg_node(db_sess, s.id, "concept", "chain rule") is not None
    assert db.find_kg_node(db_sess, s.id, "preference", "diagram-first explanation") is not None


@pytest.mark.asyncio
async def test_memory_api_filters_process_nodes_and_keeps_session_isolation(db_sess):
    s = _session(db_sess)
    other = _session(db_sess, personality="other")
    db.upsert_kg_node(db_sess, s.id, "concept", "visible semantic")
    db.upsert_kg_node(db_sess, other.id, "concept", "other semantic")
    db_sess.add(
        db.KGNode(
            session_id=s.id,
            kind="background_reply",
            name="后台回复",
            properties_json="{}",
            source_episode_ids="[]",
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            status="active",
        )
    )
    db_sess.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/sessions/{s.id}/memory")

    assert r.status_code == 200
    kg_nodes = r.json()["kg_nodes"]
    assert any(n["name"] == "visible semantic" for n in kg_nodes)
    assert all(n["kind"] != "background_reply" for n in kg_nodes)
    assert all(n["name"] != "other semantic" for n in kg_nodes)
