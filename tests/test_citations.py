"""Citation grounding: what the model claims versus what the system will display."""

from __future__ import annotations

import pytest

from apps.assistant.models import QueryCitation, QueryLog
from apps.assistant.services import rag
from apps.assistant.services.citations import locate_quote, verify_citations

CHUNK_TEXT = (
    "E17 is generated when pressure stays below 110 bar for more than 5 seconds "
    "during forming. The normal forming range is 120 to 140 bar."
)


class StubLLM:
    """Returns a fixed payload so each verifier branch can be tested exactly."""

    name = "stub"
    model = "stub-llm"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate_json(self, system, user, schema):
        self.calls += 1
        return self.payload


@pytest.fixture
def press_manual(press, ingest_manual):
    ingest_manual(press, "HP-OPS-01", [CHUNK_TEXT])
    return press


def _ask_with(monkeypatch, payload, engineer, machine):
    stub = StubLLM(payload)
    monkeypatch.setattr(rag, "get_llm_provider", lambda: stub)
    return rag.ask(engineer, machine, "What does E17 mean?"), stub


def test_exact_quote_is_verified():
    quote = "pressure stays below 110 bar"
    text, verified = locate_quote(quote, CHUNK_TEXT)
    assert verified is True
    assert text == quote


def test_whitespace_and_dash_differences_still_verify():
    quote = "pressure   stays below 110 bar"
    text, verified = locate_quote(quote, CHUNK_TEXT)
    assert verified is True
    assert "110 bar" in text


def test_paraphrase_falls_back_to_stored_text():
    text, verified = locate_quote("The pump has definitely failed.", CHUNK_TEXT)
    assert verified is False
    assert text == CHUNK_TEXT[:200].strip()


def test_invented_chunk_id_is_dropped():
    verified = verify_citations(
        [{"chunk_id": 99999, "quote": "anything"}], {1: CHUNK_TEXT}
    )
    assert verified == []


@pytest.mark.django_db
def test_fabricated_quote_keeps_the_citation_but_marks_it_unverified(
    monkeypatch, engineer, press_manual
):
    from apps.manuals.models import Chunk

    chunk = Chunk.objects.filter(machine=press_manual).first()
    result, _ = _ask_with(
        monkeypatch,
        {
            "status": "ANSWERED",
            "answer": "E17 indicates low hydraulic pressure.",
            "citations": [{"chunk_id": chunk.id, "quote": "A quote that is not present."}],
            "record_before_escalation": [],
        },
        engineer,
        press_manual,
    )

    assert result.query_log.status == QueryLog.STATUS_ANSWERED
    citation = result.query_log.citations.get()
    assert citation.quote_verified is False
    assert citation.quote == chunk.text[:200].strip()
    assert citation.quote in chunk.text


@pytest.mark.django_db
def test_answered_with_no_valid_chunk_id_is_downgraded(
    monkeypatch, engineer, press_manual
):
    result, _ = _ask_with(
        monkeypatch,
        {
            "status": "ANSWERED",
            "answer": "E17 means the pump has failed.",
            "citations": [{"chunk_id": 987654, "quote": "invented"}],
            "record_before_escalation": [],
        },
        engineer,
        press_manual,
    )

    assert result.query_log.status == QueryLog.STATUS_INSUFFICIENT
    assert result.query_log.citations.count() == 0
    assert "do not contain enough information" in result.query_log.answer_text


@pytest.mark.django_db
def test_every_ask_is_persisted_with_its_citations(monkeypatch, engineer, press_manual):
    from apps.manuals.models import Chunk

    chunk = Chunk.objects.filter(machine=press_manual).first()
    result, stub = _ask_with(
        monkeypatch,
        {
            "status": "ANSWERED",
            "answer": "E17 is low hydraulic pressure.",
            "citations": [
                {"chunk_id": chunk.id, "quote": "pressure stays below 110 bar"}
            ],
            "record_before_escalation": ["machine ID", "timestamp"],
        },
        engineer,
        press_manual,
    )

    assert stub.calls == 1
    log = QueryLog.objects.get()
    assert log.user == engineer
    assert log.machine == press_manual
    assert log.status == QueryLog.STATUS_ANSWERED
    assert log.retrieved_chunk_ids
    assert log.embedding_model and log.llm_model
    assert QueryCitation.objects.count() == 1

    citation = QueryCitation.objects.get()
    assert citation.quote_verified is True
    assert citation.document_id == "HP-OPS-01"
    assert citation.page_number == 1
    assert result.record_before_escalation == ["machine ID", "timestamp"]


@pytest.mark.django_db
def test_insufficient_evidence_from_the_model_is_recorded(
    monkeypatch, engineer, press_manual
):
    result, _ = _ask_with(
        monkeypatch,
        {
            "status": "INSUFFICIENT_EVIDENCE",
            "answer": "",
            "citations": [],
            "record_before_escalation": [],
        },
        engineer,
        press_manual,
    )

    assert result.query_log.status == QueryLog.STATUS_INSUFFICIENT
    assert QueryLog.objects.count() == 1
    assert result.query_log.citations.count() == 0
