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


def test_strategy_settings_prompt_includes_executable_constraints(db_sess):
    s = engine.create_session(
        db_sess,
        title="",
        role="高三生",
        goal="数学130",
        settings={
            "feedback_intensity": 4,
            "probing_intensity": 5,
            "correction_timing": "summary_only",
            "review_frequency": "high",
            "tone": "calm",
            "proactivity": "high",
            "privacy_level": "strict",
            "scaffold_intensity": 2,
        },
    )

    prompt = engine.build_system_prompt(s, [], [])

    assert "# 策略设置" in prompt
    assert "连续 3 轮内不允许进入 small_lecture" in prompt
    assert "禁止在追问中纠错，仅 recap 时纠正" in prompt
    assert "复习间隔阶梯改为 1/2/4/7" in prompt
    assert "隐私级别：strict" in prompt


async def test_high_probing_intensity_forces_probe_when_llm_only_asks(db_sess, monkeypatch):
    s = engine.create_session(
        db_sess,
        title="",
        role="高三生",
        goal="数学130",
        settings={"probing_intensity": 5},
    )

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "evaluation": {
                "correctness": 0.4,
                "depth": 0.3,
                "entry_status": "has_entry",
                "evidence_for_mastery": {"type": "none", "status": "none", "error_type": "", "reason": ""},
                "user_emotion": "neutral",
                "new_requirements": [],
            },
            "action": {
                "type": "ask",
                "student_role": "probing_student",
                "knowledge_point": "判别式",
                "difficulty": 0.5,
                "note": "model asked too early",
            },
            "reply": "老师，那判别式下一步怎么用？",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "因为判别式能判断二次函数和 x 轴交点")

    assert result.action["type"] == "probe"
    assert result.action["student_role"] == "probing_student"


async def test_summary_only_correction_switches_correction_turn_to_recap(db_sess, monkeypatch):
    s = engine.create_session(
        db_sess,
        title="",
        role="高三生",
        goal="数学130",
        settings={"correction_timing": "summary_only"},
    )

    async def fake_chat_json(system, messages, **kwargs):
        return {
            "evaluation": {
                "correctness": 0.2,
                "depth": 0.2,
                "entry_status": "has_entry",
                "evidence_for_mastery": {
                    "type": "correction",
                    "status": "failed",
                    "error_type": "条件错",
                    "reason": "需要纠正条件使用",
                },
                "user_emotion": "neutral",
                "new_requirements": [],
            },
            "action": {
                "type": "probe",
                "student_role": "probing_student",
                "knowledge_point": "判别式",
                "difficulty": 0.6,
                "note": "model wants to correct inside probing",
            },
            "reply": "老师，这里条件好像不对。",
            "anchor_updates": [],
        }

    monkeypatch.setattr(engine.llm, "chat_json", fake_chat_json)

    result = await engine.run_turn(db_sess, s.id, "判别式大于零时一定没有交点")

    assert result.action["type"] == "recap"
    assert result.action["student_role"] == "review_student"


def test_high_review_frequency_uses_short_review_ladder(db_sess):
    s = engine.create_session(db_sess, title="", role="高三生", goal="数学130")

    intervals = []
    for _ in range(4):
        m = db.upsert_mastery(
            db_sess,
            s.id,
            "二次函数判别式",
            correctness=0.8,
            depth=0.7,
            evidence_type="delayed_retrieval",
            verification_status="passed",
            review_frequency="high",
        )
        intervals.append(m.review_interval)

    assert intervals == [1, 2, 4, 7]


async def test_session_settings_round_trip_api(client):
    r = await client.post(
        "/api/sessions",
        json={
            "role": "高三生",
            "goal": "数学130",
            "core_self": "我需要先被理解再被推动",
            "settings": {"probing_intensity": 4, "review_frequency": "high"},
            "auto_opening": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    sid = body["id"]
    assert body["core_self"] == "我需要先被理解再被推动"
    assert body["settings"]["probing_intensity"] == 4

    r = await client.patch(
        f"/api/sessions/{sid}/settings",
        json={
            "core_self": "先给我空间，再提醒我",
            "settings": {"correction_timing": "summary_only", "privacy_level": "strict"},
        },
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["core_self"] == "先给我空间，再提醒我"
    assert updated["settings"]["correction_timing"] == "summary_only"
    assert updated["settings"]["privacy_level"] == "strict"

    detail = (await client.get(f"/api/sessions/{sid}")).json()
    assert detail["settings"]["correction_timing"] == "summary_only"


def test_pwa_settings_panel_exposes_strategy_controls():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    for element_id in [
        "setting-core-self",
        "setting-feedback-intensity",
        "setting-probing-intensity",
        "setting-correction-timing",
        "setting-review-frequency",
        "setting-tone",
        "setting-proactivity",
        "setting-privacy-level",
        "setting-scaffold-intensity",
    ]:
        assert f'id="{element_id}"' in html

    assert "function normalizeStrategySettings" in html
    assert "function formatStrategySettings" in html
    assert "function saveCurrentSessionStrategySettings" in html
    assert "build_system_prompt(session, anchors, masteries, summary_text, sourceContext, kgContextText)" in html
