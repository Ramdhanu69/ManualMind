"""Optional step: install the pgvector extension for VECTOR_BACKEND=pgvector.

Kept out of migrations on purpose, so the default numpy backend never needs a
database extension and a missing extension can never break a migration run.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Run CREATE EXTENSION IF NOT EXISTS vector (only needed for pgvector)."

    def handle(self, *args, **options) -> None:
        if settings.VECTOR_BACKEND != "pgvector":
            self.stdout.write(
                self.style.WARNING(
                    f"VECTOR_BACKEND is {settings.VECTOR_BACKEND}; the extension is not "
                    "required. Set VECTOR_BACKEND=pgvector first if you want it."
                )
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"Could not create the vector extension: {type(exc).__name__}: {exc}\n"
                    "Set VECTOR_BACKEND=numpy to run without it."
                )
            )
            return
        self.stdout.write(self.style.SUCCESS("pgvector extension is available."))
