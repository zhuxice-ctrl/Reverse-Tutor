"""Persona 模板：DB CRUD + HTTP API。"""
from __future__ import annotations

import httpx
import pytest

import db
from server import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_seed_creates_five_builtin(db_sess):
    ts = db.list_templates(db_sess)
    assert len(ts) >= 5
    assert all(t.builtin for t in ts)
    labels = {t.label for t in ts}
    assert any("高三" in s for s in labels)
    assert any("Python" in s for s in labels)


def test_seed_is_idempotent(db_sess):
    before = len(db.list_templates(db_sess))
    n = db.seed_builtin_templates(db_sess)
    after = len(db.list_templates(db_sess))
    assert n == 0
    assert before == after


def test_create_user_template_and_delete(db_sess):
    t = db.create_template(
        db_sess, label="my", role="r", goal="g",
        deadline="d", personality="p", reqs=["a", "b"],
    )
    assert t.id and t.builtin == 0
    assert t.reqs() == ["a", "b"]
    assert db.delete_template(db_sess, t.id) is True
    assert db.get_template(db_sess, t.id) is None


def test_cannot_delete_builtin(db_sess):
    builtin = next(t for t in db.list_templates(db_sess) if t.builtin)
    assert db.delete_template(db_sess, builtin.id) is False
    assert db.get_template(db_sess, builtin.id) is not None


def test_update_template_fields(db_sess):
    t = db.create_template(db_sess, label="x", role="r1", goal="g1")
    db.update_template(db_sess, t, role="r2", reqs=["x", "y"])
    t2 = db.get_template(db_sess, t.id)
    assert t2.role == "r2" and t2.reqs() == ["x", "y"]


# --- HTTP API ----------------------------------------------------------------

async def test_api_list_returns_builtins(client):
    r = await client.get("/api/templates")
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 5
    assert all(t["builtin"] for t in arr)


async def test_api_create_validates_required(client):
    r = await client.post("/api/templates", json={"label": "x"})
    assert r.status_code == 400


async def test_api_create_then_update_then_delete(client):
    r = await client.post("/api/templates", json={
        "label": "电吉他入门", "role": "成人新手", "goal": "半年内能弹《Wish You Were Here》",
        "personality": "三分钟热度", "reqs": ["每天 20 分钟"],
    })
    assert r.status_code == 200
    t = r.json()
    tid = t["id"]
    assert t["builtin"] is False
    assert t["reqs"] == ["每天 20 分钟"]

    r = await client.put(f"/api/templates/{tid}",
                          json={"deadline": "6 个月", "reqs": ["每天 30 分钟"]})
    assert r.status_code == 200
    assert r.json()["deadline"] == "6 个月"
    assert r.json()["reqs"] == ["每天 30 分钟"]

    r = await client.delete(f"/api/templates/{tid}")
    assert r.status_code == 200

    r = await client.delete(f"/api/templates/{tid}")
    assert r.status_code == 404


async def test_api_cannot_delete_builtin_via_http(client):
    r = await client.get("/api/templates")
    builtin = next(t for t in r.json() if t["builtin"])
    r = await client.delete(f"/api/templates/{builtin['id']}")
    assert r.status_code == 400
