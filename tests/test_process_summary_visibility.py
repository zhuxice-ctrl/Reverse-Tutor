from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from server import app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_chat_response_exposes_process_summary_and_evidence_episode_ids(client):
    r = await client.post("/api/sessions", json={
        "role": "高三生",
        "goal": "数学130",
        "auto_opening": False,
    })
    sid = r.json()["id"]

    r = await client.post(
        f"/api/sessions/{sid}/chat",
        json={"message": "因为对称轴是 x=-b/(2a)，所以先找对称轴再判断最值"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["process_summary"]
    assert "evidence_episode_ids" in body
    assert isinstance(body["evidence_episode_ids"], list)
    assert body["evidence_episode_ids"]


def test_desktop_chat_bubble_has_collapsible_process_summary():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    for label in ("本轮判断", "依据", "策略", "下一步", "证据 episodes"):
        assert label in html
    assert "renderProcessSummary" in html


def test_pwa_chat_bubble_has_collapsible_process_summary():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    for label in ("思考摘要", "公开思考摘要", "判断", "依据", "策略", "下一步", "证据 episodes"):
        assert label in html
    assert "renderProcessSummary" in html
