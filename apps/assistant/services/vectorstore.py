"""Vector search backends.

In both backends the machine filter is part of the database query, never a
post-filter in Python: that is what makes machine isolation a property of the
system rather than of the prompt.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from django.conf import settings
from django.db import connection

from apps.manuals.models import Chunk, Manual


class VectorStore(Protocol):
    name: str

    def search(
        self, machine_id: int, query_embedding: list[float], limit: int
    ) -> list[tuple[int, float]]:
        """Return (chunk_id, cosine_similarity) for one machine, best first."""


class NumpyVectorStore:
    """Machine-prefiltered cosine search. Default backend: no DB extension needed."""

    name = "numpy"

    def search(
        self, machine_id: int, query_embedding: list[float], limit: int
    ) -> list[tuple[int, float]]:
        rows = list(
            Chunk.objects.filter(
                machine_id=machine_id,
                manual__is_active=True,
                manual__status=Manual.STATUS_INDEXED,
            ).values_list("id", "embedding")
        )
        if not rows:
            return []
        expected = settings.EMBEDDING_DIM
        wrong = [chunk_id for chunk_id, vector in rows if len(vector) != expected]
        if wrong:
            raise RuntimeError(
                f"{len(wrong)} stored chunk(s) do not have EMBEDDING_DIM={expected} "
                "dimensions. The embedding model changed; run 'manage.py reindex_all'."
            )
        ids = [chunk_id for chunk_id, _ in rows]
        matrix = np.asarray([vector for _, vector in rows], dtype=np.float32)
        query = np.asarray(query_embedding, dtype=np.float32)
        # Both sides are L2-normalised, so the dot product is the cosine similarity.
        scores = matrix @ query
        best = np.argsort(-scores)[:limit]
        return [(ids[index], float(scores[index])) for index in best]


class PgVectorStore:
    """Optional backend using the pgvector extension's cosine distance operator."""

    name = "pgvector"

    def search(
        self, machine_id: int, query_embedding: list[float], limit: int
    ) -> list[tuple[int, float]]:
        literal = "[" + ",".join(repr(float(value)) for value in query_embedding) + "]"
        chunk_table = Chunk._meta.db_table
        manual_table = Manual._meta.db_table
        # TODO-OPT: add an HNSW index on (embedding::vector) to avoid the full scan.
        sql = f"""
            SELECT c.id, 1 - (c.embedding::vector <=> %s::vector) AS score
            FROM {chunk_table} AS c
            JOIN {manual_table} AS m ON m.id = c.manual_id
            WHERE c.machine_id = %s AND m.is_active AND m.status = %s
            ORDER BY c.embedding::vector <=> %s::vector
            LIMIT %s
        """
        with connection.cursor() as cursor:
            cursor.execute(
                sql, [literal, machine_id, Manual.STATUS_INDEXED, literal, limit]
            )
            return [(row[0], float(row[1])) for row in cursor.fetchall()]


def get_vector_store() -> VectorStore:
    if settings.VECTOR_BACKEND == "pgvector":
        return PgVectorStore()
    return NumpyVectorStore()
