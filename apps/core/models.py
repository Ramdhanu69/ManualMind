from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of security-relevant actions (uploads, denials, logins)."""

    ACTION_UPLOAD = "UPLOAD"
    ACTION_INGEST = "INGEST"
    ACTION_REINDEX = "REINDEX"
    ACTION_DENIED_UPLOAD = "DENIED_UPLOAD"
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_MACHINE_CREATE = "MACHINE_CREATE"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=32)
    target = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action} {self.target}"


def record_audit(user, action: str, target: str = "") -> AuditLog:
    """Write an audit row. `user` may be an AnonymousUser or None."""
    actor = user if getattr(user, "is_authenticated", False) else None
    return AuditLog.objects.create(user=actor, action=action, target=target[:255])
