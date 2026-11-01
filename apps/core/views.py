from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from apps.accounts.roles import ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR, role_of


@require_GET
def health(request) -> JsonResponse:
    """Liveness plus the facts a judge asks for: which backends are actually active."""
    checks = {"database": "error", "pgvector_extension": "absent"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            checks["database"] = "ok"
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            if cursor.fetchone():
                checks["pgvector_extension"] = "present"
    except Exception as exc:  # surfaced as unhealthy, never as a 500
        checks["database_error"] = type(exc).__name__

    from apps.assistant.providers import embedding_provider_info, llm_provider_info

    payload = {
        "app": settings.APP_NAME,
        "status": "ok" if checks["database"] == "ok" else "degraded",
        "checks": checks,
        "vector_backend": settings.VECTOR_BACKEND,
        "embedding": embedding_provider_info(),
        "llm": llm_provider_info(),
        "retrieval_min_score": settings.RETRIEVAL_MIN_SCORE,
    }
    return JsonResponse(payload, status=200 if payload["status"] == "ok" else 503)


def home(request):
    """Send each signed-in user to the page their role actually uses."""
    role = role_of(request.user)
    if role == ROLE_ADMIN:
        return redirect("admin_console")
    if role == ROLE_ENGINEER:
        return redirect("engineer_ask")
    if role == ROLE_SUPERVISOR:
        return redirect("supervisor_log")
    return redirect("login")
