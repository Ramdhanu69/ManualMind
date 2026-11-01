"""Create the demo roles, users, machines and manuals. Safe to run repeatedly."""

from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.roles import ALL_ROLES, ROLE_ADMIN, ROLE_ENGINEER, ROLE_SUPERVISOR
from apps.machines.models import Machine
from apps.manuals.models import Manual
from apps.manuals.services.ingest import find_indexed_duplicate, run_ingestion, sha256_of

CSV_NAME = "machine_manual_index.csv"
MANUALS_DIRECTORY = "Manuals"
DEMO_USERS = [
    ("admin1", ROLE_ADMIN),
    ("engineer1", ROLE_ENGINEER),
    ("supervisor1", ROLE_SUPERVISOR),
]


class Command(BaseCommand):
    help = "Seed demo roles, users, machines and the student-pack manuals."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-manuals",
            action="store_true",
            help="Seed users and machines only, so an upload can be demonstrated live.",
        )

    def handle(self, *args, **options) -> None:
        self._seed_groups()
        self._seed_users()
        rows = self._read_index()
        machines = self._seed_machines(rows)
        if options["no_manuals"]:
            self.stdout.write(self.style.WARNING("Skipped manuals (--no-manuals)."))
            return
        self._seed_manuals(rows, machines)

    def _seed_groups(self) -> None:
        for role in ALL_ROLES:
            group, created = Group.objects.get_or_create(name=role)
            if created:
                self.stdout.write(f"group created: {group.name}")

    def _seed_users(self) -> None:
        for username, role in DEMO_USERS:
            password = settings.DEMO_PASSWORDS[username]
            user, created = User.objects.get_or_create(
                username=username, defaults={"is_staff": role == ROLE_ADMIN}
            )
            # Reset the password every run so a stale demo database still logs in.
            user.set_password(password)
            user.is_staff = role == ROLE_ADMIN
            user.save()
            user.groups.set([Group.objects.get(name=role)])
            self.stdout.write(
                f"user {'created' if created else 'updated'}: {username} ({role})"
            )

    def _read_index(self) -> list[dict]:
        path = Path(settings.STUDENT_PACK_DIR) / CSV_NAME
        if not path.exists():
            raise CommandError(f"Missing {path}. Put the student pack in student_pack/.")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        required = {
            "machine_id",
            "model",
            "machine_name",
            "document_id",
            "revision",
            "pdf_filename",
        }
        missing = required - set(rows[0] if rows else {})
        if missing:
            raise CommandError(f"{CSV_NAME} is missing columns: {sorted(missing)}")
        return rows

    def _seed_machines(self, rows: list[dict]) -> dict[str, Machine]:
        machines: dict[str, Machine] = {}
        for row in rows:
            machine, created = Machine.objects.get_or_create(
                machine_id=row["machine_id"],
                defaults={"model": row["model"], "name": row["machine_name"]},
            )
            machines[machine.machine_id] = machine
            if created:
                self.stdout.write(f"machine created: {machine.machine_id}")
        return machines

    def _seed_manuals(self, rows: list[dict], machines: dict[str, Machine]) -> None:
        directory = Path(settings.STUDENT_PACK_DIR) / MANUALS_DIRECTORY
        admin = User.objects.filter(username="admin1").first()
        for row in rows:
            machine = machines[row["machine_id"]]
            pdf_path = directory / row["pdf_filename"]
            if not pdf_path.exists():
                raise CommandError(f"Missing PDF {pdf_path}")

            with pdf_path.open("rb") as handle:
                digest = sha256_of(handle)
            if find_indexed_duplicate(machine.pk, row["revision"], digest) is not None:
                self.stdout.write(f"manual already indexed: {row['document_id']}")
                continue

            manual = Manual.objects.filter(
                document_id=row["document_id"], revision=row["revision"]
            ).first()
            if manual is None:
                with pdf_path.open("rb") as handle:
                    manual = Manual.objects.create(
                        document_id=row["document_id"],
                        machine=machine,
                        title=self._title_for(row),
                        revision=row["revision"],
                        file=File(handle, name=row["pdf_filename"]),
                        sha256=digest,
                        uploaded_by=admin,
                    )
            manual = run_ingestion(manual.pk)
            style = self.style.SUCCESS if manual.status == Manual.STATUS_INDEXED else self.style.ERROR
            self.stdout.write(
                style(
                    f"manual {manual.document_id} rev {manual.revision}: "
                    f"{manual.status} pages={manual.page_count} chunks={manual.chunk_count}"
                )
            )
            if manual.error_message:
                self.stdout.write(self.style.ERROR(f"  {manual.error_message}"))

    @staticmethod
    def _title_for(row: dict) -> str:
        """Readable title from the document id, since the index has no title column."""
        kind = row["document_id"].split("-")[1] if "-" in row["document_id"] else ""
        label = {"OPS": "Operations Manual", "MNT": "Maintenance Manual"}.get(
            kind, "Operations and Maintenance Manual"
        )
        return f"{row['model']} {label}"
