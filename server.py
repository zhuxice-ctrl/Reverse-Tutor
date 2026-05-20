"""FastAPI 服务入口。

REST API：
  POST  /api/sessions                       创建会话
  GET   /api/sessions                       列出会话
  GET   /api/sessions/{sid}                 会话详情（含 anchors/messages/mastery 概要）
  POST  /api/sessions/{sid}/chat            一轮对话（核心）
  GET   /api/sessions/{sid}/anchors         查看锚
  POST  /api/sessions/{sid}/anchors         手动追加锚
  GET   /api/sessions/{sid}/export          导出 (format=md|json)
  POST  /api/adapters/{platform}/webhook    平台 webhook 入口
  GET   /api/health                         健康检查
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

import db
import engine
import llm
import trial
from adapters import dispatch_webhook

# --- App ---------------------------------------------------------------------

app = FastAPI(title="Reverse Tutor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ENV_FILE = Path(__file__).parent / ".env"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    # 首次启动 seed 内置 persona 模板
    with db.SessionLocal() as s:
        db.seed_builtin_templates(s)


def get_db() -> DbSession:
    s = db.SessionLocal()
    try:
        yield s
    finally:
        s.close()


# --- Schemas -----------------------------------------------------------------

class CreateSessionReq(BaseModel):
    title: str = ""
    role: str = Field(..., description="AI 扮演的角色，如：高三学生")
    goal: str = Field(..., description="角色要达成的目标，如：一年内数学考 130 分")
    deadline: str = ""
    personality: str = "好奇、有点贪玩、容易丧气但能被鼓励"
    initial_requirements: list[str] = []
    auto_opening: bool = True  # 创建后立即让 AI 主动开场


class ChatReq(BaseModel):
    message: str


class AnchorReq(BaseModel):
    kind: Literal["initial", "requirement", "milestone", "constraint"] = "requirement"
    content: str
    weight: float = 1.0


class TrialRedeemReq(BaseModel):
    code: str
    device_id: str


# --- 健康 / 元信息 -----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    real = llm.has_real_llm()
    return {
        "ok": True,
        "llm_real": real,
        "mode": "live" if real else "mock",
        "model": llm.LLM_MODEL if real else None,
        "base_url": llm.LLM_BASE_URL if real else None,
        "adapters": ["feishu", "qq", "hermes"],
        "time": datetime.utcnow().isoformat() + "Z",
    }


# --- LLM 运行时配置 ---------------------------------------------------------

@app.get("/api/llm-config")
def get_llm_config() -> dict:
    return llm.get_config()


@app.post("/api/llm-config")
async def set_llm_config(body: dict) -> dict:
    """运行时切换 LLM 凭据（不写回 .env，进程退出失效）。"""
    llm.apply_config(
        body.get("base_url", ""),
        body.get("api_key"),  # None 表示保留原 key（前端"留空 = 不变"）
        body.get("model", ""),
    )
    return llm.get_config()


@app.post("/api/llm-config/save")
async def save_llm_config(body: dict) -> dict:
    """Apply the runtime LLM config and persist it to the local .env file."""
    llm.apply_config(
        body.get("base_url", ""),
        body.get("api_key"),
        body.get("model", ""),
    )
    try:
        _write_env_values(ENV_FILE, {
            "LLM_BASE_URL": llm.LLM_BASE_URL,
            "LLM_API_KEY": llm.LLM_API_KEY,
            "LLM_MODEL": llm.LLM_MODEL,
        })
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except OSError as e:
        raise HTTPException(500, f"failed to write .env: {e}") from e
    return {**llm.get_config(), "saved": True, "path": str(ENV_FILE)}


@app.post("/api/llm-config/test")
async def test_llm_connectivity() -> dict:
    """发一个最小请求验证联通性。"""
    return await llm.ping()


def _write_env_values(path: Path, values: dict[str, str]) -> None:
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} cannot contain newlines")

    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out: list[str] = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in pending:
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)
    if out and pending:
        out.append("")
    out.extend(f"{key}={value}" for key, value in pending.items())
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


# --- Trial LLM proxy ---------------------------------------------------------

@app.post("/api/trial/redeem")
def redeem_trial(req: TrialRedeemReq, d: DbSession = Depends(get_db)) -> dict:
    try:
        return trial.redeem_code(d, req.code, req.device_id)
    except trial.TrialError as e:
        raise HTTPException(e.status_code, str(e)) from e


@app.get("/api/trial/status")
def trial_status(
    authorization: str = Header(default=""),
    d: DbSession = Depends(get_db),
) -> dict:
    try:
        row = trial.get_code_by_token(d, _bearer_token(authorization))
        return trial.quota_status(row)
    except trial.TrialError as e:
        raise HTTPException(e.status_code, str(e)) from e


@app.post("/api/trial/chat/completions")
async def trial_chat_completions(
    body: dict,
    authorization: str = Header(default=""),
    d: DbSession = Depends(get_db),
) -> dict:
    if body.get("stream"):
        raise HTTPException(400, "trial proxy does not support stream; retry without stream")
    try:
        row = trial.get_code_by_token(d, _bearer_token(authorization))
        payload = trial.build_provider_payload(body)
        trial.ensure_quota_available(row, payload)
        response = await trial.call_provider(payload)
        trial.charge_usage(d, row, payload, response)
        return response
    except trial.TrialError as e:
        raise HTTPException(e.status_code, str(e)) from e


def _bearer_token(authorization: str) -> str:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise trial.TrialError("缺少体验 token", status_code=401)
    token = authorization[len(prefix):].strip()
    if not token:
        raise trial.TrialError("缺少体验 token", status_code=401)
    return token


# --- Sessions ---------------------------------------------------------------

@app.post("/api/sessions")
async def create_session(req: CreateSessionReq, d: DbSession = Depends(get_db)) -> dict:
    s = engine.create_session(
        d,
        title=req.title,
        role=req.role,
        goal=req.goal,
        deadline=req.deadline,
        personality=req.personality,
        initial_requirements=req.initial_requirements,
    )
    if req.auto_opening:
        try:
            await engine.run_opening_turn(d, s.id)
        except Exception as e:
            # 开场失败不阻塞会话创建（mock 模式肯定能成；真 LLM 偶发故障时降级）
            db.add_message(d, s.id, "assistant",
                           "（嗯……老师在吗？我们什么时候开始？）",
                           meta={"opening": True, "error": str(e)[:200]})
            d.commit()
    return _serialize_session(d, s, include_messages=True)


@app.delete("/api/sessions/{sid}")
def delete_session_api(sid: str, d: DbSession = Depends(get_db)) -> dict:
    if not db.delete_session(d, sid):
        raise HTTPException(404, "session not found")
    return {"ok": True, "deleted": sid}


@app.post("/api/sessions/{sid}/opening")
async def trigger_opening(sid: str, d: DbSession = Depends(get_db)) -> dict:
    """手动触发开场（debug/重置用）。"""
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    try:
        result = await engine.run_opening_turn(d, sid)
    except llm.LLMError as e:
        raise HTTPException(502, f"LLM error: {e}") from e
    return {"reply": result.reply, "action": result.action}


@app.post("/api/sessions/{sid}/summarize")
async def trigger_summarize(
    sid: str, force: bool = True, d: DbSession = Depends(get_db)
) -> dict:
    """手动触发历史压缩。force=True 时不论是否到阈值都压缩。"""
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    try:
        info = await engine.maybe_summarize(d, sid, force=force)
    except llm.LLMError as e:
        raise HTTPException(502, f"LLM error: {e}") from e
    if info is None:
        return {"ok": True, "skipped": "nothing to summarize"}
    return {"ok": True, **info}


@app.get("/api/sessions")
def list_sessions(d: DbSession = Depends(get_db)) -> list[dict]:
    rows = d.query(db.Session).order_by(db.Session.updated_at.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "persona": r.persona(),
            "created_at": r.created_at.isoformat() + "Z",
            "updated_at": r.updated_at.isoformat() + "Z",
        }
        for r in rows
    ]


@app.get("/api/sessions/{sid}")
def get_session(sid: str, d: DbSession = Depends(get_db)) -> dict:
    s = db.get_session(d, sid)
    if not s:
        raise HTTPException(404, "session not found")
    return _serialize_session(d, s, include_messages=True)


# --- Chat -------------------------------------------------------------------

@app.post("/api/sessions/{sid}/chat")
async def chat(sid: str, req: ChatReq, d: DbSession = Depends(get_db)) -> dict:
    s = db.get_session(d, sid)
    if not s:
        raise HTTPException(404, "session not found")
    try:
        result = await engine.run_turn(d, sid, req.message)
    except llm.LLMError as e:
        raise HTTPException(502, f"LLM error: {e}") from e
    return {
        "reply": result.reply,
        "evaluation": result.evaluation,
        "action": result.action,
        "anchor_updates": result.anchor_updates,
    }


# --- Anchors ----------------------------------------------------------------

@app.get("/api/sessions/{sid}/anchors")
def get_anchors(sid: str, d: DbSession = Depends(get_db)) -> list[dict]:
    return [_serialize_anchor(a) for a in db.list_anchors(d, sid)]


@app.post("/api/sessions/{sid}/anchors")
def add_anchor_api(sid: str, req: AnchorReq, d: DbSession = Depends(get_db)) -> dict:
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    a = db.add_anchor(d, sid, req.kind, req.content, weight=req.weight)
    d.commit()
    d.refresh(a)
    return _serialize_anchor(a)


@app.delete("/api/anchors/{aid}")
def delete_anchor_api(aid: int, d: DbSession = Depends(get_db)) -> dict:
    a = d.get(db.Anchor, aid)
    if a is None:
        raise HTTPException(404, "anchor not found")
    d.delete(a); d.commit()
    return {"ok": True, "deleted": aid}


# --- Persona Templates ------------------------------------------------------

def _serialize_template(t: db.PersonaTemplate) -> dict:
    return {
        "id": t.id,
        "label": t.label,
        "role": t.role,
        "goal": t.goal,
        "deadline": t.deadline,
        "personality": t.personality,
        "reqs": t.reqs(),
        "builtin": bool(t.builtin),
        "sort": t.sort,
    }


@app.get("/api/templates")
def list_templates(d: DbSession = Depends(get_db)) -> list[dict]:
    return [_serialize_template(t) for t in db.list_templates(d)]


@app.post("/api/templates")
def create_template_api(body: dict, d: DbSession = Depends(get_db)) -> dict:
    required = ("label", "role", "goal")
    for k in required:
        if not body.get(k):
            raise HTTPException(400, f"missing field: {k}")
    t = db.create_template(
        d,
        label=body["label"], role=body["role"], goal=body["goal"],
        deadline=body.get("deadline", ""),
        personality=body.get("personality", ""),
        reqs=body.get("reqs", []),
        sort=body.get("sort", 100),
    )
    return _serialize_template(t)


@app.put("/api/templates/{tid}")
def update_template_api(tid: int, body: dict, d: DbSession = Depends(get_db)) -> dict:
    t = db.get_template(d, tid)
    if t is None:
        raise HTTPException(404, "template not found")
    db.update_template(d, t, **{k: v for k, v in body.items()
                                 if k in {"label", "role", "goal", "deadline",
                                          "personality", "reqs", "sort"}})
    return _serialize_template(t)


@app.delete("/api/templates/{tid}")
def delete_template_api(tid: int, d: DbSession = Depends(get_db)) -> dict:
    t = db.get_template(d, tid)
    if t is None:
        raise HTTPException(404, "template not found")
    if t.builtin:
        raise HTTPException(400, "builtin template cannot be deleted")
    db.delete_template(d, tid)
    return {"ok": True, "deleted": tid}


# --- Export -----------------------------------------------------------------

@app.get("/api/sessions/{sid}/export")
def export_session(
    sid: str, format: Literal["md", "json"] = "md", d: DbSession = Depends(get_db)
):
    s = db.get_session(d, sid)
    if not s:
        raise HTTPException(404, "session not found")
    full = _serialize_session(d, s, include_messages=True)
    if format == "json":
        return JSONResponse(full)
    return PlainTextResponse(
        _to_markdown(full),
        headers={
            "Content-Disposition": f'attachment; filename="session_{sid}.md"'
        },
        media_type="text/markdown; charset=utf-8",
    )


# --- Webhook 入口（多平台适配器）--------------------------------------------

@app.post("/api/adapters/{platform}/webhook")
async def adapter_webhook(
    platform: str, request: Request, d: DbSession = Depends(get_db)
) -> dict:
    body = await request.json()
    return await dispatch_webhook(platform, body, d, engine)


# --- Bindings 管理 ----------------------------------------------------------

@app.get("/api/bindings")
def list_bindings_api(d: DbSession = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": b.id,
            "platform": b.platform,
            "external_id": b.external_id,
            "session_id": b.session_id,
            "onboarding_state": b.onboarding_state,
            "onboarding_data": b.onboarding(),
            "created_at": b.created_at.isoformat() + "Z",
            "updated_at": b.updated_at.isoformat() + "Z",
        }
        for b in db.list_bindings(d)
    ]


@app.delete("/api/bindings/{bid}")
def delete_binding_api(bid: int, d: DbSession = Depends(get_db)) -> dict:
    if not db.delete_binding(d, bid):
        raise HTTPException(404, "binding not found")
    return {"ok": True, "deleted": bid}


# --- 序列化辅助 -------------------------------------------------------------

def _serialize_session(
    d: DbSession, s: db.Session, *, include_messages: bool = False
) -> dict:
    out = {
        "id": s.id,
        "title": s.title,
        "persona": s.persona(),
        "plan": s.plan(),
        "created_at": s.created_at.isoformat() + "Z",
        "updated_at": s.updated_at.isoformat() + "Z",
        "anchors": [_serialize_anchor(a) for a in db.list_anchors(d, s.id)],
        "mastery": [_serialize_mastery(m) for m in db.list_mastery(d, s.id)],
    }
    if include_messages:
        out["messages"] = [_serialize_message(m) for m in db.list_messages(d, s.id, limit=500)]
    return out


def _serialize_anchor(a: db.Anchor) -> dict:
    return {
        "id": a.id, "kind": a.kind, "content": a.content,
        "weight": a.weight, "created_at": a.created_at.isoformat() + "Z",
    }


def _serialize_message(m: db.Message) -> dict:
    return {
        "id": m.id, "role": m.role, "content": m.content,
        "meta": m.meta(), "created_at": m.created_at.isoformat() + "Z",
    }


def _serialize_mastery(m: db.Mastery) -> dict:
    return {
        "knowledge_point": m.knowledge_point, "level": m.level,
        "attempts": m.attempts,
        "last_correctness": m.last_correctness, "last_depth": m.last_depth,
    }


def _to_markdown(s: dict) -> str:
    persona = s["persona"]
    out = [
        f"# {s['title']}",
        "",
        "## Persona",
        f"- 角色: {persona.get('role','')}",
        f"- 目标: {persona.get('goal','')}",
        f"- 截止: {persona.get('deadline','')}",
        f"- 性格: {persona.get('personality','')}",
        "",
        "## 主线锚 (Anchors)",
    ]
    for a in s["anchors"]:
        out.append(f"- **[{a['kind']} w={a['weight']:.1f}]** {a['content']}")
    out += ["", "## 知识点掌握度"]
    for m in s["mastery"]:
        out.append(f"- {m['knowledge_point']}: {m['level']:.2f} (试 {m['attempts']} 次)")
    out += ["", "## 对话记录"]
    for m in s.get("messages", []):
        who = "👤 用户" if m["role"] == "user" else "🎓 学生(AI)"
        out.append(f"\n### {who}  _{m['created_at']}_\n\n{m['content']}\n")
        meta = m.get("meta") or {}
        if meta.get("action"):
            a = meta["action"]
            ev = meta.get("evaluation", {})
            out.append(
                f"> _action=`{a.get('type')}` · kp=`{a.get('knowledge_point','')}` · "
                f"correctness={ev.get('correctness','?')} · depth={ev.get('depth','?')} · "
                f"emotion=`{ev.get('user_emotion','?')}`_"
            )
    return "\n".join(out)


# --- 静态前端挂载 -----------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Reverse Tutor</h1><p>static/index.html 缺失</p>")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 移动端 PWA：访问 /app 自动 serve static/app/index.html
APP_DIR = STATIC_DIR / "app"
APP_DIR.mkdir(exist_ok=True)
app.mount("/app", StaticFiles(directory=str(APP_DIR), html=True), name="app")
