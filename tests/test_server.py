"""HTTP API 端到端测试（用 httpx ASGITransport，不开端口）。"""
from __future__ import annotations

import httpx
import pytest

import server
import db
import trial
from server import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["adapters"] == ["feishu", "qq", "hermes"]


async def test_full_session_lifecycle(client):
    # 创建（auto_opening=True 默认）
    r = await client.post("/api/sessions", json={"role": "高三生", "goal": "数学130"})
    assert r.status_code == 200
    s = r.json()
    sid = s["id"]
    # 自动开场 → 应有 1 条 assistant message
    msgs = s["messages"]
    assert len(msgs) == 1 and msgs[0]["role"] == "assistant"

    # 发一轮 chat
    r = await client.post(f"/api/sessions/{sid}/chat", json={"message": "对称轴 -b/2a"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"]
    assert "action" in body and body["action"].get("type")

    # 拉详情
    r = await client.get(f"/api/sessions/{sid}")
    full = r.json()
    assert len(full["messages"]) >= 3
    assert len(full["anchors"]) >= 1
    assert len(full["mastery"]) >= 1

    # 手动加 anchor
    r = await client.post(f"/api/sessions/{sid}/anchors",
                          json={"kind": "requirement", "content": "test req", "weight": 2.0})
    assert r.status_code == 200

    # 导出 MD
    r = await client.get(f"/api/sessions/{sid}/export?format=md")
    assert r.status_code == 200
    assert "Persona" in r.text and "对称轴" in r.text

    # 删除
    r = await client.delete(f"/api/sessions/{sid}")
    assert r.status_code == 200
    r = await client.get(f"/api/sessions/{sid}")
    assert r.status_code == 404


async def test_webhook_to_bindings_endpoint(client):
    r = await client.post("/api/adapters/hermes/webhook",
                          json={"external_id": "u-srv-1", "text": "hi"})
    assert r.status_code == 200
    assert r.json()["stage"] == "welcome"

    r = await client.get("/api/bindings")
    assert r.status_code == 200
    bs = r.json()
    assert any(b["external_id"] == "u-srv-1" for b in bs)


async def test_summarize_endpoint(client):
    r = await client.post("/api/sessions", json={"role": "r", "goal": "g"})
    sid = r.json()["id"]
    for i in range(3):
        await client.post(f"/api/sessions/{sid}/chat", json={"message": f"m{i}"})
    r = await client.post(f"/api/sessions/{sid}/summarize?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body.get("summarized_count", 0) >= 1


async def test_llm_config_get_post_test_cycle(client):
    # 默认 mock
    r = await client.get("/api/llm-config")
    assert r.json()["mode"] == "mock"

    # POST 切到 live（凭据是假的指向无人监听端口，连接立即拒绝）
    r = await client.post("/api/llm-config", json={
        "base_url": "http://127.0.0.1:1/v1",
        "api_key": "sk-fake",
        "model": "fake-model",
    })
    cfg = r.json()
    assert cfg["mode"] == "live"
    assert cfg["model"] == "fake-model"

    # ping 应被快速 catch 为 ok=False（连接拒绝）
    r = await client.post("/api/llm-config/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "error" in body or "reason" in body

    # POST 空配置回退 mock
    r = await client.post("/api/llm-config", json={"base_url": "", "api_key": "", "model": ""})
    assert r.json()["mode"] == "mock"


async def test_llm_config_save_writes_local_env_and_masks_key(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DB_URL=sqlite:///keep.db\nOTHER=value\n", encoding="utf-8")
    monkeypatch.setattr(server, "ENV_FILE", env_file)

    r = await client.post("/api/llm-config/save", json={
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-local-test",
        "model": "deepseek-chat",
    })

    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "live"
    assert body["saved"] is True
    assert body["path"] == str(env_file)

    saved = env_file.read_text(encoding="utf-8")
    assert "DB_URL=sqlite:///keep.db" in saved
    assert "OTHER=value" in saved
    assert "LLM_BASE_URL=https://api.deepseek.com/v1" in saved
    assert "LLM_API_KEY=sk-local-test" in saved
    assert "LLM_MODEL=deepseek-chat" in saved

    r = await client.get("/api/llm-config")
    cfg = r.json()
    assert cfg["has_api_key"] is True
    assert "sk-local-test" not in str(cfg)

    await client.post("/api/llm-config", json={"base_url": "", "api_key": "", "model": ""})


async def test_trial_redeem_binds_device_and_proxy_charges_usage(client, monkeypatch):
    with db.SessionLocal() as s:
        s.add(db.TrialCode(code="RT-TEST", total_quota_micro_cny=500_000, daily_quota_micro_cny=0))
        s.commit()

    r = await client.post("/api/trial/redeem", json={"code": "rt-test", "device_id": "device-abc-123"})
    assert r.status_code == 200
    redeemed = r.json()
    token = redeemed["trial_token"]
    assert redeemed["daily_limit_enabled"] is False
    assert redeemed["daily_remaining_yuan"] == 0.5
    assert redeemed["total_remaining_yuan"] == 0.5

    r = await client.post("/api/trial/redeem", json={"code": "RT-TEST", "device_id": "device-other-999"})
    assert r.status_code == 403

    async def fake_call_provider(payload):
        assert payload["model"] == trial.provider_model()
        assert payload["max_tokens"] <= trial.max_output_tokens()
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    monkeypatch.setattr(trial, "call_provider", fake_call_provider)
    r = await client.post(
        "/api/trial/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model": "client-side-model-is-ignored",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 9999,
        },
    )
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "ok"

    r = await client.get("/api/trial/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    status = r.json()
    assert status["request_count"] == 1
    assert status["total_remaining_micro_cny"] < 500_000


async def test_trial_proxy_rejects_stream_for_client_fallback(client):
    with db.SessionLocal() as s:
        s.add(db.TrialCode(code="RT-STREAM", total_quota_micro_cny=500_000, daily_quota_micro_cny=0))
        s.commit()
    r = await client.post("/api/trial/redeem", json={"code": "RT-STREAM", "device_id": "device-stream-1"})
    token = r.json()["trial_token"]

    r = await client.post(
        "/api/trial/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "ping"}], "stream": True},
    )
    assert r.status_code == 400
    assert "stream" in r.text


async def test_trial_proxy_prechecks_quota_before_provider_call(client, monkeypatch):
    with db.SessionLocal() as s:
        s.add(db.TrialCode(code="RT-LOW", total_quota_micro_cny=50, daily_quota_micro_cny=0))
        s.commit()
    r = await client.post("/api/trial/redeem", json={"code": "RT-LOW", "device_id": "device-low-1"})
    token = r.json()["trial_token"]

    async def fake_call_provider(payload):
        raise AssertionError("provider should not be called when estimated quota is insufficient")

    monkeypatch.setattr(trial, "call_provider", fake_call_provider)
    r = await client.post(
        "/api/trial/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 700},
    )
    assert r.status_code == 402
    assert "额度不足" in r.text


async def test_anchor_delete(client):
    r = await client.post("/api/sessions", json={"role": "r", "goal": "g"})
    sid = r.json()["id"]
    r = await client.post(f"/api/sessions/{sid}/anchors",
                          json={"kind": "requirement", "content": "x", "weight": 1.0})
    aid = r.json()["id"]
    r = await client.delete(f"/api/anchors/{aid}")
    assert r.status_code == 200 and r.json()["ok"] is True

    # 再删一次应 404
    r = await client.delete(f"/api/anchors/{aid}")
    assert r.status_code == 404
