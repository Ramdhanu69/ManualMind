import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.machines.models import Machine


def manual_upload_path(instance: "Manual", filename: str) -> str:
    """Rename to a UUID so a hostile filename can never escape MEDIA_ROOT/manuals."""
    return f"manuals/{uuid.uuid4().hex}{Path(filename).suffix.lower() or '.pdf'}"


class Manual(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_INDEXED = "INDEXED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
    ]

    document_id = models.CharField(max_length=64)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="manuals")
    title = models.CharField(max_length=255)
    revision = models.CharField(max_length=32)
    file = models.FileField(upload_to=manual_upload_path)
    sha256 = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["machine__machine_id", "document_id", "-created_at"]
        constraints = [
            # A document is identified by its ID *and* revision: a new revision is a
            # new row that supersedes the old one, so document_id alone cannot be unique.
            models.UniqueConstraint(
                fields=["document_id", "revision"], name="uniq_document_revision"
            ),
            models.UniqueConstraint(
                fields=["machine", "revision", "sha256"], name="uniq_machine_revision_sha"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document_id} rev {self.revision}"

    @property
    def chunk_count(self) -> int:
        return self.chunks.count()


class Chunk(models.Model):
    manual = models.ForeignKey(Manual, on_delete=models.CASCADE, related_name="chunks")
    # Denormalised from manual.machine so the isolation filter is a single indexed
    # column in the retrieval WHERE clause.
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="chunks")
    page_number = models.PositiveIntegerField()
    section_title = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    content_hash = models.CharField(max_length=64)
    char_start = models.PositiveIntegerField()
    char_end = models.PositiveIntegerField()
    embedding = ArrayField(models.FloatField(), size=None)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        ordering = ["manual_id", "page_number", "char_start"]
        indexes = [
            models.Index(fields=["machine", "manual"]),
            models.Index(fields=["machine", "page_number"]),
            GinIndex(fields=["search_vector"], name="chunk_search_vector_gin"),
        ]

    def __str__(self) -> str:
        return f"{self.manual.document_id} p{self.page_number} [{self.char_start}:{self.char_end}]"
