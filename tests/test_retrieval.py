"""Machine isolation and the retrieval-score gate."""

from __future__ import annotations

import pytest
from django.test import override_settings

from apps.assistant.models import QueryLog
from apps.assistant.services import rag
from apps.assistant.services.rag import analyze_query, retrieve
from apps.assistant.services.vectorstore import NumpyVectorStore

PRESS_PAGES = [
    "HP-200 operating reference. Normal hydraulic pressure is 120 to 140 bar.",
    "Alarm codes. E17 means low hydraulic pressure below 110 bar during forming. "
    "The return filter identifier is RF-20.",
]
COMPRESSOR_PAGES = [
    "AC-90 operating reference. Normal outlet pressure is 7.0 to 8.0 bar.",
    "Alarm codes. E17 means high discharge temperature above 95 degrees C. "
    "The inlet filter identifier is AF-10.",
]


@pytest.fixture
def two_machines(press, compressor, ingest_manual):
    ingest_manual(press, "HP-OPS-01", PRESS_PAGES)
    ingest_manual(compressor, "AC-OM-01", COMPRESSOR_PAGES)
    return press, compressor


@pytest.mark.django_db
def test_retrieval_excludes_other_machine(two_machines):
    """Vector, keyword and fused results must all stay inside the selected machine.

    The second question deliberately quotes text unique to the other machine, so a
    post-filter or a prompt-only rule would leak here.
    """
    press, compressor = two_machines
    questions = [
        "What does E17 mean?",
        "high discharge temperature above 95 degrees C AF-10 inlet filter",
    ]

    for question in questions:
        for machine, other in ((press, compressor), (compressor, press)):
            analysis = analyze_query(question, machine)
            result = retrieve(analysis, machine)

            assert result.chunks, f"no chunks for {machine.machine_id} / {question}"
            assert all(chunk.machine_id == machine.pk for chunk in result.chunks)

            fused_ids = {chunk.id for chunk in result.chunks}
            vector_ids = set(result.vector_scores)
            keyword_ids = set(rag._keyword_ranking(analysis, machine))
            exact_ids = set(rag._exact_ranking(analysis, machine))

            foreign = set(
                other.chunks.values_list("id", flat=True)
            )
            assert not (fused_ids & foreign)
            assert not (vector_ids & foreign)
            assert not (keyword_ids & foreign)
            assert not (exact_ids & foreign)


@pytest.mark.django_db
def test_same_code_gives_a_different_answer_per_machine(two_machines):
    press, compressor = two_machines

    press_text = " ".join(
        chunk.text for chunk in retrieve(analyze_query("What does E17 mean?", press), press).chunks
    )
    compressor_text = " ".join(
        chunk.text
        for chunk in retrieve(analyze_query("What does E17 mean?", compressor), compressor).chunks
    )

    assert "low hydraulic pressure" in press_text
    assert "high discharge temperature" not in press_text
    assert "high discharge temperature" in compressor_text
    assert "low hydraulic pressure" not in compressor_text


@pytest.mark.django_db
def test_numpy_backend_needs_no_database_extension(two_machines, settings):
    """The default backend scores in Python, so stock Postgres is enough."""
    press, _ = two_machines
    settings.VECTOR_BACKEND = "numpy"

    from apps.assistant.providers import get_embedding_provider
    from apps.assistant.services.vectorstore import get_vector_store

    store = get_vector_store()
    assert isinstance(store, NumpyVectorStore)

    embedding = get_embedding_provider().embed_query("normal hydraulic pressure")
    hits = store.search(press.pk, embedding, 5)
    assert hits
    assert all(score <= 1.0001 for _, score in hits)


@pytest.mark.django_db
def test_low_score_retrieval_refuses_without_calling_the_llm(
    two_machines, engineer, monkeypatch
):
    press, _ = two_machines

    def fail_if_called():
        raise AssertionError("the LLM must not be called when gate 1 refuses")

    monkeypatch.setattr(rag, "get_llm_provider", fail_if_called)

    with override_settings(RETRIEVAL_MIN_SCORE=0.99):
        result = rag.ask(engineer, press, "What is the capital of France?")

    assert result.query_log.status == QueryLog.STATUS_INSUFFICIENT
    assert result.query_log.latency_ms_llm == 0
    assert result.citations == []
    assert "do not contain enough information" in result.query_log.answer_text


@pytest.mark.django_db
def test_question_about_another_machine_gets_a_hint_without_leaking(
    two_machines, engineer
):
    press, _ = two_machines
    result = rag.ask(engineer, press, "When is the AF-10 filter replaced on the AC-90?")

    assert "AC-90" in result.machine_hint
    assert "Switch machine" in result.machine_hint
    assert "discharge" not in result.machine_hint
    for citation in result.citations:
        assert citation.chunk.machine_id == press.pk
