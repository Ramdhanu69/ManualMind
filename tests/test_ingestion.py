"""Ingestion rules and login-protected delivery of the stored PDFs."""

from __future__ import annotations

import hashlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.manuals.models import Chunk, Manual
from apps.manuals.services.ingest import IngestionError, validate_upload
from tests.conftest import build_pdf

UPLOAD_URL = "/api/v1/manuals/"


@pytest.mark.django_db
def test_page_numbers_are_one_based(press, ingest_manual):
    manual = ingest_manual(
        press, "HP-OPS-01", ["Page one content.", "Page two content.", "Page three."]
    )

    assert manual.status == Manual.STATUS_INDEXED
    assert manual.page_count == 3
    pages = sorted(set(Chunk.objects.filter(manual=manual).values_list("page_number", flat=True)))
    assert pages == [1, 2, 3]
    assert not Chunk.objects.filter(manual=manual, page_number=0).exists()


@pytest.mark.django_db
def test_chunks_never_cross_a_page(press, ingest_manual):
    manual = ingest_manual(press, "HP-OPS-01", ["Alpha only here.", "Beta only here."])

    for chunk in Chunk.objects.filter(manual=manual):
        other = "Beta" if chunk.page_number == 1 else "Alpha"
        assert other not in chunk.text


@pytest.mark.django_db
def test_reuploading_an_identical_file_is_a_no_op(client, administrator, press):
    client.force_login(administrator)
    content = build_pdf(["Normal pressure is 120 to 140 bar."])
    payload = {
        "machine": press.machine_id,
        "document_id": "HP-OPS-01",
        "title": "HP-200 Operations Manual",
        "revision": "1.0",
    }

    first = client.post(
        UPLOAD_URL,
        {**payload, "file": SimpleUploadedFile("m.pdf", content, "application/pdf")},
    )
    assert first.status_code == 201
    chunk_count = Chunk.objects.count()

    second = client.post(
        UPLOAD_URL,
        {**payload, "file": SimpleUploadedFile("m.pdf", content, "application/pdf")},
    )
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert Manual.objects.count() == 1
    assert Chunk.objects.count() == chunk_count


@pytest.mark.django_db
def test_a_non_pdf_with_a_pdf_extension_is_rejected(client, administrator, press):
    client.force_login(administrator)
    response = client.post(
        UPLOAD_URL,
        {
            "machine": press.machine_id,
            "document_id": "HP-OPS-01",
            "title": "Fake",
            "revision": "1.0",
            "file": SimpleUploadedFile("evil.pdf", b"PK\x03\x04 not a pdf", "application/pdf"),
        },
    )

    assert response.status_code == 400
    assert "not a PDF" in response.json()["detail"]
    assert Manual.objects.count() == 0


def test_validate_upload_rejects_an_oversized_file(settings):
    settings.MAX_UPLOAD_BYTES = 10
    upload = SimpleUploadedFile("big.pdf", b"%PDF" + b"x" * 100, "application/pdf")

    with pytest.raises(IngestionError, match="larger than"):
        validate_upload(upload)


@pytest.mark.django_db
def test_a_new_revision_supersedes_the_previous_one(press, ingest_manual):
    first = ingest_manual(press, "HP-OPS-01", ["Revision one text."], revision="1.0")
    second = ingest_manual(press, "HP-OPS-01", ["Revision two text."], revision="2.0")

    first.refresh_from_db()
    assert first.is_active is False
    assert second.is_active is True
    assert Manual.objects.filter(document_id="HP-OPS-01").count() == 2


@pytest.mark.django_db
def test_superseded_revisions_are_not_retrieved(press, ingest_manual):
    from apps.assistant.services.rag import analyze_query, retrieve

    ingest_manual(press, "HP-OPS-01", ["Obsolete value is 999 bar."], revision="1.0")
    ingest_manual(press, "HP-OPS-01", ["Current value is 120 bar."], revision="2.0")

    analysis = analyze_query("what is the value in bar", press)
    text = " ".join(chunk.text for chunk in retrieve(analysis, press).chunks)
    assert "999" not in text
    assert "120" in text


@pytest.mark.django_db
def test_pdf_serving_requires_login(client, engineer, press, ingest_manual):
    manual = ingest_manual(press, "HP-OPS-01", ["Content."])

    anonymous = client.get(f"/api/v1/manuals/{manual.pk}/pdf/")
    assert anonymous.status_code == 302
    assert "/login/" in anonymous.headers["Location"]

    client.force_login(engineer)
    allowed = client.get(f"/api/v1/manuals/{manual.pk}/pdf/")
    assert allowed.status_code == 200
    assert allowed["Content-Type"] == "application/pdf"
    assert "inline" in allowed["Content-Disposition"]


@pytest.mark.django_db
def test_page_preview_returns_png_for_a_valid_page(client, engineer, press, ingest_manual):
    manual = ingest_manual(press, "HP-OPS-01", ["One.", "Two.", "Three."])
    client.force_login(engineer)

    response = client.get(f"/api/v1/manuals/{manual.pk}/page/2/preview/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert "max-age" in response["Cache-Control"]


@pytest.mark.django_db
def test_page_preview_rejects_out_of_range_pages(client, engineer, press, ingest_manual):
    manual = ingest_manual(press, "HP-OPS-01", ["One.", "Two.", "Three."])
    client.force_login(engineer)

    assert client.get(f"/api/v1/manuals/{manual.pk}/page/0/preview/").status_code == 404
    assert client.get(f"/api/v1/manuals/{manual.pk}/page/4/preview/").status_code == 404


@pytest.mark.django_db
def test_page_preview_requires_login(client, press, ingest_manual):
    manual = ingest_manual(press, "HP-OPS-01", ["One."])

    response = client.get(f"/api/v1/manuals/{manual.pk}/page/1/preview/")
    assert response.status_code == 302
    assert "/login/" in response.headers["Location"]


@pytest.mark.django_db
def test_failed_ingestion_is_recorded_not_raised(press):
    """A broken file must leave a FAILED row with a readable reason, not a 500."""
    content = b"%PDF-1.4 truncated and unreadable"
    manual = Manual.objects.create(
        document_id="HP-BAD-01",
        machine=press,
        title="Broken",
        revision="1.0",
        file=SimpleUploadedFile("broken.pdf", content, "application/pdf"),
        sha256=hashlib.sha256(content).hexdigest(),
    )

    from apps.manuals.services.ingest import run_ingestion

    result = run_ingestion(manual.pk)
    assert result.status == Manual.STATUS_FAILED
    assert result.error_message
