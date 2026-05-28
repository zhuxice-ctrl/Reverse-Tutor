from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import db
import engine
from server import app


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _examiner_failure(pattern: str, kp: str = "二次函数判别式") -> dict:
    return {
        "evaluation": {
            "correctness": 0.3,
            "depth": 0.4,
            "entry_status": "has_entry",
            "error_pattern": pattern,
            "evidence_for_mastery": {
                "type": "retrieval",
                "status": "failed",
                "error_type": "条件错",
                "reason": "考官验证失败",
            },
            "user_emotion": "neutral",
            "new_requirements": [],
        },
        "action": {
            "type": "examiner_verify",
            "student_role": "examiner",
            "knowledge_point": kp,
            "difficulty": 0.6,
            "note": "verify failed",
        },
        "reply": "老师，我这题还是没过。",
        "anchor_updates": [],
    }


async def test_same_error_pattern_increments_recurrence_and_updates_last_seen(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    async def fake_chat_json(system, messages, **kwargs):
        return _examiner_failure("条件混淆")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来验证")
    first = db.list_error_logs(db_sess, s.id)[0]
    first_seen = first.last_seen_at
    await engine.run_turn(db_sess, s.id, "我再试一次验证")
    row = db.list_error_logs(db_sess, s.id)[0]

    assert row.recurrence_count == 2
    assert row.last_seen_at >= first_seen
    assert len(row.linked_ids()) == 2


async def test_same_kp_different_error_patterns_do_not_merge(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    patterns = iter(["条件混淆", "步骤跳跃"])

    async def fake_chat_json(system, messages, **kwargs):
        return _examiner_failure(next(patterns))

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来验证")
    await engine.run_turn(db_sess, s.id, "再验证一次")

    rows = db.list_error_logs(db_sess, s.id)
    assert sorted(r.error_pattern for r in rows) == ["条件混淆", "步骤跳跃"]
    assert all(r.recurrence_count == 1 for r in rows)


async def test_empty_error_pattern_does_not_write_dirty_row(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    async def fake_chat_json(system, messages, **kwargs):
        return _examiner_failure("")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来验证")

    assert db.list_error_logs(db_sess, s.id) == []


async def test_delayed_retrieval_pass_resolves_existing_error_pattern(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    row = db.upsert_error_log(db_sess, s.id, "二次函数判别式", "条件混淆", evidence_episode_id=None)
    db_sess.commit()

    async def fake_chat_json(system, messages, **kwargs):
        payload = _examiner_failure("条件混淆")
        payload["evaluation"]["correctness"] = 0.85
        payload["evaluation"]["evidence_for_mastery"]["type"] = "delayed_retrieval"
        payload["evaluation"]["evidence_for_mastery"]["status"] = "passed"
        return payload

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来延迟复习验证")
    refreshed = db.get_error_log(db_sess, s.id, row.id)

    assert refreshed.status == "resolved"


async def test_error_log_resolve_api_keeps_record(client):
    r = await client.post("/api/sessions", json={
        "role": "高三生",
        "goal": "数学130",
        "auto_opening": False,
    })
    sid = r.json()["id"]
    with db.SessionLocal() as d:
        row = db.upsert_error_log(d, sid, "判别式", "条件混淆", evidence_episode_id=None)
        d.commit()
        eid = row.id

    r = await client.post(f"/api/sessions/{sid}/errors/{eid}/resolve")

    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    detail = (await client.get(f"/api/sessions/{sid}/errors/{eid}")).json()
    assert detail["id"] == eid
    assert detail["status"] == "resolved"


async def test_error_log_api_orders_by_recurrence_and_resolved_last(client):
    r = await client.post("/api/sessions", json={
        "role": "高三生",
        "goal": "数学130",
        "auto_opening": False,
    })
    sid = r.json()["id"]
    with db.SessionLocal() as d:
        db.upsert_error_log(d, sid, "A", "少见错误", evidence_episode_id=None)
        frequent = db.upsert_error_log(d, sid, "B", "反复错误", evidence_episode_id=None)
        db.upsert_error_log(d, sid, "B", "反复错误", evidence_episode_id=None)
        resolved = db.upsert_error_log(d, sid, "C", "已解决", evidence_episode_id=None)
        db.resolve_error_log(d, sid, resolved.id)
        d.commit()
        frequent_id = frequent.id

    rows = (await client.get(f"/api/sessions/{sid}/errors")).json()

    assert rows[0]["id"] == frequent_id
    assert rows[0]["recurrence_count"] == 2
    assert rows[-1]["status"] == "resolved"


def test_delete_session_cascades_error_logs(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")
    db.upsert_error_log(db_sess, s.id, "判别式", "条件混淆", evidence_episode_id=None)
    db_sess.commit()

    assert db.list_error_logs(db_sess, s.id)
    assert db.delete_session(db_sess, s.id) is True
    assert db.list_error_logs(db_sess, s.id) == []


async def test_goal_mode_does_not_write_error_log(db_sess, monkeypatch):
    s = engine.create_session(db_sess, title="", role="推进伙伴", goal="完成作品集", mode="goal")

    async def fake_chat_json(system, messages, **kwargs):
        return _examiner_failure("条件混淆")

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    await engine.run_turn(db_sess, s.id, "懂了，来验证")

    assert db.list_error_logs(db_sess, s.id) == []


def test_pwa_context_has_error_tab_and_top_recurrence_view():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'data-context-tab="errors"' in html
    assert "renderContextErrors" in html
    assert "recurrence_count" in html
    assert "linked_episode_ids" in html
    assert "错因" in html
