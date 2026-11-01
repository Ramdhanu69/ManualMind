"""Role enforcement. These rules are server-side, so the UI can never grant access."""

from __future__ import annotations

import pytest

from apps.assistant.models import QueryLog
from apps.core.models import AuditLog
from apps.manuals.models import Manual

UPLOAD_URL = "/api/v1/manuals/"


def _upload_payload(machine, upload):
    return {
        "machine": machine.machine_id,
        "document_id": "HP-OPS-01",
        "title": "HP-200 Operations Manual",
        "revision": "1.0",
        "file": upload,
    }


@pytest.mark.django_db
def test_engineer_cannot_upload_manual(client, engineer, press, pdf_upload):
    client.force_login(engineer)
    response = client.post(UPLOAD_URL, _upload_payload(press, pdf_upload()))

    assert response.status_code == 403
    assert Manual.objects.count() == 0
    denials = AuditLog.objects.filter(action=AuditLog.ACTION_DENIED_UPLOAD)
    assert denials.count() == 1
    assert denials.first().user == engineer


@pytest.mark.django_db
def test_supervisor_cannot_upload_manual(client, supervisor, press, pdf_upload):
    client.force_login(supervisor)
    response = client.post(UPLOAD_URL, _upload_payload(press, pdf_upload()))

    assert response.status_code == 403
    assert Manual.objects.count() == 0
    assert AuditLog.objects.filter(action=AuditLog.ACTION_DENIED_UPLOAD).count() == 1


@pytest.mark.django_db
def test_anonymous_cannot_upload_manual(client, press, pdf_upload):
    response = client.post(UPLOAD_URL, _upload_payload(press, pdf_upload()))

    assert response.status_code in (401, 403)
    assert Manual.objects.count() == 0


@pytest.mark.django_db
def test_administrator_can_upload_manual(client, administrator, press, pdf_upload):
    client.force_login(administrator)
    response = client.post(
        UPLOAD_URL,
        _upload_payload(press, pdf_upload(pages=["Normal pressure is 120 to 140 bar."])),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["manual"]["status"] == Manual.STATUS_INDEXED
    assert Manual.objects.count() == 1
    assert AuditLog.objects.filter(action=AuditLog.ACTION_UPLOAD).count() == 1


@pytest.mark.django_db
def test_supervisor_cannot_ask(client, supervisor, press):
    client.force_login(supervisor)
    response = client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": press.machine_id, "question": "What does E17 mean?"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert QueryLog.objects.count() == 0


@pytest.mark.django_db
def test_engineer_cannot_read_another_engineers_query(
    client, engineer, other_engineer, press, ingest_manual
):
    ingest_manual(press, "HP-OPS-01", ["E17 means low hydraulic pressure below 110 bar."])
    client.force_login(other_engineer)
    client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": press.machine_id, "question": "What does E17 mean?"},
        content_type="application/json",
    )
    query = QueryLog.objects.get()

    client.force_login(engineer)
    assert client.get(f"/api/v1/assistant/history/{query.pk}/").status_code == 404
    assert client.get("/api/v1/assistant/history/").json()["count"] == 0


@pytest.mark.django_db
def test_supervisor_can_read_every_query(
    client, supervisor, other_engineer, press, ingest_manual
):
    ingest_manual(press, "HP-OPS-01", ["E17 means low hydraulic pressure below 110 bar."])
    client.force_login(other_engineer)
    client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": press.machine_id, "question": "What does E17 mean?"},
        content_type="application/json",
    )
    query = QueryLog.objects.get()

    client.force_login(supervisor)
    assert client.get(f"/api/v1/assistant/history/{query.pk}/").status_code == 200
    assert client.get("/api/v1/assistant/history/").json()["count"] == 1


@pytest.mark.django_db
def test_only_administrator_can_create_a_machine(client, engineer, administrator):
    payload = {"machine_id": "M-NEW", "model": "NEW-1", "name": "New machine"}

    client.force_login(engineer)
    assert client.post("/api/v1/machines/", payload, content_type="application/json").status_code == 403

    client.force_login(administrator)
    assert client.post("/api/v1/machines/", payload, content_type="application/json").status_code == 201
