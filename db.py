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
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, UniqueConstraint,
    create_engine, select,
)
from sqlalchemy.orm import DeclarativeBase, Session as DbSession, sessionmaker

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
    persona_json = Column(Text, nullable=False)  # {role, goal, deadline, personality, mood}
    plan_json = Column(Text, default="[]")       # 课程主线节点列表
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def persona(self) -> dict:
        return json.loads(self.persona_json)

    def plan(self) -> list:
        return json.loads(self.plan_json or "[]")


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
    level = Column(Float, default=0.0)      # 0-1
    attempts = Column(Integer, default=0)
    last_correctness = Column(Float, default=0.0)
    last_depth = Column(Float, default=0.0)
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


def init_db() -> None:
    Base.metadata.create_all(engine)


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


def upsert_mastery(
    db: DbSession,
    sid: str,
    kp: str,
    correctness: float,
    depth: float,
) -> Mastery:
    """掌握度增量更新：指数移动平均 + 试次累计。"""
    stmt = select(Mastery).where(
        Mastery.session_id == sid, Mastery.knowledge_point == kp
    )
    m = db.scalar(stmt)
    if m is None:
        m = Mastery(session_id=sid, knowledge_point=kp)
        db.add(m)
    alpha = 0.35
    m.level = round((1 - alpha) * (m.level or 0.0) + alpha * (0.5 * correctness + 0.5 * depth), 4)
    m.attempts = (m.attempts or 0) + 1
    m.last_correctness = correctness
    m.last_depth = depth
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


def delete_session(db_sess: DbSession, sid: str) -> bool:
    """级联删除会话及其所有 anchors / messages / mastery / bindings。"""
    s = db_sess.get(Session, sid)
    if s is None:
        return False
    db_sess.query(Anchor).filter(Anchor.session_id == sid).delete(synchronize_session=False)
    db_sess.query(Message).filter(Message.session_id == sid).delete(synchronize_session=False)
    db_sess.query(Mastery).filter(Mastery.session_id == sid).delete(synchronize_session=False)
    db_sess.query(Binding).filter(Binding.session_id == sid).delete(synchronize_session=False)
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
