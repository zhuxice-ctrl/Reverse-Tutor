from __future__ import annotations

import db
import engine
import kg_extractor as kg
from kg_extractor import KIND_CONCEPT, KIND_ERROR, REL_ERROR_ON, REL_MASTERED


def _session(db_sess, sid: str) -> db.Session:
    s = engine.create_session(db_sess, title="", role="student", goal="local test")
    s.id = sid
    db_sess.commit()
    return s


def _evaluation(*, correctness=0.4, evidence=None, error="", entry="has_entry"):
    return {
        "entry_status": entry,
        "correctness": correctness,
        "depth": 0.5,
        "error_pattern": error,
        "evidence_for_mastery": evidence
        or {"type": "none", "status": "none", "error_type": "", "reason": ""},
    }


def _action(kp="shared-kp", action_type="probe"):
    return {"type": action_type, "student_role": "probing_student", "knowledge_point": kp, "difficulty": 0.6}


def _payload(
    *,
    kp="payload-kp",
    action_type="probe",
    correctness=0.55,
    depth=0.5,
    evidence=None,
    error="",
):
    role = {
        "clue": "clue_student",
        "scaffold_example": "scaffold_student",
        "examiner_verify": "examiner",
        "recap": "review_student",
    }.get(action_type, "probing_student")
    return {
        "evaluation": {
            "correctness": correctness,
            "depth": depth,
            "entry_status": "has_entry",
            "error_pattern": error,
            "evidence_for_mastery": evidence
            or {"type": "none", "status": "none", "error_type": "", "reason": "mock"},
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": action_type,
            "student_role": role,
            "knowledge_point": kp,
            "difficulty": 0.6,
            "note": "mock",
        },
        "reply": f"reply about {kp}",
        "anchor_updates": [],
    }


def _concept_pair(db_sess, sid: str, left="left-kp", right="right-kp"):
    source = db.upsert_kg_node(db_sess, sid, KIND_CONCEPT, left)
    target = db.upsert_kg_node(db_sess, sid, KIND_CONCEPT, right)
    return source, target


async def _fake_chat_json(system, messages, **kwargs):
    return _payload()


def test_same_concept_name_is_session_isolated(db_sess):
    _session(db_sess, "iso-a")
    _session(db_sess, "iso-b")

    node_a = db.upsert_kg_node(db_sess, "iso-a", KIND_CONCEPT, "shared concept")
    node_b = db.upsert_kg_node(db_sess, "iso-b", KIND_CONCEPT, "shared concept")

    assert node_a.id != node_b.id
    assert {n.id for n in db.list_kg_nodes(db_sess, "iso-a")} == {node_a.id}
    assert {n.id for n in db.list_kg_nodes(db_sess, "iso-b")} == {node_b.id}


def test_edges_do_not_leak_between_sessions(db_sess):
    _session(db_sess, "edge-a")
    _session(db_sess, "edge-b")
    source, target = _concept_pair(db_sess, "edge-a")

    edge = db.upsert_kg_edge(db_sess, "edge-a", source.id, target.id, kg.REL_PREREQ)

    assert [e.id for e in db.list_kg_edges(db_sess, "edge-a")] == [edge.id]
    assert db.list_kg_edges(db_sess, "edge-b") == []


def test_delete_session_removes_only_that_sessions_graph(db_sess):
    _session(db_sess, "delete-a")
    _session(db_sess, "delete-b")
    a_source, a_target = _concept_pair(db_sess, "delete-a", "a-source", "a-target")
    b_source, b_target = _concept_pair(db_sess, "delete-b", "b-source", "b-target")
    db.upsert_kg_edge(db_sess, "delete-a", a_source.id, a_target.id, kg.REL_PREREQ)
    edge_b = db.upsert_kg_edge(db_sess, "delete-b", b_source.id, b_target.id, kg.REL_PREREQ)
    db_sess.commit()

    assert db.delete_session(db_sess, "delete-a") is True

    assert db.list_kg_nodes(db_sess, "delete-a", status="") == []
    assert db.list_kg_edges(db_sess, "delete-a", status="") == []
    assert {n.id for n in db.list_kg_nodes(db_sess, "delete-b")} == {b_source.id, b_target.id}
    assert [e.id for e in db.list_kg_edges(db_sess, "delete-b")] == [edge_b.id]


async def test_run_turn_graph_extraction_is_session_isolated(db_sess, monkeypatch):
    _session(db_sess, "turn-a")
    _session(db_sess, "turn-b")

    async def fake_chat_json(system, messages, **kwargs):
        user_input = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        kp = "turn-a-kp" if "alpha" in user_input else "turn-b-kp"
        return _payload(kp=kp, correctness=0.55)

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, "turn-a", "alpha answer")
    await engine.run_turn(db_sess, "turn-b", "beta answer")

    assert {n.name for n in db.list_kg_nodes(db_sess, "turn-a", kind=KIND_CONCEPT)} == {"turn-a-kp"}
    assert {n.name for n in db.list_kg_nodes(db_sess, "turn-b", kind=KIND_CONCEPT)} == {"turn-b-kp"}


def test_repeated_node_upsert_is_single_row_with_stable_first_seen(db_sess):
    _session(db_sess, "node-repeat")
    first = db.upsert_kg_node(db_sess, "node-repeat", KIND_CONCEPT, "same-kp", episode_id=1)
    first_seen = first.first_seen_at
    first_last_seen = first.last_seen_at
    second = db.upsert_kg_node(db_sess, "node-repeat", KIND_CONCEPT, "same-kp", episode_id=1)
    second_last_seen = second.last_seen_at
    third = db.upsert_kg_node(db_sess, "node-repeat", KIND_CONCEPT, "same-kp", episode_id=2)

    nodes = db.list_kg_nodes(db_sess, "node-repeat", kind=KIND_CONCEPT)
    assert [n.id for n in nodes] == [first.id]
    assert third.id == first.id
    assert third.first_seen_at == first_seen
    assert third.last_seen_at >= second_last_seen >= first_last_seen
    assert third.episode_ids() == [1, 2]


def test_repeated_edge_upsert_is_single_active_edge_with_latest_weight(db_sess):
    _session(db_sess, "edge-repeat")
    source, target = _concept_pair(db_sess, "edge-repeat")

    first = db.upsert_kg_edge(db_sess, "edge-repeat", source.id, target.id, kg.REL_LEARNING, weight=0.2)
    db.upsert_kg_edge(db_sess, "edge-repeat", source.id, target.id, kg.REL_LEARNING, weight=0.5)
    third = db.upsert_kg_edge(db_sess, "edge-repeat", source.id, target.id, kg.REL_LEARNING, weight=0.9)

    edges = db.list_kg_edges(db_sess, "edge-repeat", relation=kg.REL_LEARNING)
    assert [e.id for e in edges] == [first.id]
    assert third.id == first.id
    assert edges[0].weight == 0.9


async def test_extract_from_turn_same_payload_and_episode_is_idempotent(db_sess, monkeypatch):
    _session(db_sess, "extract-repeat")
    monkeypatch.setattr(engine.llm, "chat_json", _fake_chat_json)
    evaluation = _evaluation(correctness=0.45)
    action = _action(kp="extract-kp")

    await kg.extract_from_turn(db_sess, "extract-repeat", evaluation=evaluation, action=action, episode_id=7)
    node_count = len(db.list_kg_nodes(db_sess, "extract-repeat"))
    edge_count = len(db.list_kg_edges(db_sess, "extract-repeat"))
    await kg.extract_from_turn(db_sess, "extract-repeat", evaluation=evaluation, action=action, episode_id=7)

    nodes = db.list_kg_nodes(db_sess, "extract-repeat")
    edges = db.list_kg_edges(db_sess, "extract-repeat")
    assert len(nodes) == node_count
    assert len(edges) == edge_count
    assert all(n.episode_ids().count(7) == 1 for n in nodes)
    assert all(e.episode_ids().count(7) == 1 for e in edges)


async def test_run_turn_same_input_does_not_duplicate_concept(db_sess, monkeypatch):
    _session(db_sess, "turn-repeat")
    monkeypatch.setattr(engine.llm, "chat_json", _fake_chat_json)

    await engine.run_turn(db_sess, "turn-repeat", "repeat this answer")
    await engine.run_turn(db_sess, "turn-repeat", "repeat this answer")

    concepts = [n for n in db.list_kg_nodes(db_sess, "turn-repeat", kind=KIND_CONCEPT) if n.name == "payload-kp"]
    assert len(concepts) == 1


def test_invalidate_edge_hides_from_active_listing(db_sess):
    _session(db_sess, "edge-invalidate")
    source, target = _concept_pair(db_sess, "edge-invalidate")
    edge = db.upsert_kg_edge(db_sess, "edge-invalidate", source.id, target.id, kg.REL_PREREQ)

    invalidated = db.invalidate_kg_edge(db_sess, "edge-invalidate", edge.id)

    assert invalidated.status == "invalidated"
    assert invalidated.invalidated_at is not None
    assert db.list_kg_edges(db_sess, "edge-invalidate", status="active") == []
    assert [e.id for e in db.list_kg_edges(db_sess, "edge-invalidate", status="invalidated")] == [edge.id]


def test_supersede_edge_marks_old_and_creates_timestamp_consistent_replacement(db_sess):
    _session(db_sess, "edge-supersede")
    source, target = _concept_pair(db_sess, "edge-supersede")
    old = db.upsert_kg_edge(db_sess, "edge-supersede", source.id, target.id, kg.REL_LEARNING, weight=0.3)

    new = db.supersede_kg_edge(
        db_sess,
        "edge-supersede",
        source.id,
        target.id,
        kg.REL_LEARNING,
        new_weight=0.75,
        episode_id=9,
    )

    assert old.status == "superseded"
    assert old.invalidated_at is not None
    assert new.id != old.id
    assert new.status == "active"
    assert new.valid_from >= old.invalidated_at
    assert [e.id for e in db.list_kg_edges(db_sess, "edge-supersede", relation=kg.REL_LEARNING)] == [new.id]


def test_supersede_active_listing_keeps_new_weight_only(db_sess):
    _session(db_sess, "edge-new-weight")
    source, target = _concept_pair(db_sess, "edge-new-weight")
    db.upsert_kg_edge(db_sess, "edge-new-weight", source.id, target.id, kg.REL_LEARNING, weight=0.25)

    new = db.supersede_kg_edge(
        db_sess,
        "edge-new-weight",
        source.id,
        target.id,
        kg.REL_LEARNING,
        new_weight=0.88,
    )

    active = [
        e
        for e in db.list_kg_edges(db_sess, "edge-new-weight", relation=kg.REL_LEARNING)
        if e.source_id == source.id and e.target_id == target.id
    ]
    assert [e.id for e in active] == [new.id]
    assert active[0].weight == 0.88


def test_invalidate_node_then_reupsert_reactivates_same_row(db_sess):
    _session(db_sess, "node-invalidate")
    node = db.upsert_kg_node(db_sess, "node-invalidate", KIND_CONCEPT, "reactivated-kp")

    invalidated = db.invalidate_kg_node(db_sess, "node-invalidate", node.id)
    assert invalidated.status == "invalidated"
    assert db.list_kg_nodes(db_sess, "node-invalidate") == []
    assert [n.id for n in db.list_kg_nodes(db_sess, "node-invalidate", status="invalidated")] == [node.id]

    same = db.upsert_kg_node(db_sess, "node-invalidate", KIND_CONCEPT, "reactivated-kp")
    assert same.id == node.id
    assert same.status == "active"
    assert [n.id for n in db.list_kg_nodes(db_sess, "node-invalidate")] == [node.id]


def test_remove_episode_references_cleans_nodes_and_edges_only_for_target_episode(db_sess):
    _session(db_sess, "episode-cleanup")
    source = db.upsert_kg_node(db_sess, "episode-cleanup", KIND_CONCEPT, "ep-source", episode_id=1)
    target = db.upsert_kg_node(db_sess, "episode-cleanup", KIND_CONCEPT, "ep-target", episode_id=2)
    db.upsert_kg_node(db_sess, "episode-cleanup", KIND_CONCEPT, "ep-source", episode_id=2)
    edge = db.upsert_kg_edge(
        db_sess,
        "episode-cleanup",
        source.id,
        target.id,
        kg.REL_PREREQ,
        episode_id=1,
    )
    db.upsert_kg_edge(db_sess, "episode-cleanup", source.id, target.id, kg.REL_PREREQ, episode_id=2)

    db.remove_kg_episode_references(db_sess, "episode-cleanup", 1)

    assert source.episode_ids() == [2]
    assert target.episode_ids() == [2]
    assert edge.episode_ids() == [2]


async def test_mastery_turn_writes_mastery_and_mastered_edge(db_sess, monkeypatch):
    _session(db_sess, "mastery-consistency")

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(
            kp="mastered-kp",
            action_type="probe",
            correctness=0.82,
            depth=0.7,
            evidence={"type": "explanation", "status": "passed", "error_type": "", "reason": "verified"},
        )

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, "mastery-consistency", "clear explanation")

    masteries = [m for m in db.list_mastery(db_sess, "mastery-consistency") if m.knowledge_point == "mastered-kp"]
    person = db.list_kg_nodes(db_sess, "mastery-consistency", kind="person")[0]
    concept = db.find_kg_node(db_sess, "mastery-consistency", KIND_CONCEPT, "mastered-kp")
    mastered_edges = db.list_kg_edges(db_sess, "mastery-consistency", node_id=concept.id, relation=REL_MASTERED)
    assert len(masteries) == 1
    assert any(e.source_id == person.id and e.target_id == concept.id for e in mastered_edges)


async def test_error_turn_writes_error_log_and_error_edge(db_sess, monkeypatch):
    _session(db_sess, "error-consistency")

    async def fake_chat_json(system, messages, **kwargs):
        return _payload(
            kp="error-kp",
            action_type="examiner_verify",
            correctness=0.3,
            depth=0.4,
            evidence={"type": "retrieval", "status": "failed", "error_type": "condition", "reason": "missed guard"},
            error="missed guard",
        )

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, "error-consistency", "verification failed")

    rows = db.list_error_logs(db_sess, "error-consistency")
    person = db.list_kg_nodes(db_sess, "error-consistency", kind="person")[0]
    err_node = db.find_kg_node(db_sess, "error-consistency", KIND_ERROR, "missed guard")
    error_edges = db.list_kg_edges(db_sess, "error-consistency", node_id=err_node.id, relation=REL_ERROR_ON)
    assert len(rows) == 1
    assert rows[0].kp == "error-kp"
    assert rows[0].error_pattern == "missed guard"
    assert any(e.source_id == person.id and e.target_id == err_node.id for e in error_edges)


def test_delete_session_after_node_invalidation_leaves_no_orphan_edges(db_sess):
    _session(db_sess, "orphan-delete")
    source, target = _concept_pair(db_sess, "orphan-delete")
    db.upsert_kg_edge(db_sess, "orphan-delete", source.id, target.id, kg.REL_PREREQ)
    db.invalidate_kg_node(db_sess, "orphan-delete", source.id)
    db_sess.commit()

    assert db.delete_session(db_sess, "orphan-delete") is True

    assert db.list_kg_nodes(db_sess, "orphan-delete", status="") == []
    assert db.list_kg_edges(db_sess, "orphan-delete", status="") == []
    orphan_edges = [
        e
        for e in db_sess.query(db.KGEdge).all()
        if e.status == "active"
        and (db_sess.get(db.KGNode, e.source_id) is None or db_sess.get(db.KGNode, e.target_id) is None)
    ]
    assert orphan_edges == []
