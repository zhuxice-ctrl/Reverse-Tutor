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
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

import db
import engine
import llm
import vision
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
IMAGE_DATA_DIR = Path(__file__).parent / "data" / "images"
IMAGE_MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    # 首次启动 seed 内置 persona 模板
    with db.SessionLocal() as s:
        db.seed_builtin_templates(s)
        db.purge_expired_images(s, datetime.utcnow())
        s.commit()


def get_db() -> DbSession:
    s = db.SessionLocal()
    try:
        yield s
    finally:
        s.close()


# --- Schemas -----------------------------------------------------------------

class CreateSessionReq(BaseModel):
    title: str = ""
    mode: str = "study"
    core_self: str = ""
    settings: dict[str, Any] = {}
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


class SessionSettingsReq(BaseModel):
    core_self: str | None = None
    settings: dict[str, Any] | None = None


class DocumentReq(BaseModel):
    session_id: str | None = None
    title: str
    source_type: Literal["md", "txt"]
    source_uri: str = ""
    content: str


def _image_retention_days(session: db.Session) -> int:
    try:
        days = int((session.settings() or {}).get("image_retention_days", 0) or 0)
    except Exception:
        days = 0
    return max(0, min(days, 365))


def _stored_image_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path(__file__).parent))
    except ValueError:
        return str(path)


# --- 健康 / 元信息 -----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    cfg = llm.get_config()
    real = cfg["mode"] != "mock"
    return {
        "ok": True,
        "llm_real": real,
        "mode": cfg["mode"],
        "model": cfg["model"] if real else None,
        "base_url": cfg["base_url"] if real else None,
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
        mode=req.mode,
        core_self=req.core_self,
        settings=req.settings,
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
    return {"reply": result.reply, "action": result.action, "process_summary": result.process_summary}


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
            "mode": r.mode,
            "core_self": r.core_self,
            "settings": r.settings(),
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


@app.patch("/api/sessions/{sid}/settings")
def update_session_settings(sid: str, req: SessionSettingsReq, d: DbSession = Depends(get_db)) -> dict:
    s = db.get_session(d, sid)
    if not s:
        raise HTTPException(404, "session not found")
    if req.core_self is not None:
        s.core_self = req.core_self
    if req.settings is not None:
        merged = {**s.settings(), **req.settings}
        s.settings_json = json.dumps(merged, ensure_ascii=False)
    s.updated_at = datetime.utcnow()
    d.commit()
    d.refresh(s)
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
        "process_summary": result.process_summary,
        "evidence_episode_ids": _evidence_episode_ids_for_action(d, sid, result.action),
    }


# --- Image extracts ---------------------------------------------------------

@app.post("/api/sessions/{sid}/images")
async def upload_session_image(sid: str, file: UploadFile = File(...), d: DbSession = Depends(get_db)) -> dict:
    s = db.get_session(d, sid)
    if not s:
        raise HTTPException(404, "session not found")
    if file.content_type not in IMAGE_MIME_EXT:
        raise HTTPException(422, "unsupported image type")
    body = await file.read()
    if len(body) > MAX_IMAGE_BYTES:
        raise HTTPException(422, "image is too large")
    db.purge_expired_images(d, datetime.utcnow())

    image_id = int(str(uuid.uuid4().int)[:12])
    ext = IMAGE_MIME_EXT[file.content_type]
    session_dir = IMAGE_DATA_DIR / sid
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / f"{image_id}{ext}"
    image_path.write_bytes(body)

    result = vision.extract_from_image(image_path)
    structure = dict(result.structure or {})
    structure.setdefault("kind", "unknown")
    structure.setdefault("stem", None)
    structure.setdefault("options", [])
    structure.setdefault("hints", [])
    detected_kps = [str(k).strip() for k in (result.detected_kps or []) if str(k).strip()]

    days = _image_retention_days(s)
    retained_until = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    original_path = _stored_image_path(image_path) if retained_until else None
    if retained_until is None and image_path.exists():
        image_path.unlink()

    episode = db.add_episode(d, sid, kind="image_extract", content=result.extracted_text or "", meta={
        "image_id": image_id,
        "structure": structure,
        "detected_kps": detected_kps,
    })
    d.flush()
    row = db.add_image_extract(
        d, sid,
        image_id=image_id,
        mime=file.content_type or "",
        extracted_text=result.extracted_text or "",
        structure=structure,
        detected_kps=detected_kps,
        episode_id=episode.id,
        original_path=original_path,
        retained_until=retained_until,
    )
    for kp in detected_kps:
        # NOTE: Image upload temporarily borrows evidence_type="retrieval" because
        # _EVIDENCE_SCORES does not yet include a dedicated image_extract type.
        # Add a new evidence enum and scoring rule before splitting that signal.
        db.upsert_mastery(
            d, sid, kp, correctness=0.0, depth=0.0,
            evidence_type="retrieval", verification_status="partial",
            evidence_episode_id=episode.id,
            updated_reason="image_extract",
        )
    d.commit()
    d.refresh(row)
    return _serialize_image_extract(row)


@app.get("/api/sessions/{sid}/images")
def list_session_images(sid: str, d: DbSession = Depends(get_db)) -> list[dict]:
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    return [_serialize_image_extract(row) for row in db.list_image_extracts(d, sid)]


@app.get("/api/sessions/{sid}/images/{image_id}")
def get_session_image(sid: str, image_id: int, d: DbSession = Depends(get_db)) -> dict:
    row = db.get_image_extract(d, sid, image_id)
    if row is None:
        raise HTTPException(404, "image not found")
    return _serialize_image_extract(row, include_original=True)


@app.get("/api/sessions/{sid}/images/{image_id}/original")
def get_session_image_original(sid: str, image_id: int, d: DbSession = Depends(get_db)) -> FileResponse:
    row = db.get_image_extract(d, sid, image_id)
    if row is None or not row.original_path or not Path(row.original_path).exists():
        raise HTTPException(404, "original image not retained")
    return FileResponse(row.original_path, media_type=row.mime)


@app.delete("/api/sessions/{sid}/images/{image_id}")
def delete_session_image(sid: str, image_id: int, d: DbSession = Depends(get_db)) -> dict:
    if not db.delete_image_extract(d, sid, image_id):
        raise HTTPException(404, "image not found")
    d.commit()
    return {"ok": True, "deleted": image_id}


# --- Memory overview / deletion --------------------------------------------

@app.get("/api/sessions/{sid}/memory")
def get_session_memory(sid: str, d: DbSession = Depends(get_db)) -> dict:
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    messages = db.list_messages(d, sid, limit=500)
    recent = [
        m for m in messages
        if m.role in {"system", "assistant"} and (m.meta().get("kind") or "")
    ][-20:]
    private_docs = (
        d.query(db.Document)
        .filter(db.Document.session_id == sid)
        .order_by(db.Document.imported_at.desc(), db.Document.id.desc())
        .all()
    )
    return {
        "anchors": [_serialize_anchor(a) for a in db.list_anchors(d, sid)],
        "mastery": [_serialize_mastery(m) for m in db.list_mastery(d, sid)],
        "error_logs": [_serialize_error_log(d, e, include_episodes=False) for e in db.list_error_logs(d, sid)],
        "images": [_serialize_image_extract(row) for row in db.list_image_extracts(d, sid)],
        "recent_episodes": [_serialize_message(m) for m in reversed(recent)],
        "documents": [_serialize_document(d, doc) for doc in private_docs],
    }


@app.delete("/api/sessions/{sid}/memory/{kind}/{rid}")
def delete_session_memory_item(sid: str, kind: str, rid: int, d: DbSession = Depends(get_db)) -> dict:
    allowed = {"anchor", "mastery", "error_log", "image", "episode", "document"}
    if kind not in allowed:
        raise HTTPException(422, "invalid memory kind")
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")

    deleted = False
    if kind == "anchor":
        deleted = db.delete_anchor(d, sid, rid)
    elif kind == "mastery":
        deleted = db.delete_mastery_entry(d, sid, rid)
    elif kind == "error_log":
        row = db.get_error_log(d, sid, rid)
        if row is not None:
            d.delete(row)
            deleted = True
    elif kind == "image":
        row = d.query(db.ImageExtract).filter(db.ImageExtract.session_id == sid, db.ImageExtract.id == rid).first()
        if row is not None:
            deleted = db.delete_image_extract(d, sid, int(row.image_id))
    elif kind == "episode":
        deleted = db.delete_episode_message(d, sid, rid)
    elif kind == "document":
        doc = db.get_document(d, rid)
        if doc is not None and doc.session_id == sid:
            deleted = db.delete_document(d, rid)

    if not deleted:
        raise HTTPException(404, "memory item not found")
    d.commit()
    return {"ok": True, "deleted": {"kind": kind, "id": rid}}


# --- Documents --------------------------------------------------------------

@app.post("/api/documents")
def create_document(req: DocumentReq, d: DbSession = Depends(get_db)) -> dict:
    content = req.content or ""
    if not content.strip():
        raise HTTPException(422, "content cannot be empty")
    if len(content.encode("utf-8")) > 500 * 1024:
        raise HTTPException(422, "content is too large")
    doc = db.add_document(
        d,
        session_id=req.session_id,
        title=req.title,
        source_type=req.source_type,
        source_uri=req.source_uri,
        content=content,
    )
    d.commit()
    d.refresh(doc)
    return _serialize_document(d, doc)


@app.get("/api/documents")
def list_documents_api(session_id: str | None = None, d: DbSession = Depends(get_db)) -> list[dict]:
    return [_serialize_document(d, doc) for doc in db.list_documents(d, session_id=session_id)]


@app.get("/api/documents/{doc_id}")
def get_document_api(doc_id: int, d: DbSession = Depends(get_db)) -> dict:
    doc = db.get_document(d, doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    return _serialize_document(d, doc)


@app.delete("/api/documents/{doc_id}")
def delete_document_api(doc_id: int, d: DbSession = Depends(get_db)) -> dict:
    if not db.delete_document(d, doc_id):
        raise HTTPException(404, "document not found")
    d.commit()
    return {"ok": True, "deleted": doc_id}


@app.post("/api/documents/{doc_id}/reindex")
def reindex_document_api(doc_id: int, d: DbSession = Depends(get_db)) -> dict:
    doc = db.reindex_document(d, doc_id)
    if doc is None:
        raise HTTPException(404, "document not found")
    d.commit()
    d.refresh(doc)
    return _serialize_document(d, doc)


# --- Error logs --------------------------------------------------------------

@app.get("/api/sessions/{sid}/errors")
def list_errors_api(sid: str, d: DbSession = Depends(get_db)) -> list[dict]:
    if not db.get_session(d, sid):
        raise HTTPException(404, "session not found")
    return [_serialize_error_log(d, e, include_episodes=False) for e in db.list_error_logs(d, sid)]


@app.get("/api/sessions/{sid}/errors/{eid}")
def get_error_api(sid: str, eid: int, d: DbSession = Depends(get_db)) -> dict:
    row = db.get_error_log(d, sid, eid)
    if row is None:
        raise HTTPException(404, "error not found")
    return _serialize_error_log(d, row, include_episodes=True)


@app.post("/api/sessions/{sid}/errors/{eid}/resolve")
def resolve_error_api(sid: str, eid: int, d: DbSession = Depends(get_db)) -> dict:
    row = db.resolve_error_log(d, sid, eid)
    if row is None:
        raise HTTPException(404, "error not found")
    d.commit()
    d.refresh(row)
    return _serialize_error_log(d, row, include_episodes=True)


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
        "mode": s.mode,
        "core_self": s.core_self,
        "settings": s.settings(),
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


def _serialize_error_log(d: DbSession, e: db.ErrorLog, *, include_episodes: bool) -> dict:
    out = {
        "id": e.id,
        "session_id": e.session_id,
        "kp": e.kp,
        "error_pattern": e.error_pattern,
        "first_seen_at": e.first_seen_at.isoformat() + "Z",
        "last_seen_at": e.last_seen_at.isoformat() + "Z",
        "recurrence_count": e.recurrence_count,
        "linked_episode_ids": e.linked_ids(),
        "status": e.status,
    }
    if include_episodes:
        episodes = []
        for mid in e.linked_ids():
            msg = d.get(db.Message, mid)
            if msg is not None and msg.session_id == e.session_id:
                episodes.append({
                    "id": msg.id,
                    "role": msg.role,
                    "content_preview": (msg.content or "")[:240],
                    "created_at": msg.created_at.isoformat() + "Z",
                    "meta": msg.meta(),
                })
        out["episodes"] = episodes
    return out


def _serialize_document(d: DbSession, doc: db.Document) -> dict:
    chunks = db.list_doc_chunks(d, doc.id)
    return {
        "id": doc.id,
        "session_id": doc.session_id,
        "title": doc.title,
        "source_type": doc.source_type,
        "source_uri": doc.source_uri,
        "hash": doc.hash,
        "chunk_count": len(chunks),
        "imported_at": doc.imported_at.isoformat() + "Z",
        "updated_at": doc.updated_at.isoformat() + "Z",
    }


def _serialize_image_extract(row: db.ImageExtract, *, include_original: bool = False) -> dict:
    retained = bool(row.original_path and Path(row.original_path).exists())
    out = {
        "id": row.id,
        "image_id": row.image_id,
        "session_id": row.session_id,
        "mime": row.mime,
        "extracted_text": row.extracted_text,
        "structure": row.structure(),
        "detected_kps": row.detected_kps(),
        "episode_id": row.episode_id,
        "original_retained_until": row.retained_until.isoformat() + "Z" if row.retained_until else None,
        "original_url": f"/api/sessions/{row.session_id}/images/{row.image_id}/original" if retained else None,
        "created_at": row.created_at.isoformat() + "Z",
    }
    if include_original:
        out["original_path"] = row.original_path if retained else None
    return out


def _evidence_episode_ids_for_action(d: DbSession, sid: str, action: dict) -> list[int]:
    kp = (action.get("knowledge_point") or "").strip()
    if not kp:
        return []
    for m in db.list_mastery(d, sid):
        existing = (m.knowledge_point or "").strip()
        if existing == kp or existing in kp or kp in existing:
            return m.evidence_ids()
    return []


def _serialize_mastery(m: db.Mastery) -> dict:
    score = float(getattr(m, "mastery_score", 0.0) or (m.level or 0.0) * 100)
    return {
        "id": m.id,
        "knowledge_point": m.knowledge_point,
        "level": m.level,
        "mastery_score": score,
        "mastery_band": db.mastery_band(score),
        "confidence_score": getattr(m, "confidence_score", 0.0) or 0.0,
        "attempts": m.attempts,
        "last_correctness": m.last_correctness, "last_depth": m.last_depth,
        "last_evidence_type": getattr(m, "last_evidence_type", "none") or "none",
        "last_verification_status": getattr(m, "last_verification_status", "none") or "none",
        "error_type": getattr(m, "error_type", "") or "",
        "evidence_episode_ids": m.evidence_ids() if hasattr(m, "evidence_ids") else [],
        "updated_reason": getattr(m, "updated_reason", "") or "",
        "next_review_at": m.next_review_at.isoformat() + "Z" if getattr(m, "next_review_at", None) else None,
        "review_interval": getattr(m, "review_interval", 0) or 0,
        "updated_at": m.updated_at.isoformat() + "Z" if getattr(m, "updated_at", None) else None,
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
        out.append(
            f"- {m['knowledge_point']}: {m['mastery_score']:.0f}/100 "
            f"({m['mastery_band']}，试 {m['attempts']} 次)"
        )
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
