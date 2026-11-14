"""Postgres + pgvector store: one table for all strategies, cosine search."""
from __future__ import annotations

import json
from typing import Any

import psycopg

from .models import Chunk


_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    strategy       TEXT        NOT NULL,
    chunk_id       TEXT        NOT NULL,
    document_id    TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    page           INT         NOT NULL,
    text           TEXT        NOT NULL,
    article        INT,
    chapter_roman  TEXT,
    metadata       JSONB       NOT NULL,
    embedding      VECTOR(%(dim)s) NOT NULL,
    PRIMARY KEY (strategy, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_strategy
    ON chunks (strategy);
CREATE INDEX IF NOT EXISTS idx_chunks_strategy_article
    ON chunks (strategy, article);
CREATE INDEX IF NOT EXISTS idx_chunks_strategy_chapter
    ON chunks (strategy, chapter_roman);
"""


_ALLOWED_FILTERS = {"article": "int", "chapter_roman": "text"}


def _vec_literal(vector: list[float]) -> str:
    """Render a Python list as pgvector's text literal '[v1,v2,...]'."""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url)

    def create_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL % {"dim": self.dimensions})
            conn.commit()

    def server_info(self) -> dict[str, str]:
        """PostgreSQL + pgvector versions, for the run manifest."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SHOW server_version")
            pg_version = cur.fetchone()[0]
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = cur.fetchone()
        return {"postgres": pg_version, "pgvector": row[0] if row else "missing"}

    def count(self, strategy: str) -> dict[str, int]:
        """Row count and distinct chunk_id count for one strategy."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COUNT(DISTINCT chunk_id) FROM chunks WHERE strategy = %s",
                (strategy,),
            )
            rows, distinct_ids = cur.fetchone()
        return {"rows": int(rows), "distinct_chunk_ids": int(distinct_ids)}

    def delete_strategy(self, strategy: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE strategy = %s", (strategy,))
            conn.commit()

    def upsert(
        self,
        strategy: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) must align"
            )
        if not chunks:
            return
        for i, v in enumerate(vectors):
            if len(v) != self.dimensions:
                raise ValueError(
                    f"vector[{i}] has {len(v)} dims, expected {self.dimensions}"
                )

        document_ids = {c.document_id for c in chunks}
        rows = []
        for chunk, vector in zip(chunks, vectors):
            meta = chunk.metadata or {}
            rows.append(
                (
                    strategy,
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.source,
                    chunk.page,
                    chunk.text,
                    meta.get("article"),
                    meta.get("chapter_roman") or None,
                    json.dumps(meta, ensure_ascii=False),
                    _vec_literal(vector),
                )
            )

        insert_sql = """
            INSERT INTO chunks (
                strategy, chunk_id, document_id, source, page, text,
                article, chapter_roman, metadata, embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
        """

        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "DELETE FROM chunks WHERE strategy = %s AND document_id = %s",
                [(strategy, doc_id) for doc_id in document_ids],
            )
            cur.executemany(insert_sql, rows)
            conn.commit()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"query_vector has {len(query_vector)} dims, expected {self.dimensions}"
            )
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        filters = filters or {}
        unknown = set(filters) - _ALLOWED_FILTERS.keys()
        if unknown:
            raise ValueError(f"unsupported filter keys: {sorted(unknown)}")

        clauses = ["strategy = %s"]
        params: list[Any] = [strategy]
        for key, cast in _ALLOWED_FILTERS.items():
            value = filters.get(key)
            if value is None:
                continue
            clauses.append(f"{key} = %s::{cast}")
            params.append(value)

        qvec_literal = _vec_literal(query_vector)
        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT chunk_id, document_id, source, page, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        exec_params = [qvec_literal, *params, qvec_literal, top_k]

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, exec_params)
            fetched = cur.fetchall()

        results = []
        for chunk_id, document_id, source, page, text, metadata, score in fetched:
            results.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "source": source,
                    "page": page,
                    "text": text,
                    "metadata": metadata,
                    "score": float(score),
                }
            )
        return results
