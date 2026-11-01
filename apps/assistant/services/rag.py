"""Retrieval and answer pipeline.

The two properties this module exists to guarantee:

1. Machine isolation. Every retrieval path filters on `chunk.machine_id` inside
   the database query, so a chunk belonging to another machine cannot reach the
   model at all.
2. Grounded citations. Chunk ids returned by the model are checked against what
   was actually retrieved, and a displayed quote is always text copied from the
   stored chunk.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import transaction
from django.db.models import F

from apps.assistant.models import QueryCitation, QueryLog
from apps.assistant.providers import ProviderError, get_embedding_provider, get_llm_provider
from apps.assistant.services.citations import verify_citations
from apps.assistant.services.vectorstore import get_vector_store
from apps.machines.models import Machine
from apps.manuals.models import Chunk, Manual

logger = logging.getLogger(__name__)

ALARM_CODE = re.compile(r"\bE\d{2}\b", re.IGNORECASE)
PART_IDENTIFIER = re.compile(r"\b[A-Z]{2}-\d{2}\b")
MAX_QUESTION_CHARS = 1000

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ANSWERED", "INSUFFICIENT_EVIDENCE"]},
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["chunk_id", "quote"],
            },
        },
        "record_before_escalation": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "answer", "citations"],
}

SYSTEM_PROMPT = """You are a maintenance manual assistant for a single machine.

Answer ONLY from the numbered passages supplied in the user message. Every passage
belongs to machine {model}. You have no other knowledge: do not use general
engineering knowledge, and do not infer a value that is not written in a passage.

If the passages do not contain the answer, set "status" to "INSUFFICIENT_EVIDENCE".
That includes the case where a passage states that the information is not provided,
not specified or not supplied.

When the answer needs passages from more than one document, cite each of them.

Every factual sentence in "answer" must be supported by a citation. Each citation
quote must be copied EXACTLY from its passage as a short verbatim span of fewer
than 300 characters. Never write a quote in your own words.

Respect "whichever occurs first" logic and exact thresholds as written. Do not
round a number, convert a unit, or merge two thresholds into one.

Never state or imply that you authorize operation, repair or return to service.
Authorization belongs to the people the manuals designate.

If, and only if, the passages list items to record before escalation, put them in
"record_before_escalation". Otherwise return an empty list.

Reply with a single JSON object and nothing else:
{{"status": "ANSWERED" | "INSUFFICIENT_EVIDENCE", "answer": str,
"citations": [{{"chunk_id": int, "quote": str}}],
"record_before_escalation": [str]}}"""

INSUFFICIENT_MESSAGE = (
    "The available manuals for {model} do not contain enough information to "
    "answer this question."
)


@dataclass
class QueryAnalysis:
    question: str
    alarm_codes: list[str] = field(default_factory=list)
    part_identifiers: list[str] = field(default_factory=list)
    other_machine_hint: str = ""

    @property
    def exact_terms(self) -> list[str]:
        return self.alarm_codes + self.part_identifiers


@dataclass
class Retrieval:
    chunks: list[Chunk]
    vector_scores: dict[int, float]
    top_score: float
    exact_match_chunk_ids: set[int]


@dataclass
class AnswerResult:
    query_log: QueryLog
    citations: list[QueryCitation]
    machine_hint: str = ""
    record_before_escalation: list[str] = field(default_factory=list)


def analyze_query(question: str, machine: Machine) -> QueryAnalysis:
    """Pull out the identifiers that keyword search has to match exactly."""
    normalized = " ".join(question.split())[:MAX_QUESTION_CHARS]
    codes = sorted({match.group(0).upper() for match in ALARM_CODE.finditer(normalized)})
    parts = sorted(
        {
            match.group(0).upper()
            for match in PART_IDENTIFIER.finditer(normalized.upper())
            if match.group(0).upper() != machine.model.upper()
        }
    )
    return QueryAnalysis(
        question=normalized,
        alarm_codes=codes,
        part_identifiers=parts,
        other_machine_hint=_other_machine_hint(normalized, machine),
    )


def _other_machine_hint(question: str, machine: Machine) -> str:
    """Warn when the question names a different registered machine.

    The hint never reveals content from the other machine. It only reports that
    the machine selection would have to change.
    """
    models = (
        Machine.objects.exclude(pk=machine.pk).values_list("model", flat=True).distinct()
    )
    for model in models:
        pattern = re.escape(model).replace(r"\-", r"[\s\-]?")
        if re.search(rf"\b{pattern}\b", question, re.IGNORECASE):
            return (
                f"Your question mentions {model} but {machine.model} is selected. "
                f"Switch machine to ask about it."
            )
    return ""


def machine_chunks(machine: Machine):
    """The only queryset retrieval may start from: isolation lives in this filter."""
    return Chunk.objects.filter(
        machine_id=machine.pk,
        manual__is_active=True,
        manual__status=Manual.STATUS_INDEXED,
    )


def _keyword_ranking(analysis: QueryAnalysis, machine: Machine) -> list[int]:
    search = SearchQuery(analysis.question, search_type="websearch", config="english")
    rows = (
        machine_chunks(machine)
        .filter(search_vector=search)
        .annotate(rank=SearchRank(F("search_vector"), search))
        .order_by("-rank", "id")
        .values_list("id", flat=True)[: settings.RETRIEVAL_KEYWORD_TOP_K]
    )
    return list(rows)


def _exact_ranking(analysis: QueryAnalysis, machine: Machine) -> list[int]:
    """Exact hits for alarm codes and part identifiers, which vectors often miss."""
    found: list[int] = []
    for term in analysis.exact_terms:
        rows = (
            machine_chunks(machine)
            .filter(text__icontains=term)
            .order_by("page_number", "char_start")
            .values_list("id", flat=True)[: settings.RETRIEVAL_KEYWORD_TOP_K]
        )
        for chunk_id in rows:
            if chunk_id not in found:
                found.append(chunk_id)
    return found


def _reciprocal_rank_fusion(rankings: list[list[int]]) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (
                settings.RRF_K + position + 1
            )
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def retrieve(analysis: QueryAnalysis, machine: Machine) -> Retrieval:
    """Hybrid retrieval: vector, full-text and exact identifier, fused with RRF.

    TODO-OPT: run a cross-encoder reranker over the fused list before truncating.
    """
    embedding = get_embedding_provider().embed_query(analysis.question)
    vector_hits = get_vector_store().search(
        machine.pk, embedding, settings.RETRIEVAL_VECTOR_TOP_K
    )
    vector_scores = {chunk_id: score for chunk_id, score in vector_hits}

    exact_ids = _exact_ranking(analysis, machine)
    fused = _reciprocal_rank_fusion(
        [
            [chunk_id for chunk_id, _ in vector_hits],
            _keyword_ranking(analysis, machine),
            exact_ids,
        ]
    )
    selected = [chunk_id for chunk_id, _ in fused[: settings.RETRIEVAL_CONTEXT_K]]
    by_id = {
        chunk.id: chunk
        for chunk in machine_chunks(machine)
        .select_related("manual", "manual__machine")
        .filter(id__in=selected)
    }
    chunks = [by_id[chunk_id] for chunk_id in selected if chunk_id in by_id]
    return Retrieval(
        chunks=chunks,
        vector_scores=vector_scores,
        top_score=max(vector_scores.values(), default=0.0),
        exact_match_chunk_ids=set(exact_ids),
    )


def build_context(chunks: list[Chunk]) -> str:
    """Render the passages. The chunk_id marker is the contract with the verifier."""
    blocks = []
    for position, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[chunk_id={chunk.id} | passage={position} | document="
            f"{chunk.manual.document_id} rev {chunk.manual.revision} | page "
            f"{chunk.page_number} | section={chunk.section_title or 'General'}]\n"
            f"{chunk.text}"
        )
    return "\n".join(blocks)


def ask(user, machine: Machine, question: str) -> AnswerResult:
    """Run the full pipeline and persist the outcome, whatever it turns out to be."""
    analysis = analyze_query(question, machine)
    providers = {
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
    }

    started = time.perf_counter()
    try:
        retrieval = retrieve(analysis, machine)
    except (ProviderError, RuntimeError) as exc:
        return _persist(
            user=user,
            machine=machine,
            analysis=analysis,
            status=QueryLog.STATUS_ERROR,
            answer_text=str(exc),
            chunk_ids=[],
            citations=[],
            top_score=0.0,
            retrieval_ms=int((time.perf_counter() - started) * 1000),
            llm_ms=0,
            providers=providers,
        )
    retrieval_ms = int((time.perf_counter() - started) * 1000)
    chunk_ids = [chunk.id for chunk in retrieval.chunks]

    # Evidence gate 1: do not spend a model call on a hopeless retrieval.
    context_has_exact_match = bool(retrieval.exact_match_chunk_ids & set(chunk_ids))
    if not retrieval.chunks or (
        retrieval.top_score < settings.RETRIEVAL_MIN_SCORE and not context_has_exact_match
    ):
        return _persist(
            user=user,
            machine=machine,
            analysis=analysis,
            status=QueryLog.STATUS_INSUFFICIENT,
            answer_text=INSUFFICIENT_MESSAGE.format(model=machine.model),
            chunk_ids=chunk_ids,
            citations=[],
            top_score=retrieval.top_score,
            retrieval_ms=retrieval_ms,
            llm_ms=0,
            providers=providers,
        )

    context_texts = {chunk.id: chunk.text for chunk in retrieval.chunks}
    started_llm = time.perf_counter()
    try:
        payload = get_llm_provider().generate_json(
            SYSTEM_PROMPT.format(model=machine.model),
            f"Question about {machine.model}: {analysis.question}\n\n"
            f"Passages:\n{build_context(retrieval.chunks)}",
            ANSWER_SCHEMA,
        )
    except ProviderError as exc:
        return _persist(
            user=user,
            machine=machine,
            analysis=analysis,
            status=QueryLog.STATUS_ERROR,
            answer_text=str(exc),
            chunk_ids=chunk_ids,
            citations=[],
            top_score=retrieval.top_score,
            retrieval_ms=retrieval_ms,
            llm_ms=int((time.perf_counter() - started_llm) * 1000),
            providers=providers,
        )
    llm_ms = int((time.perf_counter() - started_llm) * 1000)

    # Evidence gate 2: the answer is only as good as its verifiable chunk ids.
    citations = verify_citations(payload.get("citations"), context_texts)
    answered = str(payload.get("status")) == "ANSWERED" and bool(citations)
    if answered:
        status = QueryLog.STATUS_ANSWERED
        answer_text = str(payload.get("answer") or "").strip()
        escalation = [
            str(item)
            for item in (payload.get("record_before_escalation") or [])
            if str(item).strip()
        ]
    else:
        status = QueryLog.STATUS_INSUFFICIENT
        answer_text = INSUFFICIENT_MESSAGE.format(model=machine.model)
        citations = []
        escalation = []

    return _persist(
        user=user,
        machine=machine,
        analysis=analysis,
        status=status,
        answer_text=answer_text,
        chunk_ids=chunk_ids,
        citations=citations,
        top_score=retrieval.top_score,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        providers=providers,
        escalation=escalation,
    )


def _persist(
    *,
    user,
    machine: Machine,
    analysis: QueryAnalysis,
    status: str,
    answer_text: str,
    chunk_ids: list[int],
    citations: list,
    top_score: float,
    retrieval_ms: int,
    llm_ms: int,
    providers: dict,
    escalation: list[str] | None = None,
) -> AnswerResult:
    """Record every query, refusals and errors included, for the supervisor views."""
    with transaction.atomic():
        query_log = QueryLog.objects.create(
            user=user,
            machine=machine,
            question=analysis.question,
            answer_text=answer_text,
            status=status,
            retrieved_chunk_ids=chunk_ids,
            top_score=top_score,
            llm_provider=providers["llm_provider"],
            llm_model=providers["llm_model"],
            embedding_model=providers["embedding_model"],
            latency_ms_retrieval=retrieval_ms,
            latency_ms_llm=llm_ms,
        )
        chunks = {
            chunk.id: chunk
            for chunk in Chunk.objects.select_related("manual").filter(
                id__in=[citation.chunk_id for citation in citations]
            )
        }
        rows = []
        for order, citation in enumerate(citations):
            chunk = chunks.get(citation.chunk_id)
            if chunk is None:
                continue
            rows.append(
                QueryCitation(
                    query=query_log,
                    chunk=chunk,
                    manual=chunk.manual,
                    document_id=chunk.manual.document_id,
                    revision=chunk.manual.revision,
                    page_number=chunk.page_number,
                    quote=citation.quote,
                    quote_verified=citation.quote_verified,
                    order=order,
                )
            )
        QueryCitation.objects.bulk_create(rows)

    logger.info(
        "ask machine=%s status=%s top_score=%.3f retrieval_ms=%s llm_ms=%s citations=%s",
        machine.machine_id,
        status,
        top_score,
        retrieval_ms,
        llm_ms,
        len(rows),
    )
    return AnswerResult(
        query_log=query_log,
        citations=rows,
        machine_hint=analysis.other_machine_hint,
        record_before_escalation=escalation or [],
    )
