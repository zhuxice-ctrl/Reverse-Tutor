"""SQLite + SQLAlchemy 持久化层。

表设计：
  sessions   一次学习会话（含 persona）
  anchors    主线锚（防漂移核心）
  messages   对话历史 + 每轮的评估/动作元数据
  mastery    用户对每个知识点的掌握度（0-1）
"""
from __future__ import annotations

import json
import os
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, inspect, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Session as DbSession, sessionmaker

from chunker import chunk_text

load_dotenv()

DB_URL = os.getenv("DB_URL", "sqlite:///./reverse_tutor.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    mode = Column(String, default="study")       # study | goal | companion
    core_self = Column(Text, default="")         # 用户最希望 AI 理解的一点
    persona_json = Column(Text, nullable=False)  # {role, goal, deadline, personality, mood}
    settings_json = Column(Text, default="{}")   # slider/toggle settings
    plan_json = Column(Text, default="[]")       # 课程主线节点列表
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def persona(self) -> dict:
        return json.loads(self.persona_json)

    def plan(self) -> list:
        return json.loads(self.plan_json or "[]")

    def settings(self) -> dict:
        try:
            raw = json.loads(self.settings_json or "{}")
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}


class Anchor(Base):
    """主线锚 —— 每次 LLM 调用前注入 system prompt，防漂移。"""
    __tablename__ = "anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    kind = Column(String, nullable=False)   # initial | requirement | milestone | constraint
    content = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)     # 权重，越高越优先注入
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)   # user | assistant | system
    content = Column(Text, nullable=False)
    meta_json = Column(Text, default="{}")  # 评估/动作等元数据
    created_at = Column(DateTime, default=datetime.utcnow)

    def meta(self) -> dict:
        try:
            return json.loads(self.meta_json or "{}")
        except Exception:
            return {}


class Mastery(Base):
    """用户对每个知识点的掌握度。"""
    __tablename__ = "mastery"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    knowledge_point = Column(String, nullable=False)
    level = Column(Float, default=0.0)      # 0-1, compatibility view of mastery_score
    mastery_score = Column(Float, default=0.0)      # 0-100
    confidence_score = Column(Float, default=0.0)   # subjective/soft confidence, 0-100
    attempts = Column(Integer, default=0)
    last_correctness = Column(Float, default=0.0)
    last_depth = Column(Float, default=0.0)
    last_evidence_type = Column(String, default="none")
    last_verification_status = Column(String, default="none")
    error_type = Column(String, default="")
    evidence_episode_ids = Column(Text, default="[]")
    updated_reason = Column(Text, default="")
    next_review_at = Column(DateTime, nullable=True)
    review_interval = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def evidence_ids(self) -> list[int]:
        try:
            raw = json.loads(self.evidence_episode_ids or "[]")
        except Exception:
            return []
        return [int(x) for x in raw if isinstance(x, int) or str(x).isdigit()]


class ErrorLog(Base):
    __tablename__ = "error_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    kp = Column(String, nullable=False)
    error_pattern = Column(String, nullable=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    recurrence_count = Column(Integer, default=1)
    linked_episode_ids = Column(Text, default="[]")
    status = Column(String, default="active")

    __table_args__ = (
        UniqueConstraint("session_id", "kp", "error_pattern", name="uq_error_log_pattern"),
    )

    def linked_ids(self) -> list[int]:
        try:
            raw = json.loads(self.linked_episode_ids or "[]")
        except Exception:
            return []
        return [int(x) for x in raw if isinstance(x, int) or str(x).isdigit()]


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=True)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_uri = Column(String, default="")
    hash = Column(String, nullable=False, index=True)
    content_text = Column(Text, nullable=False, default="")
    imported_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), index=True)
    chunk_index = Column(Integer)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("doc_id", "chunk_index", name="uq_doc_chunk_index"),)


class ImageExtract(Base):
    __tablename__ = "image_extracts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    image_id = Column(Integer, unique=True, nullable=False)
    mime = Column(String, default="")
    extracted_text = Column(Text, default="")
    structure_json = Column(Text, default="{}")
    detected_kps_json = Column(Text, default="[]")
    episode_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    original_path = Column(String, nullable=True)
    retained_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def structure(self) -> dict:
        try:
            raw = json.loads(self.structure_json or "{}")
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def detected_kps(self) -> list[str]:
        try:
            raw = json.loads(self.detected_kps_json or "[]")
        except Exception:
            return []
        return [str(x) for x in raw if str(x).strip()]


class GoalState(Base):
    __tablename__ = "goal_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    state_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanionState(Base):
    __tablename__ = "companion_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    state_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PersonaTemplate(Base):
    """Persona 模板（创建会话时一键填充用）。"""
    __tablename__ = "persona_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)        # UI 展示的短名
    role = Column(String, nullable=False)
    goal = Column(String, nullable=False)
    deadline = Column(String, default="")
    personality = Column(String, default="")
    reqs_json = Column(Text, default="[]")        # 初始 requirements
    builtin = Column(Integer, default=0)          # 1=系统内置，禁止删
    sort = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def reqs(self) -> list[str]:
        try:
            return json.loads(self.reqs_json or "[]")
        except Exception:
            return []


class Binding(Base):
    """外部平台用户 ↔ 会话 的绑定。

    onboarding_state 取值：
      asking_role     刚进入，等用户说要扮演什么角色
      asking_goal     已拿到 role，等目标
      asking_deadline 已拿到 goal，等截止时间
      active          完成引导，session_id 已写入，后续走正常引擎
    """
    __tablename__ = "bindings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String, nullable=False, index=True)     # feishu / qq / hermes
    external_id = Column(String, nullable=False, index=True)  # 平台用户/群的唯一 id
    session_id = Column(String, nullable=True, index=True)    # onboarding 完成后才填
    onboarding_state = Column(String, default="asking_role")
    onboarding_data = Column(Text, default="{}")              # 临时收集的 role/goal/deadline
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_binding_platform_user"),
    )

    def onboarding(self) -> dict:
        try:
            return json.loads(self.onboarding_data or "{}")
        except Exception:
            return {}


class KGNode(Base):
    __tablename__ = "kg_nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    properties_json = Column(Text, default="{}")
    source_episode_ids = Column(Text, default="[]")
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")

    __table_args__ = (
        UniqueConstraint("session_id", "kind", "name", name="uq_kg_node_session_kind_name"),
    )

    def properties(self) -> dict:
        try:
            return json.loads(self.properties_json or "{}")
        except Exception:
            return {}

    def episode_ids(self) -> list[int]:
        try:
            raw = json.loads(self.source_episode_ids or "[]")
        except Exception:
            return []
        return [int(x) for x in raw if isinstance(x, int) or str(x).isdigit()]


class KGEdge(Base):
    __tablename__ = "kg_edges"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    source_id = Column(Integer, ForeignKey("kg_nodes.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("kg_nodes.id"), nullable=False)
    relation = Column(String, nullable=False)
    weight = Column(Float, default=1.0)
    properties_json = Column(Text, default="{}")
    source_episode_ids = Column(Text, default="[]")
    valid_from = Column(DateTime, default=datetime.utcnow)
    invalidated_at = Column(DateTime, nullable=True)
    status = Column(String, default="active")

    def properties(self) -> dict:
        try:
            return json.loads(self.properties_json or "{}")
        except Exception:
            return {}

    def episode_ids(self) -> list[int]:
        try:
            raw = json.loads(self.source_episode_ids or "[]")
        except Exception:
            return []
        return [int(x) for x in raw if isinstance(x, int) or str(x).isdigit()]


PROCESS_KG_KINDS = {
    "background_reply",
    "background_generation",
    "free_reply",
    "model_free_reply",
    "ordinary_message_event",
    "normal_message_event",
    "message_event",
}
SEMANTIC_KG_KINDS = {
    "person",
    "concept",
    "error_pattern",
    "preference",
    "method",
    "mastery_state",
    "persona_trait",
    "source_topic",
    "source_memory",
}
PROCESS_KG_NAMES = {
    "后台回复",
    "后台生成",
    "自由回复",
    "模型自由回复",
    "普通消息事件",
}


def _normalize_kg_kind(kind: str) -> str:
    return str(kind or "").strip().lower().replace("-", "_").replace(" ", "_")


def is_process_kg_node(kind: str, name: str = "") -> bool:
    clean_kind = _normalize_kg_kind(kind)
    clean_name = str(name or "").strip()
    return clean_kind in PROCESS_KG_KINDS or clean_name in PROCESS_KG_NAMES


def is_semantic_kg_node(kind: str, name: str = "") -> bool:
    clean_kind = _normalize_kg_kind(kind)
    return bool(str(name or "").strip()) and clean_kind in SEMANTIC_KG_KINDS and not is_process_kg_node(kind, name)


def init_db() -> None:
    Base.metadata.create_all(engine)
    ensure_schema()


def ensure_schema() -> None:
    """Lightweight SQLite migration for newly added V1 learning-state columns."""
    if engine.dialect.name != "sqlite":
        return
    desired: dict[str, dict[str, str]] = {
        "sessions": {
            "mode": "VARCHAR DEFAULT 'study'",
            "core_self": "TEXT DEFAULT ''",
            "settings_json": "TEXT DEFAULT '{}'",
        },
        "mastery": {
            "mastery_score": "FLOAT DEFAULT 0.0",
            "confidence_score": "FLOAT DEFAULT 0.0",
            "last_evidence_type": "VARCHAR DEFAULT 'none'",
            "last_verification_status": "VARCHAR DEFAULT 'none'",
            "error_type": "VARCHAR DEFAULT ''",
            "evidence_episode_ids": "TEXT DEFAULT '[]'",
            "updated_reason": "TEXT DEFAULT ''",
            "next_review_at": "DATETIME",
            "review_interval": "INTEGER DEFAULT 0",
        },
        "documents": {
            "content_text": "TEXT NOT NULL DEFAULT ''",
        },
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in desired.items():
            if table not in existing_tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "documents" in existing_tables and "doc_chunks" in existing_tables:
            rows = conn.execute(text(
                "SELECT id FROM documents WHERE COALESCE(content_text, '') = ''"
            )).fetchall()
            for (doc_id,) in rows:
                chunks = conn.execute(text(
                    "SELECT content FROM doc_chunks WHERE doc_id = :doc_id ORDER BY chunk_index"
                ), {"doc_id": doc_id}).scalars().all()
                if chunks:
                    conn.execute(text(
                        "UPDATE documents SET content_text = :content WHERE id = :doc_id"
                    ), {"content": "\n\n".join(chunks), "doc_id": doc_id})
        _ensure_fts(conn)


def _ensure_fts(conn_or_sess) -> None:
    conn_or_sess.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5("
        "content, title UNINDEXED, doc_id UNINDEXED, chunk_id UNINDEXED, "
        "session_id UNINDEXED, tokenize = 'unicode61')"
    ))
    conn_or_sess.execute(text(
        "DELETE FROM doc_chunks_fts WHERE doc_id NOT IN (SELECT id FROM documents)"
    ))


def _delete_fts_for_doc(db: DbSession, doc_id: int) -> None:
    _ensure_fts(db)
    db.execute(text("DELETE FROM doc_chunks_fts WHERE doc_id = :doc_id"), {"doc_id": doc_id})


def _insert_fts_row(db: DbSession, doc: "Document", chunk: "DocChunk") -> None:
    _ensure_fts(db)
    db.execute(text(
        "INSERT INTO doc_chunks_fts(content, title, doc_id, chunk_id, session_id) "
        "VALUES (:content, :title, :doc_id, :chunk_id, :session_id)"
    ), {
        "content": _normalize_fts_text(chunk.content),
        "title": doc.title,
        "doc_id": doc.id,
        "chunk_id": chunk.id,
        "session_id": doc.session_id or "",
    })


# --- 便捷查询 -----------------------------------------------------------------

def get_session(db: DbSession, sid: str) -> Session | None:
    return db.get(Session, sid)


def list_anchors(db: DbSession, sid: str) -> list[Anchor]:
    stmt = select(Anchor).where(Anchor.session_id == sid).order_by(
        Anchor.weight.desc(), Anchor.created_at.asc()
    )
    return list(db.scalars(stmt))


def list_messages(db: DbSession, sid: str, limit: int = 50) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == sid)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def list_mastery(db: DbSession, sid: str) -> list[Mastery]:
    stmt = select(Mastery).where(Mastery.session_id == sid).order_by(Mastery.level.desc())
    return list(db.scalars(stmt))


def list_due_reviews(db: DbSession, sid: str, now: datetime) -> list[Mastery]:
    stmt = (
        select(Mastery)
        .where(
            Mastery.session_id == sid,
            Mastery.next_review_at.is_not(None),
            Mastery.next_review_at <= now,
        )
        .order_by(Mastery.next_review_at.asc(), Mastery.updated_at.asc())
    )
    return list(db.scalars(stmt))


def _document_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


# TODO(V2): replace per-char CJK split with jieba/cuttoken when 切到外置分词。
# 当前实现是 unicode61 的 fallback：在每个 CJK 字符两侧加空格，让默认分词器能切。
# 切 jieba 时，本函数和 _prepare_fts_query 必须同步替换。
def _normalize_fts_text(value: str) -> str:
    return re.sub(r"([\u4e00-\u9fff])", r" \1 ", value or "")


def _prepare_fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", query or "")
    return " ".join(tokens)


def _search_doc_chunks_fts(
    db: DbSession,
    query: str,
    *,
    session_id: str | None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    _ensure_fts(db)
    fts_query = _prepare_fts_query(query)
    if not fts_query:
        return []
    sid = session_id or ""
    rows = db.execute(text(
        "SELECT c.id AS chunk_id, c.doc_id AS doc_id, d.title AS title, "
        "c.content AS content, -bm25(doc_chunks_fts) AS score "
        "FROM doc_chunks_fts "
        "JOIN doc_chunks c ON c.id = doc_chunks_fts.chunk_id "
        "JOIN documents d ON d.id = c.doc_id "
        "WHERE doc_chunks_fts MATCH :query "
        "AND (doc_chunks_fts.session_id = '' OR (:sid != '' AND doc_chunks_fts.session_id = :sid)) "
        "ORDER BY bm25(doc_chunks_fts) ASC "
        "LIMIT :limit"
    ), {"query": fts_query, "sid": sid, "limit": max(1, int(top_k))}).mappings().all()
    return [dict(r) for r in rows]


def _document_scope_filter(session_id: str | None):
    if session_id is None:
        return Document.session_id.is_(None)
    return (Document.session_id.is_(None)) | (Document.session_id == session_id)


def add_document(
    db: DbSession,
    *,
    session_id: str | None,
    title: str,
    source_type: str,
    source_uri: str = "",
    content: str,
) -> Document:
    _ensure_fts(db)
    doc_hash = _document_hash(content)
    stmt = select(Document).where(Document.session_id == session_id, Document.hash == doc_hash)
    existing = db.scalar(stmt)
    if existing is not None:
        return existing
    doc = Document(
        session_id=session_id,
        title=(title or "Untitled").strip() or "Untitled",
        source_type=source_type,
        source_uri=source_uri or "",
        hash=doc_hash,
        content_text=content or "",
    )
    db.add(doc)
    db.flush()
    _write_chunks(db, doc, content)
    return doc


def _write_chunks(db: DbSession, doc: Document, content: str) -> None:
    for idx, ch in enumerate(chunk_text(content)):
        row = DocChunk(doc_id=doc.id, chunk_index=idx, content=ch.content, token_count=ch.token_count)
        db.add(row)
        db.flush()
        _insert_fts_row(db, doc, row)


def list_documents(db: DbSession, *, session_id: str | None) -> list[Document]:
    stmt = select(Document).where(_document_scope_filter(session_id)).order_by(Document.imported_at.desc(), Document.id.desc())
    return list(db.scalars(stmt))


def get_document(db: DbSession, doc_id: int) -> Document | None:
    return db.get(Document, doc_id)


def list_doc_chunks(db: DbSession, doc_id: int) -> list[DocChunk]:
    stmt = select(DocChunk).where(DocChunk.doc_id == doc_id).order_by(DocChunk.chunk_index.asc())
    return list(db.scalars(stmt))


def resolve_cited_chunks(db: DbSession, chunk_ids: list[int]) -> list[dict]:
    """Resolve cited chunk ids to source descriptors in input order."""
    out: list[dict] = []
    for raw_id in chunk_ids or []:
        try:
            chunk_id = int(raw_id)
        except Exception:
            continue
        chunk = db.get(DocChunk, chunk_id)
        if chunk is None:
            continue
        doc = db.get(Document, int(chunk.doc_id))
        if doc is None:
            continue
        snippet = " ".join((chunk.content or "").split())
        if len(snippet) > 160:
            snippet = snippet[:157].rstrip() + "..."
        out.append({
            "chunk_id": int(chunk.id),
            "doc_id": int(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "source_uri": doc.source_uri,
            "snippet": snippet,
        })
    return out


def delete_document(db: DbSession, doc_id: int) -> bool:
    doc = get_document(db, doc_id)
    if doc is None:
        return False
    _delete_fts_for_doc(db, doc_id)
    db.query(DocChunk).filter(DocChunk.doc_id == doc_id).delete(synchronize_session=False)
    db.delete(doc)
    return True


def reindex_document(db: DbSession, doc_id: int) -> Document | None:
    doc = get_document(db, doc_id)
    if doc is None:
        return None
    _delete_fts_for_doc(db, doc_id)
    db.query(DocChunk).filter(DocChunk.doc_id == doc_id).delete(synchronize_session=False)
    db.flush()
    _write_chunks(db, doc, doc.content_text or "")
    doc.updated_at = datetime.utcnow()
    return doc


def _unlink_path(path: str | None) -> None:
    if not path:
        return
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            p.unlink()
    except OSError:
        pass


def add_image_extract(
    db: DbSession,
    sid: str,
    *,
    image_id: int,
    mime: str,
    extracted_text: str,
    structure: dict[str, Any],
    detected_kps: list[str],
    episode_id: int | None,
    original_path: str | None,
    retained_until: datetime | None,
) -> ImageExtract:
    row = ImageExtract(
        session_id=sid,
        image_id=image_id,
        mime=mime,
        extracted_text=extracted_text or "",
        structure_json=json.dumps(structure or {}, ensure_ascii=False),
        detected_kps_json=json.dumps(detected_kps or [], ensure_ascii=False),
        episode_id=episode_id,
        original_path=original_path,
        retained_until=retained_until,
    )
    db.add(row)
    return row


def list_image_extracts(db: DbSession, sid: str) -> list[ImageExtract]:
    stmt = select(ImageExtract).where(ImageExtract.session_id == sid).order_by(ImageExtract.created_at.desc(), ImageExtract.id.desc())
    return list(db.scalars(stmt))


def get_image_extract(db: DbSession, sid: str, image_id: int) -> ImageExtract | None:
    stmt = select(ImageExtract).where(ImageExtract.session_id == sid, ImageExtract.image_id == image_id)
    return db.scalar(stmt)


def remove_episode_references(db: DbSession, sid: str, episode_id: int) -> None:
    """Remove an episode id from memory records owned by this session."""
    target = int(episode_id)
    for m in list_mastery(db, sid):
        ids = [i for i in m.evidence_ids() if i != target]
        if ids != m.evidence_ids():
            m.evidence_episode_ids = json.dumps(ids, ensure_ascii=False)
    for e in list_error_logs(db, sid):
        ids = [i for i in e.linked_ids() if i != target]
        if ids != e.linked_ids():
            e.linked_episode_ids = json.dumps(ids, ensure_ascii=False)
    remove_kg_episode_references(db, sid, episode_id)


def delete_image_extract(db: DbSession, sid: str, image_id: int, *, clean_references: bool = True) -> bool:
    row = get_image_extract(db, sid, image_id)
    if row is None:
        return False
    _unlink_path(row.original_path)
    if row.episode_id is not None:
        if clean_references:
            remove_episode_references(db, sid, int(row.episode_id))
        msg = db.get(Message, row.episode_id)
        if msg is not None and msg.session_id == sid and msg.meta().get("kind") == "image_extract":
            db.delete(msg)
    db.delete(row)
    return True


def delete_session_images(db: DbSession, sid: str, *, clean_references: bool = True) -> int:
    count = 0
    for row in list(list_image_extracts(db, sid)):
        if delete_image_extract(db, sid, int(row.image_id), clean_references=clean_references):
            count += 1
    return count


def purge_expired_images(db: DbSession, now: datetime) -> int:
    stmt = select(ImageExtract).where(
        ImageExtract.retained_until.is_not(None),
        ImageExtract.retained_until <= now,
    )
    rows = list(db.scalars(stmt))
    for row in rows:
        _unlink_path(row.original_path)
        row.original_path = None
        row.retained_until = None
    return len(rows)


def _clean_error_pattern(pattern: str) -> str:
    return str(pattern or "").strip()[:12]


def list_error_logs(db: DbSession, sid: str) -> list[ErrorLog]:
    stmt = (
        select(ErrorLog)
        .where(ErrorLog.session_id == sid)
        .order_by((ErrorLog.status == "resolved").asc(), ErrorLog.recurrence_count.desc(), ErrorLog.last_seen_at.desc())
    )
    return list(db.scalars(stmt))


def get_error_log(db: DbSession, sid: str, eid: int) -> ErrorLog | None:
    stmt = select(ErrorLog).where(ErrorLog.session_id == sid, ErrorLog.id == eid)
    return db.scalar(stmt)


def upsert_error_log(
    db: DbSession,
    sid: str,
    kp: str,
    error_pattern: str,
    *,
    evidence_episode_id: int | None,
) -> ErrorLog | None:
    pattern = _clean_error_pattern(error_pattern)
    if not pattern:
        return None
    kp = (kp or "当前焦点").strip() or "当前焦点"
    now = datetime.utcnow()
    stmt = select(ErrorLog).where(
        ErrorLog.session_id == sid,
        ErrorLog.kp == kp,
        ErrorLog.error_pattern == pattern,
    )
    row = db.scalar(stmt)
    if row is None:
        row = ErrorLog(
            session_id=sid,
            kp=kp,
            error_pattern=pattern,
            first_seen_at=now,
            last_seen_at=now,
            recurrence_count=1,
            linked_episode_ids="[]",
            status="active",
        )
        db.add(row)
        db.flush()
    else:
        row.recurrence_count = int(row.recurrence_count or 0) + 1
        row.last_seen_at = now
        row.status = "active"
    ids = row.linked_ids()
    if evidence_episode_id is not None and int(evidence_episode_id) not in ids:
        ids.append(int(evidence_episode_id))
        row.linked_episode_ids = json.dumps(ids, ensure_ascii=False)
    return row


def resolve_error_log(db: DbSession, sid: str, eid: int) -> ErrorLog | None:
    row = get_error_log(db, sid, eid)
    if row is None:
        return None
    row.status = "resolved"
    row.last_seen_at = datetime.utcnow()
    return row


def resolve_error_pattern(db: DbSession, sid: str, kp: str, error_pattern: str) -> ErrorLog | None:
    pattern = _clean_error_pattern(error_pattern)
    if not pattern:
        return None
    stmt = select(ErrorLog).where(
        ErrorLog.session_id == sid,
        ErrorLog.kp == ((kp or "当前焦点").strip() or "当前焦点"),
        ErrorLog.error_pattern == pattern,
    )
    row = db.scalar(stmt)
    if row is None:
        return None
    row.status = "resolved"
    row.last_seen_at = datetime.utcnow()
    return row


_EVIDENCE_SCORES = {
    "none": 0.0,
    "explanation": 35.0,
    "retrieval": 55.0,
    "transfer": 72.0,
    "delayed_retrieval": 82.0,
    "correction": 90.0,
}


def _next_review_interval(current: int, review_frequency: str = "normal") -> int:
    ladder = [1, 2, 4, 7] if review_frequency == "high" else [1, 3, 7, 14]
    for days in ladder:
        if current < days:
            return days
    return ladder[-1]


def mastery_band(score: float) -> str:
    score = float(score or 0.0)
    if score < 10:
        return "未接触"
    if score < 30:
        return "有直观入口"
    if score < 50:
        return "能跟着例子讲"
    if score < 70:
        return "能基础应用"
    if score < 85:
        return "能处理变式"
    return "可迁移纠错"


def upsert_mastery(
    db: DbSession,
    sid: str,
    kp: str,
    correctness: float,
    depth: float,
    *,
    evidence_type: str = "none",
    verification_status: str = "none",
    evidence_episode_id: int | None = None,
    error_type: str = "",
    updated_reason: str = "",
    review_frequency: str = "normal",
) -> Mastery:
    """Evidence-gated mastery update.

    A user saying "懂了" is not evidence. Score increases only when a turn
    supplies passed/partial evidence such as explanation, retrieval, transfer,
    delayed retrieval, or correction.
    """
    stmt = select(Mastery).where(
        Mastery.session_id == sid, Mastery.knowledge_point == kp
    )
    m = db.scalar(stmt)
    if m is None:
        m = Mastery(session_id=sid, knowledge_point=kp)
        db.add(m)
        db.flush()

    evidence_type = evidence_type if evidence_type in _EVIDENCE_SCORES else "none"
    verification_status = verification_status or "none"
    old_score = float(m.mastery_score or (m.level or 0.0) * 100)

    m.attempts = (m.attempts or 0) + 1
    m.last_correctness = correctness
    m.last_depth = depth
    m.last_evidence_type = evidence_type
    m.last_verification_status = verification_status
    m.updated_reason = updated_reason or ""

    ids = m.evidence_ids()
    if evidence_episode_id is not None and int(evidence_episode_id) not in ids:
        ids.append(int(evidence_episode_id))
        m.evidence_episode_ids = json.dumps(ids, ensure_ascii=False)

    if error_type:
        m.error_type = error_type

    if evidence_type != "none" and verification_status in {"passed", "partial"}:
        alpha = 0.35
        target = _EVIDENCE_SCORES[evidence_type]
        if verification_status == "partial":
            target *= 0.75
        score = (1 - alpha) * old_score + alpha * target
        m.mastery_score = round(max(0.0, min(100.0, score)), 2)
        m.review_interval = _next_review_interval(int(m.review_interval or 0), review_frequency)
        m.next_review_at = datetime.utcnow() + timedelta(days=m.review_interval)
    elif verification_status == "failed":
        # Failed verification is evidence, but not evidence for progress.
        rollback = 8.0 if old_score > 50 else 0.0
        m.mastery_score = round(max(0.0, old_score - rollback), 2)
        m.review_interval = 1
        m.next_review_at = datetime.utcnow() + timedelta(days=1)
    else:
        m.mastery_score = round(max(0.0, min(100.0, old_score)), 2)

    m.level = round((m.mastery_score or 0.0) / 100.0, 4)
    return m


def add_anchor(
    db: DbSession, sid: str, kind: str, content: str, weight: float = 1.0
) -> Anchor:
    a = Anchor(session_id=sid, kind=kind, content=content, weight=weight)
    db.add(a)
    return a


def add_message(
    db: DbSession,
    sid: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> Message:
    m = Message(
        session_id=sid,
        role=role,
        content=content,
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(m)
    return m


def delete_anchor(db: DbSession, sid: str, anchor_id: int) -> bool:
    row = db.get(Anchor, anchor_id)
    if row is None or row.session_id != sid:
        return False
    db.delete(row)
    return True


def delete_mastery_entry(db: DbSession, sid: str, mastery_id: int) -> bool:
    row = db.get(Mastery, mastery_id)
    if row is None or row.session_id != sid:
        return False
    db.delete(row)
    return True


def delete_episode_message(db: DbSession, sid: str, message_id: int) -> bool:
    row = db.get(Message, message_id)
    if row is None or row.session_id != sid:
        return False
    remove_episode_references(db, sid, int(message_id))
    db.delete(row)
    return True


def add_episode(
    db: DbSession,
    sid: str,
    *,
    kind: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> Message:
    """Append-only episode wrapper.

    V1 stores episodes in messages with role=system and meta.kind. The wrapper
    keeps the boundary explicit so the storage can move to a dedicated table
    later without changing call sites.
    """
    payload = dict(meta or {})
    payload["kind"] = kind
    return add_message(db, sid, "system", content, meta=payload)


def upsert_kg_node(
    db: DbSession,
    sid: str,
    kind: str,
    name: str,
    *,
    properties: dict[str, Any] | None = None,
    episode_id: int | None = None,
) -> KGNode | None:
    """Create or update a knowledge-graph node unique by session/kind/name."""
    name = (name or "").strip() or "未命名"
    kind = (kind or "concept").strip()
    if not is_semantic_kg_node(kind, name):
        return None
    stmt = select(KGNode).where(
        KGNode.session_id == sid,
        KGNode.kind == kind,
        KGNode.name == name,
    )
    row = db.scalar(stmt)
    now = datetime.utcnow()
    if row is None:
        row = KGNode(
            session_id=sid,
            kind=kind,
            name=name,
            properties_json=json.dumps(properties or {}, ensure_ascii=False),
            source_episode_ids="[]",
            first_seen_at=now,
            last_seen_at=now,
            status="active",
        )
        db.add(row)
        db.flush()
    else:
        row.last_seen_at = now
        if row.status == "invalidated":
            row.status = "active"
        if properties:
            old = row.properties()
            old.update(properties)
            row.properties_json = json.dumps(old, ensure_ascii=False)
        db.flush()
    if episode_id is not None:
        ids = row.episode_ids()
        if int(episode_id) not in ids:
            ids.append(int(episode_id))
            row.source_episode_ids = json.dumps(ids, ensure_ascii=False)
    return row


def get_kg_node(db: DbSession, sid: str, node_id: int) -> KGNode | None:
    stmt = select(KGNode).where(KGNode.session_id == sid, KGNode.id == node_id)
    return db.scalar(stmt)


def find_kg_node(db: DbSession, sid: str, kind: str, name: str) -> KGNode | None:
    stmt = select(KGNode).where(
        KGNode.session_id == sid,
        KGNode.kind == kind,
        KGNode.name == name,
    )
    return db.scalar(stmt)


def list_kg_nodes(
    db: DbSession,
    sid: str,
    *,
    kind: str | None = None,
    status: str = "active",
) -> list[KGNode]:
    stmt = select(KGNode).where(KGNode.session_id == sid)
    if kind:
        stmt = stmt.where(KGNode.kind == kind)
    if status:
        stmt = stmt.where(KGNode.status == status)
    stmt = stmt.order_by(KGNode.last_seen_at.desc())
    return [n for n in db.scalars(stmt) if is_semantic_kg_node(n.kind, n.name)]


def invalidate_kg_node(db: DbSession, sid: str, node_id: int) -> KGNode | None:
    row = get_kg_node(db, sid, node_id)
    if row is None:
        return None
    row.status = "invalidated"
    row.last_seen_at = datetime.utcnow()
    db.flush()
    return row


def upsert_kg_edge(
    db: DbSession,
    sid: str,
    source_id: int,
    target_id: int,
    relation: str,
    *,
    weight: float = 1.0,
    properties: dict[str, Any] | None = None,
    episode_id: int | None = None,
) -> KGEdge:
    """Create or update an active edge for source/target/relation."""
    relation = (relation or "").strip() or "related"
    stmt = select(KGEdge).where(
        KGEdge.session_id == sid,
        KGEdge.source_id == source_id,
        KGEdge.target_id == target_id,
        KGEdge.relation == relation,
        KGEdge.status == "active",
    )
    row = db.scalar(stmt)
    now = datetime.utcnow()
    if row is None:
        row = KGEdge(
            session_id=sid,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            properties_json=json.dumps(properties or {}, ensure_ascii=False),
            source_episode_ids="[]",
            valid_from=now,
            status="active",
        )
        db.add(row)
        db.flush()
    else:
        row.weight = weight
        if properties:
            old = row.properties()
            old.update(properties)
            row.properties_json = json.dumps(old, ensure_ascii=False)
    if episode_id is not None:
        ids = row.episode_ids()
        if int(episode_id) not in ids:
            ids.append(int(episode_id))
            row.source_episode_ids = json.dumps(ids, ensure_ascii=False)
    return row


def get_kg_edge(db: DbSession, sid: str, edge_id: int) -> KGEdge | None:
    stmt = select(KGEdge).where(KGEdge.session_id == sid, KGEdge.id == edge_id)
    return db.scalar(stmt)


def list_kg_edges(
    db: DbSession,
    sid: str,
    *,
    node_id: int | None = None,
    relation: str | None = None,
    status: str = "active",
) -> list[KGEdge]:
    """List graph edges. node_id matches either source or target."""
    stmt = select(KGEdge).where(KGEdge.session_id == sid)
    if node_id is not None:
        stmt = stmt.where((KGEdge.source_id == node_id) | (KGEdge.target_id == node_id))
    if relation:
        stmt = stmt.where(KGEdge.relation == relation)
    if status:
        stmt = stmt.where(KGEdge.status == status)
    stmt = stmt.order_by(KGEdge.valid_from.desc())
    return list(db.scalars(stmt))


def invalidate_kg_edge(db: DbSession, sid: str, edge_id: int) -> KGEdge | None:
    row = get_kg_edge(db, sid, edge_id)
    if row is None:
        return None
    row.status = "invalidated"
    row.invalidated_at = datetime.utcnow()
    db.flush()
    return row


def supersede_kg_edge(
    db: DbSession,
    sid: str,
    source_id: int,
    target_id: int,
    relation: str,
    *,
    new_weight: float = 1.0,
    new_properties: dict[str, Any] | None = None,
    episode_id: int | None = None,
) -> KGEdge:
    """Supersede an active edge with new evidence and create a replacement."""
    now = datetime.utcnow()
    stmt = select(KGEdge).where(
        KGEdge.session_id == sid,
        KGEdge.source_id == source_id,
        KGEdge.target_id == target_id,
        KGEdge.relation == relation,
        KGEdge.status == "active",
    )
    old = db.scalar(stmt)
    if old is not None:
        old.status = "superseded"
        old.invalidated_at = now
    new_edge = KGEdge(
        session_id=sid,
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        weight=new_weight,
        properties_json=json.dumps(new_properties or {}, ensure_ascii=False),
        source_episode_ids=json.dumps([episode_id] if episode_id else [], ensure_ascii=False),
        valid_from=now,
        status="active",
    )
    db.add(new_edge)
    db.flush()
    return new_edge


def remove_kg_episode_references(db: DbSession, sid: str, episode_id: int) -> None:
    """Remove an episode id from all graph nodes and edges owned by this session."""
    target = int(episode_id)
    for n in db.scalars(select(KGNode).where(KGNode.session_id == sid)):
        ids = n.episode_ids()
        if target in ids:
            ids.remove(target)
            n.source_episode_ids = json.dumps(ids, ensure_ascii=False)
    for e in db.scalars(select(KGEdge).where(KGEdge.session_id == sid)):
        ids = e.episode_ids()
        if target in ids:
            ids.remove(target)
            e.source_episode_ids = json.dumps(ids, ensure_ascii=False)


def delete_session(db_sess: DbSession, sid: str) -> bool:
    """级联删除会话及其所有 anchors / messages / mastery / bindings。"""
    s = db_sess.get(Session, sid)
    if s is None:
        return False
    db_sess.query(Message).filter(Message.session_id == sid).delete(synchronize_session=False)
    delete_session_images(db_sess, sid, clean_references=False)
    db_sess.query(Anchor).filter(Anchor.session_id == sid).delete(synchronize_session=False)
    db_sess.query(Mastery).filter(Mastery.session_id == sid).delete(synchronize_session=False)
    db_sess.query(ErrorLog).filter(ErrorLog.session_id == sid).delete(synchronize_session=False)
    db_sess.query(GoalState).filter(GoalState.session_id == sid).delete(synchronize_session=False)
    db_sess.query(CompanionState).filter(CompanionState.session_id == sid).delete(synchronize_session=False)
    db_sess.query(Binding).filter(Binding.session_id == sid).delete(synchronize_session=False)
    for doc in list(db_sess.scalars(select(Document).where(Document.session_id == sid))):
        delete_document(db_sess, doc.id)
    db_sess.query(KGEdge).filter(KGEdge.session_id == sid).delete(synchronize_session=False)
    db_sess.query(KGNode).filter(KGNode.session_id == sid).delete(synchronize_session=False)
    db_sess.delete(s)
    db_sess.commit()
    return True


# --- Binding helpers ---------------------------------------------------------

def get_binding(db_sess: DbSession, platform: str, external_id: str) -> "Binding | None":
    stmt = select(Binding).where(
        Binding.platform == platform, Binding.external_id == external_id
    )
    return db_sess.scalar(stmt)


def create_binding(
    db_sess: DbSession, platform: str, external_id: str,
    onboarding_state: str = "asking_role",
) -> "Binding":
    b = Binding(
        platform=platform, external_id=external_id,
        onboarding_state=onboarding_state, onboarding_data="{}",
    )
    db_sess.add(b)
    db_sess.commit()
    db_sess.refresh(b)
    return b


_UNSET: Any = object()


def update_binding(
    db_sess: DbSession, binding: "Binding",
    *, session_id: Any = _UNSET,
    onboarding_state: Any = _UNSET,
    onboarding_data: Any = _UNSET,
) -> "Binding":
    """更新 binding 字段；用 sentinel 区分 "未提供" vs "显式置空"。"""
    if session_id is not _UNSET:
        binding.session_id = session_id
    if onboarding_state is not _UNSET:
        binding.onboarding_state = onboarding_state
    if onboarding_data is not _UNSET:
        binding.onboarding_data = json.dumps(onboarding_data or {}, ensure_ascii=False)
    db_sess.commit()
    db_sess.refresh(binding)
    return binding


def list_bindings(db_sess: DbSession) -> list["Binding"]:
    return list(db_sess.scalars(select(Binding).order_by(Binding.updated_at.desc())))


def delete_binding(db_sess: DbSession, bid: int) -> bool:
    b = db_sess.get(Binding, bid)
    if b is None:
        return False
    db_sess.delete(b)
    db_sess.commit()
    return True


# --- PersonaTemplate helpers ------------------------------------------------

_BUILTIN_TEMPLATES = [
    {
        "label": "📐 高三冲刺", "role": "高三理科生", "goal": "数学一年内冲到 130 分",
        "deadline": "2026 年 6 月高考", "personality": "焦虑+好胜，会逃避难题",
        "reqs": ["重点突破函数、导数、解析几何", "先慢后快，前期循序渐进"],
        "sort": 10,
    },
    {
        "label": "📚 考研英语", "role": "考研党", "goal": "考研英语二上 75 分",
        "deadline": "2025 年 12 月", "personality": "毅力强但词汇底子薄",
        "reqs": ["每天 30 个核心词汇", "阅读以真题为主"],
        "sort": 20,
    },
    {
        "label": "🐍 Python 编程入门", "role": "完全零基础", "goal": "3 个月能独立写 Python 小工具",
        "deadline": "3 个月内", "personality": "好奇心强但容易被报错吓到",
        "reqs": ["从语法到实战", "案例驱动"],
        "sort": 30,
    },
    {
        "label": "🗣️ 雅思口语", "role": "雅思考生", "goal": "口语稳定 7.0",
        "deadline": "3 个月内出分", "personality": "紧张内向，开口困难",
        "reqs": ["重点 part 2 长讲", "每天必须练 15 分钟"],
        "sort": 40,
    },
    {
        "label": "🎼 钢琴成人初学", "role": "30 岁初学钢琴", "goal": "一年内弹下《天空之城》",
        "deadline": "一年", "personality": "手指僵硬但有耐心",
        "reqs": ["每周必须练 4 次，每次 30 分钟"],
        "sort": 50,
    },
]


def seed_builtin_templates(db_sess: DbSession) -> int:
    """启动时调用：若数据库无任何 builtin 模板就 seed 一次。返回新增数量。"""
    existing = db_sess.scalar(
        select(PersonaTemplate).where(PersonaTemplate.builtin == 1).limit(1)
    )
    if existing is not None:
        return 0
    n = 0
    for t in _BUILTIN_TEMPLATES:
        db_sess.add(PersonaTemplate(
            label=t["label"], role=t["role"], goal=t["goal"],
            deadline=t["deadline"], personality=t["personality"],
            reqs_json=json.dumps(t["reqs"], ensure_ascii=False),
            builtin=1, sort=t["sort"],
        ))
        n += 1
    db_sess.commit()
    return n


def list_templates(db_sess: DbSession) -> list["PersonaTemplate"]:
    return list(db_sess.scalars(
        select(PersonaTemplate).order_by(PersonaTemplate.sort, PersonaTemplate.id)
    ))


def get_template(db_sess: DbSession, tid: int) -> "PersonaTemplate | None":
    return db_sess.get(PersonaTemplate, tid)


def create_template(db_sess: DbSession, **fields) -> "PersonaTemplate":
    reqs = fields.pop("reqs", None)
    if reqs is not None:
        fields["reqs_json"] = json.dumps(list(reqs), ensure_ascii=False)
    fields.setdefault("builtin", 0)
    t = PersonaTemplate(**fields)
    db_sess.add(t); db_sess.commit(); db_sess.refresh(t)
    return t


def update_template(db_sess: DbSession, t: "PersonaTemplate", **fields) -> "PersonaTemplate":
    reqs = fields.pop("reqs", None)
    if reqs is not None:
        t.reqs_json = json.dumps(list(reqs), ensure_ascii=False)
    for k, v in fields.items():
        if hasattr(t, k):
            setattr(t, k, v)
    db_sess.commit(); db_sess.refresh(t)
    return t


def delete_template(db_sess: DbSession, tid: int) -> bool:
    t = db_sess.get(PersonaTemplate, tid)
    if t is None:
        return False
    if t.builtin:
        # 内置模板不允许删除，但允许"隐藏"——这里用 sort=9999 的约定
        # MVP 阶段直接拒绝删除
        return False
    db_sess.delete(t); db_sess.commit()
    return True
