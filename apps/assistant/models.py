from django.conf import settings
from django.db import models

from apps.machines.models import Machine
from apps.manuals.models import Chunk, Manual


class QueryLog(models.Model):
    """One asked question, with the evidence and timings behind its answer."""

    STATUS_ANSWERED = "ANSWERED"
    STATUS_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
    STATUS_ERROR = "ERROR"
    STATUS_CHOICES = [
        (STATUS_ANSWERED, "Answered"),
        (STATUS_INSUFFICIENT, "Insufficient evidence"),
        (STATUS_ERROR, "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="queries"
    )
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="queries")
    question = models.TextField()
    answer_text = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    retrieved_chunk_ids = models.JSONField(default=list)
    top_score = models.FloatField(default=0.0)
    llm_provider = models.CharField(max_length=64, blank=True)
    llm_model = models.CharField(max_length=128, blank=True)
    embedding_model = models.CharField(max_length=128, blank=True)
    latency_ms_retrieval = models.PositiveIntegerField(default=0)
    latency_ms_llm = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["machine", "status"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.machine.machine_id} {self.status}"

    @property
    def latency_ms_total(self) -> int:
        return self.latency_ms_retrieval + self.latency_ms_llm


class QueryCitation(models.Model):
    """A source card. The quote is always text copied from the stored chunk."""

    query = models.ForeignKey(QueryLog, on_delete=models.CASCADE, related_name="citations")
    chunk = models.ForeignKey(Chunk, null=True, on_delete=models.SET_NULL)
    manual = models.ForeignKey(Manual, null=True, on_delete=models.SET_NULL)
    document_id = models.CharField(max_length=64)
    revision = models.CharField(max_length=32)
    page_number = models.PositiveIntegerField()
    quote = models.TextField()
    quote_verified = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.document_id} p{self.page_number}"
