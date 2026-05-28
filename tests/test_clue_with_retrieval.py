from __future__ import annotations

from retrieval import FTSRetriever, Hit

import db
import engine


class StaticRetriever:
    def __init__(self, hits: list[Hit]):
        self.hits = hits
        self.queries: list[tuple[str, str | None, int]] = []

    def search(self, query: str, *, session_id: str | None, top_k: int = 3) -> list[Hit]:
        self.queries.append((query, session_id, top_k))
        return self.hits[:top_k]


def _payload(*, action_type="clue", role="clue_student", cited=None, reply=None):
    return {
        "evaluation": {
            "correctness": 0.0,
            "depth": 0.0,
            "entry_status": "no_entry",
            "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": "极值点偏移",
            "difficulty": 0.5,
            "note": "mock",
        },
        "reply": reply or "老师，我听说《极值点偏移导引》里有个第一步线索，你能讲讲吗？",
        "cited_chunk_ids": cited or [],
        "anchor_updates": [],
    }


def _last_assistant_meta(db_sess, sid: str) -> dict:
    assistants = [m for m in db.list_messages(db_sess, sid) if m.role == "assistant"]
    return assistants[-1].meta()


def _import_doc(db_sess, session_id: str | None = None):
    doc = db.add_document(
        db_sess,
        session_id=session_id,
        title="极值点偏移导引",
        source_type="md",
        source_uri="local.md",
        content="极值点偏移导引：先看普通方法为什么卡住，再观察左右两侧的对称差值。" * 6,
    )
    db_sess.commit()
    return doc, db.list_doc_chunks(db_sess, doc.id)[0]


def test_should_inject_clue_retrieval_heuristic(db_sess):
    from engine import _should_inject_clue_retrieval

    assert _should_inject_clue_retrieval("极值点偏移", []) is True
    assert _should_inject_clue_retrieval("我觉得这个方法的核心思路是先观察函数的对称性，再" * 3, []) is False

    class M:
        knowledge_point = "极值点偏移"
        level = 0.6
        mastery_score = 60.0

    assert _should_inject_clue_retrieval("极值点偏移", [M()]) is False


async def test_clue_student_reply_cites_imported_doc(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    _, chunk = _import_doc(db_sess, session_id=s.id)
    prompts = []

    async def fake_chat_json(system, messages, **kwargs):
        prompts.append(system)
        return _payload(cited=[chunk.id])

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "极值点偏移", retriever=FTSRetriever(db_sess))

    assert "极值点偏移导引" in result.reply
    assert "# 可引用线索" in prompts[0]
    assert _last_assistant_meta(db_sess, s.id)["cited_chunk_ids"] == [chunk.id]


async def test_clue_student_no_local_hit_falls_back_gracefully(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(cited=[], reply="老师，我听说先找第一步线索，你能讲讲吗？")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "极值点偏移是什么", retriever=StaticRetriever([]))
    meta = _last_assistant_meta(db_sess, s.id)

    assert "未命中本地资料" in result.process_summary
    assert meta["clue_no_local_doc"] is True
    assert meta["cited_chunk_ids"] == []


async def test_clue_no_citation_warns_when_hits_exist_but_llm_skips(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    _, chunk = _import_doc(db_sess, session_id=s.id)

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(cited=[])

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "极值点偏移", retriever=FTSRetriever(db_sess))
    meta = _last_assistant_meta(db_sess, s.id)

    assert chunk.id
    assert meta["clue_no_citation"] is True
    assert meta["cited_chunk_ids"] == []


async def test_probing_student_does_not_inject_clues(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    prompts = []
    retriever = StaticRetriever([Hit(99, 1, "fake", "fake", 1.0)])

    async def fake_chat_json(system, messages, **kwargs):
        prompts.append(system)
        return _payload(action_type="probe", role="probing_student", cited=[99], reply="那你为什么这么想？")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "因为我觉得这里要先比较左右两侧变化，再看这个方法为什么能处理极值点偏移。" * 3, retriever=retriever)

    assert "# 可引用线索" not in prompts[0]
    assert retriever.queries == []
    assert _last_assistant_meta(db_sess, s.id)["cited_chunk_ids"] == []


async def test_examiner_does_not_inject_clues(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    prompts = []
    retriever = StaticRetriever([Hit(99, 1, "fake", "fake", 1.0)])

    async def fake_chat_json(system, messages, **kwargs):
        prompts.append(system)
        return _payload(action_type="examiner_verify", role="examiner", cited=[99], reply="那我出一道题验证一下？")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来验证", retriever=retriever)

    assert "# 可引用线索" not in prompts[0]
    assert retriever.queries == []
    assert _last_assistant_meta(db_sess, s.id)["cited_chunk_ids"] == []


async def test_cited_chunk_ids_must_match_injected(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    hit = Hit(10, 1, "极值点偏移导引", "先看普通方法为什么卡住。", 1.0)

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(cited=[10, 9999])

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "极值点偏移是什么", retriever=StaticRetriever([hit]))
    meta = _last_assistant_meta(db_sess, s.id)

    assert meta["cited_chunk_ids"] == [10]
    assert meta["clue_fake_citation"] == [9999]


async def test_clue_predicted_but_not_used_is_marked(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三学生", goal="方法学习")
    hit = Hit(12, 1, "极值点偏移导引", "先看普通方法为什么卡住。", 1.0)

    async def fake_chat_json(system, messages, **kwargs):
        payload = _payload(action_type="probe", role="probing_student", cited=[12], reply="那你先说说你观察到了什么？")
        payload["evaluation"]["entry_status"] = "has_entry"
        return payload

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "极值点偏移", retriever=StaticRetriever([hit]))
    meta = _last_assistant_meta(db_sess, s.id)

    assert meta["cited_chunk_ids"] == []
    assert meta["clue_predicted_but_not_used"] == [12]
