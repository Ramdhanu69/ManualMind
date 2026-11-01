"""Manual upload, indexing, and login-protected delivery of the stored PDFs."""

from __future__ import annotations

import pymupdf
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdministrator
from apps.accounts.roles import ROLE_ADMIN, has_role
from apps.core.models import AuditLog, record_audit
from apps.machines.models import Machine
from apps.manuals.models import Manual
from apps.manuals.serializers import ManualSerializer, ManualUploadSerializer
from apps.manuals.services.ingest import (
    IngestionError,
    find_indexed_duplicate,
    run_ingestion,
    sha256_of,
    validate_upload,
)

PREVIEW_DPI = 150
PREVIEW_CACHE_SECONDS = 3600


def _manual_queryset():
    return Manual.objects.select_related("machine")


class ManualListCreateAPIView(ListAPIView):
    """GET lists manuals for any signed-in user; POST uploads, Administrator only.

    A denied upload is itself an audited event, so the attempt is on record.
    """

    serializer_class = ManualSerializer
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = _manual_queryset()
        machine = self.request.query_params.get("machine")
        if machine:
            queryset = queryset.filter(machine__machine_id=machine)
        return queryset

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrator()]
        return super().get_permissions()

    def permission_denied(self, request, message=None, code=None):
        if request.method == "POST":
            username = getattr(request.user, "username", "") or "anonymous"
            record_audit(
                request.user,
                AuditLog.ACTION_DENIED_UPLOAD,
                f"POST /api/v1/manuals/ by {username}",
            )
        super().permission_denied(request, message=message, code=code)

    def post(self, request, *args, **kwargs):
        serializer = ManualUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        upload = data["file"]

        try:
            validate_upload(upload)
        except IngestionError as exc:
            return Response(
                {"detail": str(exc), "errors": {"file": [str(exc)]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        digest = sha256_of(upload)
        existing = find_indexed_duplicate(data["machine"].pk, data["revision"], digest)
        if existing is not None:
            return Response(
                {
                    "detail": "This exact file is already indexed for that machine and revision.",
                    "manual": ManualSerializer(existing).data,
                    "created": False,
                },
                status=status.HTTP_200_OK,
            )

        try:
            manual = Manual.objects.create(
                document_id=data["document_id"],
                machine=data["machine"],
                title=data["title"],
                revision=data["revision"],
                file=upload,
                sha256=digest,
                uploaded_by=request.user,
            )
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        f"Document {data['document_id']} revision {data['revision']} "
                        "already exists. Upload a new revision number instead."
                    ),
                    "errors": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        record_audit(request.user, AuditLog.ACTION_UPLOAD, manual.document_id)
        manual = run_ingestion(manual.pk)
        record_audit(
            request.user,
            AuditLog.ACTION_INGEST,
            f"{manual.document_id} -> {manual.status}",
        )
        return Response(
            {"manual": ManualSerializer(manual).data, "created": True},
            status=status.HTTP_201_CREATED,
        )


class ManualReindexAPIView(APIView):
    permission_classes = [IsAdministrator]

    def post(self, request, pk: int):
        manual = get_object_or_404(_manual_queryset(), pk=pk)
        manual = run_ingestion(manual.pk)
        record_audit(
            request.user,
            AuditLog.ACTION_REINDEX,
            f"{manual.document_id} -> {manual.status}",
        )
        return Response({"manual": ManualSerializer(manual).data})


@login_required
@require_GET
def manual_pdf(request, pk: int):
    """Stream the stored PDF. Never a public media URL, so access stays checked."""
    manual = get_object_or_404(Manual, pk=pk)
    response = FileResponse(manual.file.open("rb"), content_type="application/pdf")
    filename = f"{manual.document_id}_rev{manual.revision}.pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
@require_GET
def manual_page_preview(request, pk: int, page_number: int):
    """Render one page as PNG so a cited page can be shown next to its quote."""
    manual = get_object_or_404(Manual, pk=pk)
    if page_number < 1 or (manual.page_count and page_number > manual.page_count):
        raise Http404("That page does not exist in this manual.")
    # TODO-OPT: cache the rendered PNG on disk, keyed by sha256 + page + dpi.
    with pymupdf.open(manual.file.path) as document:
        if page_number > document.page_count:
            raise Http404("That page does not exist in this manual.")
        image = document[page_number - 1].get_pixmap(dpi=PREVIEW_DPI).tobytes("png")
    response = HttpResponse(image, content_type="image/png")
    response["Cache-Control"] = f"private, max-age={PREVIEW_CACHE_SECONDS}"
    return response


@login_required
def admin_console(request):
    """Administrator page: register machines, upload manuals, watch index status."""
    if not has_role(request.user, ROLE_ADMIN):
        return render(request, "core/forbidden.html", {"needed": "Administrator"}, status=403)
    return render(
        request,
        "manuals/admin_console.html",
        {"machines": Machine.objects.all()},
    )
