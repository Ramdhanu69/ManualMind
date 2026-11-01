"""Provider interfaces and the embedding-dimension contract."""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

KNOWN_EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "nomic-embed-text": 768,
    "text-embedding-004": 768,
    "gemini-embedding-001": 3072,
    "bge-small-en-v1.5": 384,
    "BAAI/bge-small-en-v1.5": 384,
    "text-embedding-bge-small-en-v1.5": 384,
    "all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def generate_json(self, system: str, user: str, schema: dict) -> dict: ...


def l2_normalize(vector: list[float]) -> list[float]:
    """Scale to unit length so cosine similarity is a plain dot product.

    Providers normalise before returning, which keeps the stored vectors and the
    query vector on the same scale no matter which backend scores them.
    """
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]
