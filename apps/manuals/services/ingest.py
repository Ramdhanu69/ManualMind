"""Validate, extract, chunk, embed and index an uploaded manual.

Ingestion is idempotent on the file's SHA-256 and revision-aware: a new revision
of a document_id supersedes the previous one instead of replacing its row.
"""

from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db import transaction

from apps.assistant.providers import get_embedding_provider
from apps.manuals.models import Chunk, Manual
from apps.manuals.services.extract import ExtractedPage, extract_pages

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
_EMBED_BATCH = 32


class IngestionError(Exception):
    """The upload cannot be indexed, with a message safe to show a user."""


def validate_upload(uploaded) -> None:
    """Reject anything that is not a PDF within the size limit.

    The magic bytes are checked rather than the extension, because the extension
    is attacker-controlled.
    """
    if uploaded.size == 0:
        raise IngestionError("The uploaded file is empty.")
    if uploaded.size > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise IngestionError(f"The file is larger than the {limit_mb} MB limit.")
    uploaded.seek(0)
    header = uploaded.read(len(PDF_MAGIC))
    uploaded.seek(0)
    if header != PDF_MAGIC:
        raise IngestionError("The file is not a PDF (it does not start with '%PDF').")


def sha256_of(uploaded) -> str:
    digest = hashlib.sha256()
    uploaded.seek(0)
    for block in iter(lambda: uploaded.read(65536), b""):
        digest.update(block)
    uploaded.seek(0)
    return digest.hexdigest()


def find_indexed_duplicate(machine_id: int, revision: str, sha256: str) -> Manual | None:
    """An identical file already indexed for this machine and revision is a no-op."""
    return Manual.objects.filter(
        machine_id=machine_id,
        revision=revision,
        sha256=sha256,
        status=Manual.STATUS_INDEXED,
    ).first()


def chunk_spans(text: str) -> list[tuple[int, int]]:
    """Offsets of overlapping chunks within one section, at line/sentence breaks."""
    length = len(text)
    if length == 0:
        return []
    minimum = settings.CHUNK_MIN_CHARS
    maximum = settings.CHUNK_MAX_CHARS
    overlap = settings.CHUNK_OVERLAP_CHARS

    spans: list[tuple[int, int]] = []
    position = 0
    while position < length:
        end = min(length, position + maximum)
        if end < length:
            window_start = min(position + minimum, end)
            cut = text.rfind("\n", window_start, end)
            if cut == -1:
                cut = text.rfind(". ", window_start, end)
                if cut != -1:
                    cut += 1
            if cut > position:
                end = cut
        # Absorb a short tail rather than emitting a stub chunk.
        if length - end < minimum // 2:
            end = length
        spans.append((position, end))
        if end >= length:
            break
        position = max(position + 1, end - overlap)
    return spans


def _embedded_text(manual: Manual, page_number: int, section_title: str, text: str) -> str:
    """Prefix the chunk with its coordinates so the vector carries that context."""
    header = (
        f"[{manual.machine.model} | {manual.document_id} rev {manual.revision} "
        f"| page {page_number} | {section_title or 'General'}]"
    )
    return f"{header}\n{text}"


def build_chunks(manual: Manual, pages: list[ExtractedPage]) -> list[Chunk]:
    """Chunk every page without ever crossing a page or section boundary."""
    chunks: list[Chunk] = []
    for page in pages:
        for section in page.sections:
            for start, end in chunk_spans(section.text):
                text = section.text[start:end].strip()
                if not text:
                    continue
                chunks.append(
                    Chunk(
                        manual=manual,
                        machine_id=manual.machine_id,
                        page_number=page.page_number,
                        section_title=section.title[:255],
                        text=text,
                        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        char_start=section.char_start + start,
                        char_end=section.char_start + end,
                        embedding=[],
                    )
                )
    return chunks


def run_ingestion(manual_id: int) -> Manual:
    """Index one manual. Synchronous today; the signature is the async seam.

    TODO-OPT: dispatch via Celery `run_ingestion.delay(manual_id)` in Phase 2 and
    report progress, keeping this body as the task function.
    """
    manual = Manual.objects.select_related("machine").get(pk=manual_id)
    try:
        pages = extract_pages(manual.file.path)
        chunks = build_chunks(manual, pages)
        if not chunks:
            raise IngestionError("No extractable text was found in the PDF.")

        provider = get_embedding_provider()
        texts = [
            _embedded_text(manual, chunk.page_number, chunk.section_title, chunk.text)
            for chunk in chunks
        ]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            vectors.extend(provider.embed_documents(texts[start : start + _EMBED_BATCH]))
        if len(vectors) != len(chunks):
            raise IngestionError("The embedding provider returned the wrong number of vectors.")
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != settings.EMBEDDING_DIM:
                raise IngestionError(
                    f"Embedding provider returned {len(vector)} dimensions but "
                    f"EMBEDDING_DIM is {settings.EMBEDDING_DIM}."
                )
            chunk.embedding = vector

        with transaction.atomic():
            manual.chunks.all().delete()
            Chunk.objects.bulk_create(chunks, batch_size=200)
            Chunk.objects.filter(manual=manual).update(
                search_vector=SearchVector("section_title", weight="A", config="english")
                + SearchVector("text", weight="B", config="english")
            )
            manual.page_count = len(pages)
            manual.status = Manual.STATUS_INDEXED
            manual.error_message = ""
            manual.is_active = True
            manual.save(
                update_fields=["page_count", "status", "error_message", "is_active"]
            )
            # A newer revision of the same document supersedes the older rows.
            Manual.objects.filter(document_id=manual.document_id).exclude(
                pk=manual.pk
            ).update(is_active=False)
    except Exception as exc:
        message = str(exc) if isinstance(exc, IngestionError) else f"{type(exc).__name__}: {exc}"
        Manual.objects.filter(pk=manual.pk).update(
            status=Manual.STATUS_FAILED, error_message=message[:2000]
        )
        logger.exception("ingestion failed manual=%s", manual.document_id)
        manual.refresh_from_db()
        return manual

    logger.info(
        "ingested manual=%s revision=%s pages=%s chunks=%s",
        manual.document_id,
        manual.revision,
        manual.page_count,
        len(chunks),
    )
    manual.refresh_from_db()
    return manual
