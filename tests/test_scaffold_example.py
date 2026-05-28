from __future__ import annotations

import httpx
import pytest

import engine
import llm
from retrieval import Hit
from server import app


class StaticRetriever:
    def __init__(self, hits: list[Hit]):
        self.hits = hits
        self.queries: list[str] = []

    def search(self, query: str, *, session_id: str | None, top_k: int = 3) -> list[Hit]:
        self.queries.append(query)
        return self.hits[:top_k]


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_session(client) -> str:
    r = await client.post("/api/sessions", json={
        "role": "高三学生",
        "goal": "数学 130",
        "auto_opening": False,
    })
    assert r.status_code == 200
    return r.json()["id"]


def _make_sequence_mock(payloads: list[dict]):
    it = iter(payloads)

    async def mock_chat_json(system, messages, **kwargs):
        return next(it)

    return mock_chat_json


def _payload(
    *,
    action_type: str = "scaffold_example",
    role: str = "scaffold_student",
    entry: str = "no_entry",
    correctness: float = 0.0,
    depth: float = 0.0,
    kp: str = "极值点偏移",
    reply: str = "我拿 f(x)=x^3-3x 看一下：先求导 → 再找零点。为什么第一步要求导？",
    cited: list[int] | None = None,
) -> dict:
    return {
        "evaluation": {
            "correctness": correctness,
            "depth": depth,
            "entry_status": entry,
            "error_pattern": "",
            "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": kp,
            "difficulty": 0.5,
            "note": "scaffold test",
        },
        "reply": reply,
        "cited_chunk_ids": cited or [],
        "anchor_updates": [],
    }


def _last_assistant_meta(db_sess, sid: str) -> dict:
    assistants = [m for m in engine.db.list_messages(db_sess, sid) if m.role == "assistant"]
    return assistants[-1].meta()


def test_scaffold_student_reply_starts_with_teacher():
    reply = engine._discipline_reply_for_role(
        "我拿 f(x)=x^3-3x 看一下。",
        {"student_role": "scaffold_student", "knowledge_point": "极值点偏移"},
    )

    assert reply.startswith("老师")


async def test_scaffold_example_process_summary_mentions_example(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="数学 130")
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(),
    ]))

    result = await engine.run_turn(db_sess, s.id, "完全不会极值点偏移")

    assert result.action["type"] == "scaffold_example"
    assert "例子" in result.process_summary or "脚手架" in result.process_summary


async def test_e2e_scaffold_example_then_probe(client, monkeypatch):
    sid = await _create_session(client)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="老师，我拿 f(x)=x^3-3x 看一下：求导 → 令导数为零。为什么第一步要求导？"),
        _payload(
            action_type="probe",
            role="probing_student",
            entry="has_entry",
            correctness=0.5,
            depth=0.4,
            reply="那你说说为什么导数为零能作为候选点？",
        ),
    ]))

    first = await client.post(f"/api/sessions/{sid}/chat", json={"message": "我完全不会极值点偏移"})
    second = await client.post(f"/api/sessions/{sid}/chat", json={"message": "第一步是先看导数为零的位置"})

    assert first.json()["action"]["type"] == "scaffold_example"
    assert first.json()["action"]["student_role"] == "scaffold_student"
    assert first.json()["reply"].startswith("老师")
    assert second.json()["action"]["type"] == "probe"


async def test_system_prompt_contains_example_generation_strategy(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="数学 130")
    prompts = []

    async def fake_chat_json(system, messages, **kwargs):
        prompts.append(system)
        return _payload()

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "完全不会极值点偏移")

    assert "例子生成策略" in prompts[0]
    assert "scaffold_example" in prompts[0]


async def test_scaffold_example_keeps_real_cited_chunk_ids(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="数学 130")
    hit = Hit(21, 1, "极值点偏移例题", "例题：f(x)=x^3-3x，先求导。", 1.0)
    monkeypatch.setattr(engine.llm, "chat_json", _make_sequence_mock([
        _payload(reply="老师，我拿资料里的 f(x)=x^3-3x 例子来看。为什么第一步求导？", cited=[21]),
    ]))

    await engine.run_turn(db_sess, s.id, "极值点偏移", retriever=StaticRetriever([hit]))
    meta = _last_assistant_meta(db_sess, s.id)

    assert meta["cited_chunk_ids"] == [21]


def test_mock_scaffold_example_contains_specific_numbers():
    replies = {
        llm._pack("scaffold_example", "极值点偏移", "neutral", correctness=0, depth=0, reqs=[])["reply"]
        for _ in range(10)
    }

    assert any(any(token in r for token in ("x", "0", "1", "2", "3", "±")) for r in replies)
