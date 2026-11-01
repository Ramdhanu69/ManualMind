"""Embedding providers. All of them return L2-normalised vectors."""

from __future__ import annotations

import hashlib
import re

from apps.assistant.providers.base import l2_normalize
from apps.assistant.providers.http import ProviderError, post_json

_TOKENS = re.compile(r"[a-z0-9][a-z0-9.\-]*")
_BATCH_SIZE = 32


class OpenAICompatibleEmbeddings:
    """Covers OpenAI, Azure-style gateways, Ollama /v1 and LM Studio."""

    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, dim: int, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.timeout = timeout

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            body = post_json(
                f"{self.base_url}/embeddings",
                {"model": self.model, "input": batch},
                {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                self.timeout,
                f"Embedding provider '{self.model}'",
            )
            try:
                rows = sorted(body["data"], key=lambda row: row.get("index", 0))
                vectors.extend(row["embedding"] for row in rows)
            except (KeyError, TypeError) as exc:
                raise ProviderError(
                    f"Embedding provider '{self.model}' returned an unexpected payload"
                ) from exc
        return [l2_normalize(vector) for vector in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


class GeminiEmbeddings:
    name = "gemini"

    def __init__(self, api_key: str, model: str, dim: int, timeout: int):
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.timeout = timeout

    def _embed_one(self, text: str) -> list[float]:
        body = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent",
            {"content": {"parts": [{"text": text}]}},
            {"x-goog-api-key": self.api_key},
            self.timeout,
            f"Gemini embeddings '{self.model}'",
        )
        try:
            return l2_normalize(body["embedding"]["values"])
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                f"Gemini embeddings '{self.model}' returned an unexpected payload"
            ) from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


class SentenceTransformersEmbeddings:
    """Local embeddings, e.g. BAAI/bge-small-en-v1.5 (384 dimensions)."""

    name = "sentence_transformers"

    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim
        self._encoder = None

    def _load(self):
        if self._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ProviderError(
                    "EMBEDDING_PROVIDER=sentence_transformers requires the optional "
                    "'sentence-transformers' package. Install it or choose another provider."
                ) from exc
            self._encoder = SentenceTransformer(self.model)
        return self._encoder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        encoded = self._load().encode(texts, batch_size=_BATCH_SIZE)
        return [l2_normalize([float(value) for value in row]) for row in encoded]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FakeEmbeddings:
    """Deterministic hashed bag-of-words, so tests and the eval run without keys.

    Token hashing (rather than hashing the whole string) is deliberate: cosine
    similarity then reflects real lexical overlap, which lets the retrieval score
    gate be exercised without a network call.
    """

    name = "fake"

    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKENS.findall(text.lower()):
            bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
            vector[bucket % self.dim] += 1.0
        return l2_normalize(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
