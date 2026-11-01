"""Re-embed and re-index every manual. Required after changing the embedding model."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.manuals.models import Manual
from apps.manuals.services.ingest import run_ingestion


class Command(BaseCommand):
    help = "Re-run ingestion for every manual (needed when EMBEDDING_MODEL changes)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--machine", help="Limit to one machine_id slug.")

    def handle(self, *args, **options) -> None:
        manuals = Manual.objects.all()
        if options["machine"]:
            manuals = manuals.filter(machine__machine_id=options["machine"])
        if not manuals.exists():
            self.stdout.write(self.style.WARNING("No manuals to reindex."))
            return
        for manual in manuals:
            result = run_ingestion(manual.pk)
            style = (
                self.style.SUCCESS
                if result.status == Manual.STATUS_INDEXED
                else self.style.ERROR
            )
            self.stdout.write(
                style(
                    f"{result.document_id} rev {result.revision}: {result.status} "
                    f"chunks={result.chunk_count}"
                )
            )
