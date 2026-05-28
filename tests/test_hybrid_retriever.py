from __future__ import annotations

import engine
import db
from retrieval import HybridRetriever


def test_title_match_boost_ranks_matching_title_first(db_sess):
    db.add_document(
        db_sess,
        session_id=None,
        title="General notes",
        source_type="txt",
        content="calculus tangent slope method appears in this body. " * 8,
    )
    title_doc = db.add_document(
        db_sess,
        session_id=None,
        title="Calculus method guide",
        source_type="txt",
        content="calculus tangent slope method appears in this body with a title boost. " * 8,
    )
    db_sess.commit()

    hits = HybridRetriever(db_sess).search("calculus", session_id=None, top_k=2)

    assert hits
    assert hits[0].doc_id == title_doc.id
    assert hits[0].title == "Calculus method guide"


def test_per_doc_cap_prevents_one_document_from_dominating(db_sess):
    content = "\n\n".join(
        f"dominant keyword paragraph {i} has enough surrounding text to become its own chunk. " * 3
        for i in range(5)
    )
    doc = db.add_document(
        db_sess,
        session_id=None,
        title="Dominant keyword",
        source_type="txt",
        content=content,
    )
    db_sess.commit()

    hits = HybridRetriever(db_sess, per_doc=2).search("dominant keyword", session_id=None, top_k=5)

    assert len([h for h in hits if h.doc_id == doc.id]) <= 2


def test_empty_query_returns_no_hits(db_sess):
    db.add_document(
        db_sess,
        session_id=None,
        title="Anything",
        source_type="txt",
        content="calculus content " * 10,
    )
    db_sess.commit()

    assert HybridRetriever(db_sess).search("   ", session_id=None, top_k=3) == []


def test_session_scope_includes_global_and_current_private_only(db_sess):
    current = engine.create_session(db_sess, title="", role="student", goal="goal")
    other = engine.create_session(db_sess, title="", role="student", goal="goal")
    global_doc = db.add_document(
        db_sess,
        session_id=None,
        title="Global calculus",
        source_type="txt",
        content="sharedscope calculus global material " * 10,
    )
    current_doc = db.add_document(
        db_sess,
        session_id=current.id,
        title="Current calculus",
        source_type="txt",
        content="sharedscope calculus current private material " * 10,
    )
    other_doc = db.add_document(
        db_sess,
        session_id=other.id,
        title="Other calculus",
        source_type="txt",
        content="sharedscope calculus other private material " * 10,
    )
    db_sess.commit()

    doc_ids = {
        h.doc_id
        for h in HybridRetriever(db_sess).search("sharedscope calculus", session_id=current.id, top_k=10)
    }

    assert global_doc.id in doc_ids
    assert current_doc.id in doc_ids
    assert other_doc.id not in doc_ids
