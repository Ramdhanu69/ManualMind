"""Ask endpoint and query history. Ownership rules are enforced in the queryset."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsEngineerOrAdministrator
from apps.accounts.roles import ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR, has_role
from apps.assistant.models import QueryLog
from apps.assistant.serializers import AskSerializer, QueryLogSerializer
from apps.assistant.services.rag import ask
from apps.machines.models import Machine

EXAMPLE_QUESTIONS = [
    "What does E17 mean?",
    "What is the normal operating pressure range?",
    "What triggers E17 and what should be inspected first?",
    "What should be recorded before escalation?",
]


def visible_queries(user):
    """Engineers see only their own questions; supervisors and admins see all."""
    queryset = QueryLog.objects.select_related("machine", "user").prefetch_related(
        "citations", "citations__manual"
    )
    if has_role(user, ROLE_SUPERVISOR, ROLE_ADMIN):
        return queryset
    return queryset.filter(user=user)


class AskAPIView(APIView):
    permission_classes = [IsEngineerOrAdministrator]

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        machine = get_object_or_404(
            Machine, machine_id=serializer.validated_data["machine_id"]
        )
        result = ask(request.user, machine, serializer.validated_data["question"])
        payload = QueryLogSerializer(result.query_log).data
        payload["machine_hint"] = result.machine_hint
        payload["record_before_escalation"] = result.record_before_escalation
        http_status = (
            status.HTTP_502_BAD_GATEWAY
            if result.query_log.status == QueryLog.STATUS_ERROR
            else status.HTTP_200_OK
        )
        return Response(payload, status=http_status)


class HistoryListAPIView(ListAPIView):
    serializer_class = QueryLogSerializer

    def get_queryset(self):
        queryset = visible_queries(self.request.user)
        params = self.request.query_params
        machine = params.get("machine")
        if machine:
            queryset = queryset.filter(machine__machine_id=machine)
        state = params.get("status")
        if state:
            queryset = queryset.filter(status=state)
        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        text = params.get("search")
        if text:
            queryset = queryset.filter(question__icontains=text)
        return queryset


class HistoryDetailAPIView(RetrieveAPIView):
    serializer_class = QueryLogSerializer

    def get_queryset(self):
        return visible_queries(self.request.user)


@login_required
def engineer_ask(request):
    if not has_role(request.user, ROLE_ENGINEER, ROLE_ADMIN):
        return render(request, "core/forbidden.html", {"needed": "Engineer"}, status=403)
    return render(
        request,
        "assistant/ask.html",
        {
            "machines": Machine.objects.filter(is_active=True),
            "example_questions": EXAMPLE_QUESTIONS,
        },
    )


@login_required
def engineer_history(request):
    return render(
        request,
        "assistant/history.html",
        {"machines": Machine.objects.all(), "own_only": True},
    )
