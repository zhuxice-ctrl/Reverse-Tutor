from __future__ import annotations

import pytest

import db
import engine
import llm
import kg_extractor as kg


def _session(db_sess, sid: str = "kg-extract") -> db.Session:
    s = engine.create_session(db_sess, title="", role="student", goal="local test")
    s.id = sid
    db_sess.commit()
    return s


def _evaluation(*, entry="has_entry", correctness=0.4, evidence=None, error=""):
    return {
        "entry_status": entry,
        "correctness": correctness,
        "depth": 0.4,
        "error_pattern": error,
        "evidence_for_mastery": evidence or {"type": "none", "status": "none"},
    }


def _action(kp="极值点偏移", action_type="probe"):
    return {"type": action_type, "knowledge_point": kp}


def _user_and_concept(db_sess, sid: str, kp_name: str = "极值点偏移"):
    user = db.find_kg_node(db_sess, sid, "person", "用户")
    concept = db.find_kg_node(db_sess, sid, "concept", kp_name)
    assert user is not None and concept is not None
    return user, concept


def test_rule_extract_has_entry_probe_creates_concept_and_learning_edge(db_sess):
    _session(db_sess)

    ops = kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(), action=_action(), episode_id=1)

    user, concept = _user_and_concept(db_sess, "kg-extract")
    edges = db.list_kg_edges(db_sess, "kg-extract", node_id=concept.id, relation=kg.REL_LEARNING)
    assert {"op": "upsert_node", "kind": kg.KIND_CONCEPT, "name": "极值点偏移"} in ops
    assert edges and edges[0].source_id == user.id and edges[0].weight == 0.4


def test_rule_extract_no_entry_creates_low_weight_learning_edge(db_sess):
    _session(db_sess)

    kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(entry="no_entry"), action=_action(), episode_id=2)

    _, concept = _user_and_concept(db_sess, "kg-extract")
    edge = db.list_kg_edges(db_sess, "kg-extract", node_id=concept.id, relation=kg.REL_LEARNING)[0]
    assert edge.weight == 0.1


def test_rule_extract_passed_high_correctness_supersedes_learning_and_adds_mastered(db_sess):
    _session(db_sess)
    kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(correctness=0.3), action=_action(), episode_id=1)

    kg._rule_extract(
        db_sess,
        "kg-extract",
        evaluation=_evaluation(correctness=0.8, evidence={"type": "correction", "status": "passed"}),
        action=_action(),
        episode_id=2,
    )

    _, concept = _user_and_concept(db_sess, "kg-extract")
    learning = db.list_kg_edges(db_sess, "kg-extract", node_id=concept.id, relation=kg.REL_LEARNING, status="")
    mastered = db.list_kg_edges(db_sess, "kg-extract", node_id=concept.id, relation=kg.REL_MASTERED)
    assert any(e.status == "superseded" for e in learning)
    assert mastered and mastered[0].weight == 0.8


def test_rule_extract_error_pattern_creates_error_node_and_edge(db_sess):
    _session(db_sess)

    ops = kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(error="符号错"), action=_action(), episode_id=3)

    err = db.find_kg_node(db_sess, "kg-extract", kg.KIND_ERROR, "符号错")
    assert err is not None
    assert db.list_kg_edges(db_sess, "kg-extract", node_id=err.id, relation=kg.REL_ERROR_ON)
    assert {"op": "error", "pattern": "符号错", "kp": "极值点偏移"} in ops


def test_rule_extract_passed_correction_invalidates_error_edge(db_sess):
    _session(db_sess)
    kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(error="符号错"), action=_action(), episode_id=1)

    kg._rule_extract(
        db_sess,
        "kg-extract",
        evaluation=_evaluation(correctness=0.8, evidence={"type": "correction", "status": "passed"}, error="符号错"),
        action=_action(),
        episode_id=2,
    )

    err = db.find_kg_node(db_sess, "kg-extract", kg.KIND_ERROR, "符号错")
    assert db.list_kg_edges(db_sess, "kg-extract", node_id=err.id, relation=kg.REL_ERROR_ON) == []
    assert db.list_kg_edges(db_sess, "kg-extract", node_id=err.id, relation=kg.REL_ERROR_ON, status="invalidated")


def test_rule_extract_recall_decay_adds_misunderstood_edge(db_sess):
    _session(db_sess)

    kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(entry="recall_decay"), action=_action(), episode_id=4)

    _, concept = _user_and_concept(db_sess, "kg-extract")
    edge = db.list_kg_edges(db_sess, "kg-extract", node_id=concept.id, relation=kg.REL_MISUNDERSTOOD)[0]
    assert edge.properties()["reason"] == "recall_decay"


def test_rule_extract_empty_knowledge_point_returns_no_ops(db_sess):
    _session(db_sess)

    assert kg._rule_extract(db_sess, "kg-extract", evaluation=_evaluation(), action={"type": "probe"}) == []


async def test_llm_extract_falls_back_to_rule_extract_on_llm_error(db_sess, monkeypatch):
    _session(db_sess)
    monkeypatch.setattr(llm, "chat_json", _raising_chat_json)

    ops = await kg._llm_extract(db_sess, "kg-extract", evaluation=_evaluation(), action=_action(), episode_id=5)

    assert {"op": "learning", "kp": "极值点偏移"} in ops
    assert db.find_kg_node(db_sess, "kg-extract", kg.KIND_CONCEPT, "极值点偏移") is not None


async def _raising_chat_json(*args, **kwargs):
    raise RuntimeError("boom")


async def test_llm_extract_writes_returned_nodes_and_edges(db_sess, monkeypatch):
    _session(db_sess)

    async def fake_chat_json(*args, **kwargs):
        return {
            "nodes": [
                {"kind": "concept", "name": "导数", "properties": {"domain": "math"}},
                {"kind": "method", "name": "数形结合", "properties": {}},
            ],
            "edges": [
                {
                    "source_kind": "method",
                    "source_name": "数形结合",
                    "target_kind": "concept",
                    "target_name": "导数",
                    "relation": kg.REL_USED_FOR,
                    "weight": 0.7,
                    "properties": {"reason": "visual"},
                }
            ],
            "invalidate_edges": [],
        }

    monkeypatch.setattr(llm, "chat_json", fake_chat_json)
    ops = await kg._llm_extract(db_sess, "kg-extract", evaluation=_evaluation(), action=_action(), episode_id=6)

    method = db.find_kg_node(db_sess, "kg-extract", kg.KIND_METHOD, "数形结合")
    concept = db.find_kg_node(db_sess, "kg-extract", kg.KIND_CONCEPT, "导数")
    edge = db.list_kg_edges(db_sess, "kg-extract", node_id=method.id, relation=kg.REL_USED_FOR)[0]
    assert concept.properties()["domain"] == "math"
    assert edge.target_id == concept.id and edge.weight == 0.7
    assert {"op": "upsert_edge", "src": "数形结合", "tgt": "导数", "rel": kg.REL_USED_FOR} in ops


async def test_llm_extract_invalidates_returned_edges(db_sess, monkeypatch):
    _session(db_sess)
    a = db.upsert_kg_node(db_sess, "kg-extract", "concept", "A")
    b = db.upsert_kg_node(db_sess, "kg-extract", "concept", "B")
    edge = db.upsert_kg_edge(db_sess, "kg-extract", a.id, b.id, kg.REL_PREREQ)

    async def fake_chat_json(*args, **kwargs):
        return {"nodes": [], "edges": [], "invalidate_edges": [{"source_name": "A", "target_name": "B", "relation": kg.REL_PREREQ}]}

    monkeypatch.setattr(llm, "chat_json", fake_chat_json)
    await kg._llm_extract(db_sess, "kg-extract", evaluation=_evaluation(), action=_action(), episode_id=7)

    assert db.get_kg_edge(db_sess, "kg-extract", edge.id).status == "invalidated"


async def test_run_turn_extracts_kg_nodes(db_sess):
    s = _session(db_sess)

    await engine.run_turn(db_sess, s.id, "对称轴是 x=-b/(2a)")

    assert db.list_kg_nodes(db_sess, s.id)


async def test_run_turn_multiple_turns_supersede_learning_with_mastered(db_sess, monkeypatch):
    s = _session(db_sess)
    calls = iter([
        llm._pack("ask", "判别式", "neutral", correctness=0.2, depth=0.2, reqs=[]),
        llm._pack("probe", "判别式", "neutral", correctness=0.8, depth=0.7, reqs=[]),
    ])

    async def fake_chat_json(*args, **kwargs):
        return next(calls)

    monkeypatch.setattr(llm, "chat_json", fake_chat_json)
    await engine.run_turn(db_sess, s.id, "还不太会")
    await engine.run_turn(db_sess, s.id, "判别式大于零有两个根")

    concept = db.find_kg_node(db_sess, s.id, kg.KIND_CONCEPT, "判别式")
    assert db.list_kg_edges(db_sess, s.id, node_id=concept.id, relation=kg.REL_MASTERED)
    assert db.list_kg_edges(db_sess, s.id, node_id=concept.id, relation=kg.REL_LEARNING, status="superseded")


async def test_extractor_exception_does_not_block_run_turn(db_sess, monkeypatch):
    s = _session(db_sess)

    async def raise_extract(*args, **kwargs):
        raise RuntimeError("kg down")

    monkeypatch.setattr(engine, "_kg_extract", raise_extract)
    result = await engine.run_turn(db_sess, s.id, "继续")

    assert result.reply
