"""Supervisor read-only views: the full question log and the knowledge gaps."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSupervisorOrAdmin
from apps.accounts.roles import ROLE_ADMIN, ROLE_SUPERVISOR, has_role
from apps.assistant.models import QueryLog
from apps.machines.models import Machine

LATEST_EXAMPLES_PER_MACHINE = 5


class KnowledgeGapsAPIView(APIView):
    """Unanswered questions grouped by machine: what the manuals are missing."""

    permission_classes = [IsSupervisorOrAdmin]

    def get(self, request):
        unanswered = QueryLog.objects.filter(status=QueryLog.STATUS_INSUFFICIENT)
        grouped = (
            unanswered.values("machine__machine_id", "machine__model")
            .annotate(count=Count("id"), average_top_score=Avg("top_score"))
            .order_by("-count")
        )
        groups = []
        for row in grouped:
            machine_id = row["machine__machine_id"]
            examples = unanswered.filter(machine__machine_id=machine_id).order_by(
                "-created_at"
            )[:LATEST_EXAMPLES_PER_MACHINE]
            groups.append(
                {
                    "machine_id": machine_id,
                    "machine_model": row["machine__model"],
                    "count": row["count"],
                    "average_top_score": round(row["average_top_score"] or 0.0, 4),
                    "latest": [
                        {
                            "id": item.id,
                            "question": item.question,
                            "created_at": item.created_at,
                            "top_score": item.top_score,
                        }
                        for item in examples
                    ],
                }
            )

        totals = QueryLog.objects.aggregate(
            total=Count("id"),
            average_retrieval=Avg("latency_ms_retrieval"),
            average_llm=Avg("latency_ms_llm"),
        )
        return Response(
            {
                "unanswered_total": unanswered.count(),
                "queries_total": totals["total"] or 0,
                "average_latency_ms_retrieval": round(totals["average_retrieval"] or 0.0, 1),
                "average_latency_ms_llm": round(totals["average_llm"] or 0.0, 1),
                "groups": groups,
            }
        )


class SupervisorStatsAPIView(APIView):
    """Per-model counts and latencies shown beside the question log."""

    permission_classes = [IsSupervisorOrAdmin]

    def get(self, request):
        by_status = {
            row["status"]: row["count"]
            for row in QueryLog.objects.values("status").annotate(count=Count("id"))
        }
        by_model = (
            QueryLog.objects.exclude(llm_model="")
            .values("llm_model")
            .annotate(count=Count("id"), average_latency_ms=Avg("latency_ms_llm"))
            .order_by("-count")
        )
        return Response(
            {
                "by_status": by_status,
                "by_model": [
                    {
                        "llm_model": row["llm_model"],
                        "count": row["count"],
                        "average_latency_ms": round(row["average_latency_ms"] or 0.0, 1),
                    }
                    for row in by_model
                ],
            }
        )


@login_required
def supervisor_log(request):
    if not has_role(request.user, ROLE_SUPERVISOR, ROLE_ADMIN):
        return render(request, "core/forbidden.html", {"needed": "Supervisor"}, status=403)
    return render(
        request,
        "supervisor/log.html",
        {
            "machines": Machine.objects.all(),
            "statuses": [choice[0] for choice in QueryLog.STATUS_CHOICES],
        },
    )
