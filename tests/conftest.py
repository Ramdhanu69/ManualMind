"""Shared fixtures. Tests run on FakeEmbeddings and FakeLLM, so no API key is needed."""

from __future__ import annotations

import io

import pymupdf
import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.roles import ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR
from apps.machines.models import Machine
from apps.manuals.models import Manual
from apps.manuals.services.ingest import run_ingestion

PASSWORD = "Test@12345"


def build_pdf(pages: list[str]) -> bytes:
    """A small real PDF, so ingestion is exercised end to end rather than mocked."""
    document = pymupdf.open()
    for body in pages:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 750), body, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def groups(db) -> dict[str, Group]:
    return {
        name: Group.objects.get_or_create(name=name)[0]
        for name in (ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR)
    }


@pytest.fixture
def make_user(db, groups):
    def _make(username: str, role: str) -> User:
        user = User.objects.create_user(username=username, password=PASSWORD)
        user.groups.add(groups[role])
        return user

    return _make


@pytest.fixture
def administrator(make_user) -> User:
    return make_user("admin1", ROLE_ADMIN)


@pytest.fixture
def engineer(make_user) -> User:
    return make_user("engineer1", ROLE_ENGINEER)


@pytest.fixture
def other_engineer(make_user) -> User:
    return make_user("engineer2", ROLE_ENGINEER)


@pytest.fixture
def supervisor(make_user) -> User:
    return make_user("supervisor1", ROLE_SUPERVISOR)


@pytest.fixture
def press(db) -> Machine:
    return Machine.objects.create(
        machine_id="M-HP200", model="HP-200", name="Hydraulic forming press"
    )


@pytest.fixture
def compressor(db) -> Machine:
    return Machine.objects.create(
        machine_id="M-AC90", model="AC-90", name="Air compressor"
    )


@pytest.fixture
def ingest_manual(db):
    """Create and index a manual from synthetic page text."""

    def _ingest(machine: Machine, document_id: str, pages: list[str], revision: str = "1.0") -> Manual:
        content = build_pdf(pages)
        manual = Manual.objects.create(
            document_id=document_id,
            machine=machine,
            title=f"{machine.model} {document_id}",
            revision=revision,
            file=SimpleUploadedFile(f"{document_id}.pdf", content, "application/pdf"),
            sha256=__import__("hashlib").sha256(content).hexdigest(),
        )
        return run_ingestion(manual.pk)

    return _ingest


@pytest.fixture
def pdf_upload():
    def _upload(name: str = "manual.pdf", pages: list[str] | None = None) -> SimpleUploadedFile:
        content = build_pdf(pages or ["Synthetic operations page one."])
        return SimpleUploadedFile(name, content, "application/pdf")

    return _upload


@pytest.fixture
def signed_in(client):
    def _sign_in(user: User):
        client.force_login(user)
        return client

    return _sign_in


@pytest.fixture
def pdf_bytes_reader():
    def _read(data: bytes) -> io.BytesIO:
        return io.BytesIO(data)

    return _read
