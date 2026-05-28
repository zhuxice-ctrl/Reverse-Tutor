from __future__ import annotations

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
