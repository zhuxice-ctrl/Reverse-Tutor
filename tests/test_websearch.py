from __future__ import annotations

import re

from sqlalchemy import select

import db
import engine
from websearch import (
    MockWebSearchProvider,
    NullWebSearchProvider,
    WebHit,
    get_web_search_provider,
)


def _payload(*, cited: list[int], reply: str = "I found a useful source."):
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


def _last_assistant_meta(db_sess, sid: str) -> dict:
    assistants = [m for m in db.list_messages(db_sess, sid) if m.role == "assistant"]
    return assistants[-1].meta()


def test_null_web_search_provider_returns_empty_list():
    assert NullWebSearchProvider().search("calculus") == []


def test_mock_web_search_provider_limits_hits():
    provider = MockWebSearchProvider([
        WebHit("One", "https://one.example", "first", "mock"),
        WebHit("Two", "https://two.example", "second", "mock"),
    ])

    assert provider.search("q", top_k=1) == [WebHit("One", "https://one.example", "first", "mock")]


def test_default_web_search_provider_is_null_without_env(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("WEB_SEARCH_API_KEY", raising=False)

    assert isinstance(get_web_search_provider(), NullWebSearchProvider)


def test_mock_factory_does_not_raise(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "mock")

    assert get_web_search_provider().search("anything") == []


def test_http_factory_without_key_falls_back_to_null(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "http")
    monkeypatch.delenv("WEB_SEARCH_API_KEY", raising=False)

    assert isinstance(get_web_search_provider(), NullWebSearchProvider)


async def test_web_search_enabled_imports_mock_result_as_citable_source(db_sess, monkeypatch):
    session = engine.create_session(
        db_sess,
        title="",
        role="student",
        goal="learn",
        settings={"web_search_enabled": True},
    )
    provider = MockWebSearchProvider([
        WebHit("Example", "https://e.com", "useful snippet about calculus entry points", "mock"),
    ])

    async def fake_chat_json(system, messages, **kwargs):
        cited = [int(x) for x in re.findall(r"chunk_id=(\d+)", system)]
        return _payload(cited=cited[:1], reply="I saw Example mention a useful snippet.")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, session.id, "calculus", web_search=provider)

    web_doc = db_sess.scalar(select(db.Document).where(db.Document.source_type == "web"))
    assert web_doc is not None
    assert web_doc.session_id == session.id
    assert web_doc.title == "Example"
    web_chunk = db.list_doc_chunks(db_sess, web_doc.id)[0]
    assert _last_assistant_meta(db_sess, session.id)["cited_chunk_ids"] == [web_chunk.id]


async def test_web_search_disabled_does_not_call_provider(db_sess, monkeypatch):
    session = engine.create_session(db_sess, title="", role="student", goal="learn")

    class RaisingProvider:
        def search(self, query: str, *, top_k: int = 3):
            raise AssertionError("web search should not be called")

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(cited=[])

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, session.id, "calculus", web_search=RaisingProvider())

    assert db_sess.scalar(select(db.Document).where(db.Document.source_type == "web")) is None
    assert _last_assistant_meta(db_sess, session.id)["cited_chunk_ids"] == []
