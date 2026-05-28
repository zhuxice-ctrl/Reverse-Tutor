from __future__ import annotations

from sqlalchemy import func, select, text
import httpx
import pytest

import db
import engine
from server import app
from retrieval import FTSRetriever


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _fts_count(db_sess, doc_id: int) -> int:
    return int(db_sess.execute(
        text("SELECT count(*) FROM doc_chunks_fts WHERE doc_id = :doc_id"),
        {"doc_id": doc_id},
    ).scalar() or 0)


def _chunk_count(db_sess, doc_id: int) -> int:
    return int(db_sess.scalar(select(func.count(db.DocChunk.id)).where(db.DocChunk.doc_id == doc_id)) or 0)


def test_import_md_creates_chunks_and_fts_rows(db_sess):
    doc = db.add_document(
        db_sess,
        session_id=None,
        title="极值点偏移导引",
        source_type="md",
        source_uri="local.md",
        content="# 极值点偏移\n\n先看普通方法为什么卡住。然后构造对称差值。" * 8,
    )
    db_sess.commit()

    docs = db.list_documents(db_sess, session_id=None)

    assert [d.id for d in docs] == [doc.id]
    assert _chunk_count(db_sess, doc.id) > 0
    assert _fts_count(db_sess, doc.id) == _chunk_count(db_sess, doc.id)


def test_keyword_search_ranks_relevant_chunk_first(db_sess):
    doc = db.add_document(
        db_sess,
        session_id=None,
        title="函数方法笔记",
        source_type="md",
        source_uri="",
        content=(
            "极值点偏移的关键是先比较左右两侧导数，再观察对称差值。" * 6
            + "\n\n"
            + "概率统计这里讨论抽样分布和方差估计。" * 6
        ),
    )
    db_sess.commit()

    hits = FTSRetriever(db_sess).search("极值点偏移 对称差值", session_id=None, top_k=1)

    assert hits
    assert hits[0].doc_id == doc.id
    assert "极值点偏移" in hits[0].content


def test_session_scope_isolation(db_sess):
    a = engine.create_session(db_sess, title="", role="A", goal="g")
    b = engine.create_session(db_sess, title="", role="B", goal="g")
    db.add_document(db_sess, session_id=None, title="公共", source_type="txt", source_uri="", content="公共资料：极值点偏移公共方法。" * 8)
    db.add_document(db_sess, session_id=a.id, title="A私有", source_type="txt", source_uri="", content="A资料：极值点偏移私有线索。" * 8)
    db.add_document(db_sess, session_id=b.id, title="B私有", source_type="txt", source_uri="", content="B资料：极值点偏移私有线索。" * 8)
    db_sess.commit()

    titles = {h.title for h in FTSRetriever(db_sess).search("极值点偏移", session_id=a.id, top_k=10)}

    assert {"公共", "A私有"} <= titles
    assert "B私有" not in titles


def test_delete_document_cascades_chunks_and_fts(db_sess):
    doc = db.add_document(db_sess, session_id=None, title="待删", source_type="txt", source_uri="", content="极值点偏移删除测试。" * 10)
    db_sess.commit()

    assert db.delete_document(db_sess, doc.id) is True
    db_sess.commit()

    assert _chunk_count(db_sess, doc.id) == 0
    assert _fts_count(db_sess, doc.id) == 0


def test_reindex_is_idempotent(db_sess):
    doc = db.add_document(db_sess, session_id=None, title="重建", source_type="md", source_uri="", content="极值点偏移重建测试。" * 20)
    db_sess.commit()
    before = {c.content for c in db.list_doc_chunks(db_sess, doc.id)}

    db.reindex_document(db_sess, doc.id)
    db.reindex_document(db_sess, doc.id)
    db_sess.commit()
    after = {c.content for c in db.list_doc_chunks(db_sess, doc.id)}

    assert after == before
    assert _fts_count(db_sess, doc.id) == _chunk_count(db_sess, doc.id)


def test_reindex_uses_original_content(db_sess):
    content = (
        "Intro paragraph keeps its own spacing.\n\n\n"
        "Second paragraph has a short line.\n\n"
        + ("Sentence one keeps punctuation. Sentence two follows. " * 30)
    )
    doc = db.add_document(
        db_sess,
        session_id=None,
        title="original",
        source_type="md",
        source_uri="",
        content=content,
    )
    db_sess.commit()
    first_chunks = {c.content for c in db.list_doc_chunks(db_sess, doc.id)}

    db.reindex_document(db_sess, doc.id)
    db_sess.commit()

    assert db.get_document(db_sess, doc.id).content_text == content
    assert {c.content for c in db.list_doc_chunks(db_sess, doc.id)} == first_chunks


def test_duplicate_hash_returns_existing_record(db_sess):
    content = "同一份 markdown 内容用于去重。" * 12
    first = db.add_document(db_sess, session_id="s1", title="first", source_type="md", source_uri="", content=content)
    db_sess.commit()
    second = db.add_document(db_sess, session_id="s1", title="second", source_type="md", source_uri="", content=content)
    db_sess.commit()

    assert second.id == first.id
    assert _chunk_count(db_sess, first.id) == _fts_count(db_sess, first.id)
    assert db_sess.scalar(select(func.count(db.Document.id))) == 1


def test_delete_session_cascades_private_docs_only(db_sess):
    s = engine.create_session(db_sess, title="", role="A", goal="g")
    private = db.add_document(db_sess, session_id=s.id, title="私有", source_type="txt", source_uri="", content="私有极值点偏移。" * 10)
    global_doc = db.add_document(db_sess, session_id=None, title="全局", source_type="txt", source_uri="", content="全局极值点偏移。" * 10)
    db_sess.commit()

    assert db.delete_session(db_sess, s.id) is True

    assert db.get_document(db_sess, private.id) is None
    assert db.get_document(db_sess, global_doc.id) is not None
    assert _fts_count(db_sess, private.id) == 0
    assert _fts_count(db_sess, global_doc.id) > 0


async def test_document_http_import_list_reindex_delete(client):
    r = await client.post("/api/documents", json={
        "title": "HTTP 导入",
        "source_type": "md",
        "source_uri": "http.md",
        "content": "极值点偏移 HTTP 导入测试。" * 10,
    })
    assert r.status_code == 200
    doc_id = r.json()["id"]
    assert r.json()["chunk_count"] > 0

    rows = (await client.get("/api/documents")).json()
    assert any(d["id"] == doc_id for d in rows)
    assert (await client.post(f"/api/documents/{doc_id}/reindex")).status_code == 200
    assert (await client.delete(f"/api/documents/{doc_id}")).json()["deleted"] == doc_id
