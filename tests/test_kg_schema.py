from __future__ import annotations

from datetime import datetime

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


def _session(db_sess, sid: str = "kg-session") -> db.Session:
    s = engine.create_session(db_sess, title="", role="student", goal="local test")
    s.id = sid
    db_sess.commit()
    return s


def _concept_pair(db_sess, sid: str):
    a = db.upsert_kg_node(db_sess, sid, "concept", "二次函数", episode_id=1)
    b = db.upsert_kg_node(db_sess, sid, "concept", "极值点偏移", episode_id=1)
    db_sess.flush()
    return a, b


def test_upsert_kg_node_creates_then_updates_timestamp_and_properties(db_sess):
    _session(db_sess)
    node = db.upsert_kg_node(db_sess, "kg-session", "concept", " 极值点偏移 ", properties={"difficulty": 2})
    first_seen = node.first_seen_at
    last_seen = node.last_seen_at

    same = db.upsert_kg_node(db_sess, "kg-session", "concept", "极值点偏移", properties={"domain": "函数"})

    assert same.id == node.id
    assert same.name == "极值点偏移"
    assert same.first_seen_at == first_seen
    assert same.last_seen_at >= last_seen
    assert same.properties() == {"difficulty": 2, "domain": "函数"}


def test_upsert_kg_node_appends_episode_id_once(db_sess):
    _session(db_sess)

    node = db.upsert_kg_node(db_sess, "kg-session", "concept", "符号", episode_id=12)
    db.upsert_kg_node(db_sess, "kg-session", "concept", "符号", episode_id=12)
    db.upsert_kg_node(db_sess, "kg-session", "concept", "符号", episode_id=13)

    assert node.episode_ids() == [12, 13]


def test_find_kg_node_returns_match_or_none(db_sess):
    _session(db_sess)
    node = db.upsert_kg_node(db_sess, "kg-session", "concept", "导数")

    assert db.find_kg_node(db_sess, "kg-session", "concept", "导数").id == node.id
    assert db.find_kg_node(db_sess, "kg-session", "concept", "不存在") is None


def test_list_kg_nodes_filters_by_kind_and_status(db_sess):
    _session(db_sess)
    active = db.upsert_kg_node(db_sess, "kg-session", "concept", "A")
    error = db.upsert_kg_node(db_sess, "kg-session", "error_pattern", "符号错")
    db.invalidate_kg_node(db_sess, "kg-session", active.id)

    assert [n.id for n in db.list_kg_nodes(db_sess, "kg-session", kind="error_pattern")] == [error.id]
    assert [n.id for n in db.list_kg_nodes(db_sess, "kg-session", status="invalidated")] == [active.id]


def test_invalidate_kg_node_marks_invalidated(db_sess):
    _session(db_sess)
    node = db.upsert_kg_node(db_sess, "kg-session", "concept", "A")

    invalidated = db.invalidate_kg_node(db_sess, "kg-session", node.id)

    assert invalidated.status == "invalidated"
    assert invalidated.last_seen_at is not None


def test_upsert_kg_node_reactivates_invalidated_node(db_sess):
    _session(db_sess)
    node = db.upsert_kg_node(db_sess, "kg-session", "concept", "A")
    db.invalidate_kg_node(db_sess, "kg-session", node.id)

    same = db.upsert_kg_node(db_sess, "kg-session", "concept", "A")

    assert same.id == node.id
    assert same.status == "active"


def test_upsert_kg_edge_creates_then_updates_weight(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")

    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", weight=0.2)
    same = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", weight=0.8)

    assert same.id == edge.id
    assert same.weight == 0.8


def test_upsert_kg_edge_appends_episode_id_once(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")

    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", episode_id=2)
    db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", episode_id=2)
    db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", episode_id=3)

    assert edge.episode_ids() == [2, 3]


def test_list_kg_edges_matches_source_or_target_node(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "前置于")

    assert [e.id for e in db.list_kg_edges(db_sess, "kg-session", node_id=src.id)] == [edge.id]
    assert [e.id for e in db.list_kg_edges(db_sess, "kg-session", node_id=tgt.id)] == [edge.id]


def test_invalidate_kg_edge_marks_invalidated_and_timestamp(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中")

    invalidated = db.invalidate_kg_edge(db_sess, "kg-session", edge.id)

    assert invalidated.status == "invalidated"
    assert isinstance(invalidated.invalidated_at, datetime)


def test_supersede_kg_edge_marks_old_and_creates_active_new(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    old = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", weight=0.3)

    new = db.supersede_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", new_weight=0.0, episode_id=9)

    assert old.status == "superseded"
    assert old.invalidated_at is not None
    assert new.id != old.id
    assert new.status == "active"
    assert new.weight == 0.0
    assert new.episode_ids() == [9]


def test_remove_kg_episode_references_cleans_nodes_and_edges(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", episode_id=1)
    db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中", episode_id=2)

    db.remove_kg_episode_references(db_sess, "kg-session", 1)

    assert src.episode_ids() == []
    assert tgt.episode_ids() == []
    assert edge.episode_ids() == [2]


def test_delete_session_cascades_kg_nodes_and_edges(db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中")
    db_sess.commit()

    assert db.delete_session(db_sess, "kg-session") is True
    assert db.list_kg_nodes(db_sess, "kg-session", status="") == []
    assert db.list_kg_edges(db_sess, "kg-session", status="") == []


def test_kg_queries_are_session_isolated(db_sess):
    _session(db_sess, "A")
    _session(db_sess, "B")
    node_a = db.upsert_kg_node(db_sess, "A", "concept", "共享名")
    db.upsert_kg_node(db_sess, "B", "concept", "共享名")

    assert [n.id for n in db.list_kg_nodes(db_sess, "A")] == [node_a.id]
    assert db.find_kg_node(db_sess, "B", "concept", "共享名").id != node_a.id


async def test_memory_api_returns_kg_nodes_and_edges(client, db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中")
    db_sess.commit()

    r = await client.get("/api/sessions/kg-session/memory")

    assert r.status_code == 200
    body = r.json()
    assert {n["id"] for n in body["kg_nodes"]} == {src.id, tgt.id}
    assert body["kg_edges"][0]["id"] == edge.id


async def test_memory_delete_invalidates_kg_node_and_edge(client, db_sess):
    _session(db_sess)
    src, tgt = _concept_pair(db_sess, "kg-session")
    edge = db.upsert_kg_edge(db_sess, "kg-session", src.id, tgt.id, "学习中")
    db_sess.commit()

    assert (await client.delete(f"/api/sessions/kg-session/memory/kg_node/{src.id}")).status_code == 200
    assert (await client.delete(f"/api/sessions/kg-session/memory/kg_edge/{edge.id}")).status_code == 200
    db_sess.expire_all()
    assert db.get_kg_node(db_sess, "kg-session", src.id).status == "invalidated"
    assert db.get_kg_edge(db_sess, "kg-session", edge.id).status == "invalidated"
