from __future__ import annotations

import re

import httpx
import pytest

import db
import engine
from server import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _payload(*, cited: list[int], reply: str = "I can cite that source."):
    return {
        "evaluation": {
            "correctness": 0.0,
            "depth": 0.0,
            "entry_status": "no_entry",
            "evidence_for_mastery": {
                "type": "none",
                "status": "none",
                "error_type": "",
                "reason": "",
            },
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": "clue",
            "student_role": "clue_student",
            "knowledge_point": "calculus",
            "difficulty": 0.5,
            "note": "mock",
        },
        "reply": reply,
        "cited_chunk_ids": cited,
        "anchor_updates": [],
    }


def _import_doc(db_sess, session_id: str | None = None):
    doc = db.add_document(
        db_sess,
        session_id=session_id,
        title="Calculus Guide",
        source_type="md",
        source_uri="local.md",
        content="calculus guide says to inspect the first useful entry point. " * 10,
    )
    db_sess.commit()
    return doc, db.list_doc_chunks(db_sess, doc.id)[0]


def test_resolve_cited_chunks_preserves_order_and_skips_missing(db_sess):
    first = db.add_document(
        db_sess,
        session_id=None,
        title="First Source",
        source_type="txt",
        source_uri="first.txt",
        content="first snippet content " * 10,
    )
    second = db.add_document(
        db_sess,
        session_id=None,
        title="Second Source",
        source_type="web",
        source_uri="https://example.com/second",
        content="second snippet content " * 10,
    )
    db_sess.commit()
    first_chunk = db.list_doc_chunks(db_sess, first.id)[0]
    second_chunk = db.list_doc_chunks(db_sess, second.id)[0]

    sources = db.resolve_cited_chunks(db_sess, [second_chunk.id, 999999, first_chunk.id])

    assert [s["chunk_id"] for s in sources] == [second_chunk.id, first_chunk.id]
    assert [s["title"] for s in sources] == ["Second Source", "First Source"]
    assert sources[0]["source_type"] == "web"
    assert sources[0]["source_uri"] == "https://example.com/second"
    assert sources[0]["snippet"]


async def test_message_sources_endpoint_returns_cited_source(client, db_sess, monkeypatch):
    session = engine.create_session(db_sess, title="", role="student", goal="learn")
    doc, chunk = _import_doc(db_sess, session.id)

    async def fake_chat_json(system, messages, **kwargs):
        assert str(chunk.id) in system
        return _payload(cited=[chunk.id], reply="I can cite Calculus Guide.")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, session.id, "calculus")
    assistant = [m for m in db.list_messages(db_sess, session.id) if m.role == "assistant"][-1]

    r = await client.get(f"/api/sessions/{session.id}/messages/{assistant.id}/sources")

    assert r.status_code == 200
    body = r.json()
    assert body["message_id"] == assistant.id
    assert body["sources"][0]["title"] == doc.title
    assert body["sources"][0]["chunk_id"] == chunk.id


async def test_chat_response_includes_cited_sources(client, db_sess, monkeypatch):
    session = engine.create_session(db_sess, title="", role="student", goal="learn")
    _doc, chunk = _import_doc(db_sess, session.id)

    async def fake_chat_json(system, messages, **kwargs):
        cited = [int(x) for x in re.findall(r"chunk_id=(\d+)", system)]
        return _payload(cited=cited[:1], reply="I can cite Calculus Guide.")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    r = await client.post(f"/api/sessions/{session.id}/chat", json={"message": "calculus"})

    assert r.status_code == 200
    body = r.json()
    assert "cited_sources" in body
    assert body["cited_sources"]
    assert body["cited_sources"][0]["chunk_id"] == chunk.id
