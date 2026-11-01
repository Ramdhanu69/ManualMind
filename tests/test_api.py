"""Endpoint contracts: routes, methods and the shapes the UI depends on."""

from __future__ import annotations

import pytest

from apps.assistant.models import QueryLog


@pytest.mark.django_db
def test_health_reports_the_active_backends(client):
    response = client.get("/health/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["vector_backend"] in ("numpy", "pgvector")
    assert body["checks"]["database"] == "ok"
    assert "provider" in body["embedding"]
    assert "provider" in body["llm"]


@pytest.mark.django_db
def test_login_logout_and_me(client, engineer):
    from tests.conftest import PASSWORD

    assert client.get("/api/v1/auth/me").status_code == 403

    login = client.post(
        "/api/v1/auth/login",
        {"username": engineer.username, "password": PASSWORD},
        content_type="application/json",
    )
    assert login.status_code == 200
    assert login.json() == {"username": "engineer1", "role": "Engineer"}

    assert client.get("/api/v1/auth/me").json()["role"] == "Engineer"
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 403


@pytest.mark.django_db
def test_login_with_a_bad_password_is_rejected(client, engineer):
    response = client.post(
        "/api/v1/auth/login",
        {"username": engineer.username, "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "Invalid username or password" in response.json()["detail"]


@pytest.mark.django_db
def test_manual_list_filters_by_machine(
    client, engineer, press, compressor, ingest_manual
):
    ingest_manual(press, "HP-OPS-01", ["Press content."])
    ingest_manual(compressor, "AC-OM-01", ["Compressor content."])
    client.force_login(engineer)

    everything = client.get("/api/v1/manuals/").json()
    assert len(everything) == 2

    filtered = client.get("/api/v1/manuals/?machine=M-HP200").json()
    assert [row["document_id"] for row in filtered] == ["HP-OPS-01"]


@pytest.mark.django_db
def test_ask_returns_the_shape_the_ask_page_renders(client, engineer, press, ingest_manual):
    ingest_manual(press, "HP-OPS-01", ["E17 means low hydraulic pressure below 110 bar."])
    client.force_login(engineer)

    response = client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": press.machine_id, "question": "What does E17 mean?"},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    for key in (
        "status",
        "answer_text",
        "citations",
        "latency_ms_total",
        "machine_hint",
        "record_before_escalation",
    ):
        assert key in body
    assert body["status"] == QueryLog.STATUS_ANSWERED
    citation = body["citations"][0]
    for key in ("manual_id", "document_id", "revision", "page_number", "quote", "quote_verified"):
        assert key in citation


@pytest.mark.django_db
def test_ask_for_an_unknown_machine_is_404(client, engineer):
    client.force_login(engineer)
    response = client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": "M-NOPE", "question": "What does E17 mean?"},
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_knowledge_gaps_group_unanswered_questions(
    client, supervisor, engineer, press, ingest_manual, settings
):
    ingest_manual(press, "HP-OPS-01", ["E17 means low hydraulic pressure."])
    settings.RETRIEVAL_MIN_SCORE = 0.99

    client.force_login(engineer)
    client.post(
        "/api/v1/assistant/ask/",
        {"machine_id": press.machine_id, "question": "What is the capital of France?"},
        content_type="application/json",
    )

    client.force_login(supervisor)
    response = client.get("/api/v1/supervisor/knowledge-gaps/")

    assert response.status_code == 200
    body = response.json()
    assert body["unanswered_total"] == 1
    assert body["groups"][0]["machine_id"] == "M-HP200"
    assert body["groups"][0]["count"] == 1
    assert body["groups"][0]["latest"][0]["question"] == "What is the capital of France?"


@pytest.mark.django_db
def test_knowledge_gaps_are_not_visible_to_an_engineer(client, engineer):
    client.force_login(engineer)
    assert client.get("/api/v1/supervisor/knowledge-gaps/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,role_fixture",
    [
        ("/admin-console/", "administrator"),
        ("/ask/", "engineer"),
        ("/history/", "engineer"),
        ("/supervisor/log/", "supervisor"),
    ],
)
def test_pages_render_for_the_right_role(client, request, url, role_fixture):
    client.force_login(request.getfixturevalue(role_fixture))
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_pages_refuse_the_wrong_role(client, engineer):
    client.force_login(engineer)
    assert client.get("/admin-console/").status_code == 403
    assert client.get("/supervisor/log/").status_code == 403
