"""Provider selection. Swapping a model is an .env change, not a code change."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.assistant.providers.base import (
    KNOWN_EMBEDDING_DIMS,
    EmbeddingProvider,
    LLMProvider,
)
from apps.assistant.providers.embeddings import (
    FakeEmbeddings,
    GeminiEmbeddings,
    OpenAICompatibleEmbeddings,
    SentenceTransformersEmbeddings,
)
from apps.assistant.providers.http import ProviderError
from apps.assistant.providers.llm import (
    AnthropicLLM,
    FakeLLM,
    GeminiLLM,
    OpenAICompatibleLLM,
)

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "ProviderError",
    "get_embedding_provider",
    "get_llm_provider",
    "embedding_provider_info",
    "llm_provider_info",
    "check_provider_config",
]


def get_embedding_provider() -> EmbeddingProvider:
    name = settings.EMBEDDING_PROVIDER
    model = settings.EMBEDDING_MODEL
    dim = settings.EMBEDDING_DIM
    if name == "fake":
        return FakeEmbeddings(model=model, dim=dim)
    if name == "openai_compatible":
        return OpenAICompatibleEmbeddings(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            model=model,
            dim=dim,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        )
    if name == "gemini":
        return GeminiEmbeddings(
            api_key=settings.EMBEDDING_API_KEY,
            model=model,
            dim=dim,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        )
    if name == "sentence_transformers":
        return SentenceTransformersEmbeddings(model=model, dim=dim)
    raise ImproperlyConfigured(
        f"Unknown EMBEDDING_PROVIDER '{name}'. Use one of: fake, openai_compatible, "
        "gemini, sentence_transformers."
    )


def get_llm_provider() -> LLMProvider:
    name = settings.LLM_PROVIDER
    model = settings.LLM_MODEL
    if name == "fake":
        return FakeLLM()
    if name == "openai_compatible":
        return OpenAICompatibleLLM(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=model,
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        )
    if name == "gemini":
        return GeminiLLM(
            api_key=settings.LLM_API_KEY,
            model=model,
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        )
    if name == "anthropic":
        return AnthropicLLM(
            api_key=settings.LLM_API_KEY,
            model=model,
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.PROVIDER_TIMEOUT_SECONDS,
        )
    raise ImproperlyConfigured(
        f"Unknown LLM_PROVIDER '{name}'. Use one of: fake, openai_compatible, "
        "gemini, anthropic."
    )


def check_provider_config() -> None:
    """Fail fast when EMBEDDING_DIM contradicts the configured embedding model.

    A silent mismatch would store vectors of the wrong width and make every
    similarity score meaningless, so this runs at startup.
    """
    expected = KNOWN_EMBEDDING_DIMS.get(settings.EMBEDDING_MODEL)
    if expected is not None and expected != settings.EMBEDDING_DIM:
        raise ImproperlyConfigured(
            f"EMBEDDING_DIM={settings.EMBEDDING_DIM} but embedding model "
            f"'{settings.EMBEDDING_MODEL}' produces {expected}-dimensional vectors. "
            f"Set EMBEDDING_DIM={expected} and run 'manage.py reindex_all'."
        )
    if settings.EMBEDDING_PROVIDER in {"openai_compatible", "gemini"} and not settings.EMBEDDING_API_KEY:
        raise ImproperlyConfigured(
            f"EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER} requires EMBEDDING_API_KEY."
        )
    if settings.LLM_PROVIDER in {"openai_compatible", "gemini", "anthropic"} and not settings.LLM_API_KEY:
        raise ImproperlyConfigured(f"LLM_PROVIDER={settings.LLM_PROVIDER} requires LLM_API_KEY.")
    if settings.VECTOR_BACKEND not in {"numpy", "pgvector"}:
        raise ImproperlyConfigured(
            f"Unknown VECTOR_BACKEND '{settings.VECTOR_BACKEND}'. Use 'numpy' or 'pgvector'."
        )


def embedding_provider_info() -> dict:
    return {
        "provider": settings.EMBEDDING_PROVIDER,
        "model": settings.EMBEDDING_MODEL,
        "dim": settings.EMBEDDING_DIM,
    }


def llm_provider_info() -> dict:
    return {"provider": settings.LLM_PROVIDER, "model": settings.LLM_MODEL}
