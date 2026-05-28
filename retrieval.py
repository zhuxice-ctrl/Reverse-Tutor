from __future__ import annotations

import re
from typing import NamedTuple, Protocol

import db


class Hit(NamedTuple):
    chunk_id: int
    doc_id: int
    title: str
    content: str
    score: float


class Retriever(Protocol):
    def search(self, query: str, *, session_id: str | None, top_k: int = 3) -> list[Hit]: ...


class FTSRetriever:
    def __init__(self, db_session):
        self.db = db_session

    def search(self, query: str, *, session_id: str | None, top_k: int = 3) -> list[Hit]:
        rows = db._search_doc_chunks_fts(self.db, query, session_id=session_id, top_k=top_k)
        return [
            Hit(
                chunk_id=int(row["chunk_id"]),
                doc_id=int(row["doc_id"]),
                title=str(row["title"]),
                content=str(row["content"]),
                score=float(row["score"]),
            )
            for row in rows
        ]


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _title_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in (query or "").lower().split():
        term = raw.strip()
        if not term:
            continue
        if len(term) < 2 and not _CJK_RE.search(term):
            continue
        if term not in seen:
            terms.append(term)
            seen.add(term)
    return terms


class HybridRetriever:
    """FTS content search + title-term boost + per-doc diversity."""

    TITLE_BOOST = 2.0

    def __init__(self, db_session, *, per_doc: int = 2):
        self.db = db_session
        self.per_doc = max(1, int(per_doc or 1))

    def search(self, query: str, *, session_id: str | None, top_k: int = 3) -> list[Hit]:
        if not (query or "").strip():
            return []
        limit = max(1, int(top_k or 1))
        rows = db._search_doc_chunks_fts(
            self.db,
            query,
            session_id=session_id,
            top_k=max(12, limit * 4),
        )
        if not rows:
            return []

        terms = _title_query_terms(query)
        total_terms = max(1, len(terms))
        hits: list[Hit] = []
        for row in rows:
            title = str(row["title"])
            title_lower = title.lower()
            matched = sum(1 for term in terms if term in title_lower)
            title_boost = self.TITLE_BOOST * (matched / total_terms)
            hits.append(
                Hit(
                    chunk_id=int(row["chunk_id"]),
                    doc_id=int(row["doc_id"]),
                    title=title,
                    content=str(row["content"]),
                    score=float(row["score"]) + title_boost,
                )
            )

        out: list[Hit] = []
        per_doc_counts: dict[int, int] = {}
        for hit in sorted(hits, key=lambda h: h.score, reverse=True):
            count = per_doc_counts.get(hit.doc_id, 0)
            if count >= self.per_doc:
                continue
            out.append(hit)
            per_doc_counts[hit.doc_id] = count + 1
            if len(out) >= limit:
                break
        return out


def make_default_retriever(db_session) -> Retriever:
    return HybridRetriever(db_session)
