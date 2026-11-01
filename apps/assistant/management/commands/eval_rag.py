"""Score the retrieval pipeline against eval/golden_questions.yaml.

Runs the real configured providers against the seeded data and writes
eval/report.md. The headline number is ISOLATION VIOLATIONS, which must be 0:
a citation from a machine other than the one asked about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from apps.assistant.models import QueryLog
from apps.assistant.services.rag import ask
from apps.machines.models import Machine

QUESTIONS_PATH = Path(settings.BASE_DIR) / "eval" / "golden_questions.yaml"
REPORT_PATH = Path(settings.BASE_DIR) / "eval" / "report.md"
EVAL_USERNAME = "eval_runner"


@dataclass
class Outcome:
    machine: str
    question: str
    expected_status: str
    actual_status: str
    status_ok: bool
    citation_ok: bool
    phrases_ok: bool
    isolation_violations: int
    latency_ms: int
    cited: list[str] = field(default_factory=list)
    missing_phrases: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status_ok and self.citation_ok and self.phrases_ok


def _ratio(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _mark(value: bool) -> str:
    return "ok" if value else "FAIL"


class Command(BaseCommand):
    help = "Run the golden question set and write eval/report.md."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--questions",
            default=str(QUESTIONS_PATH),
            help="Path to the golden question file.",
        )

    def handle(self, *args, **options) -> None:
        items = self._load(Path(options["questions"]))
        user = self._eval_user()
        outcomes = [self._run_one(user, item) for item in items]
        totals = self._totals(outcomes)
        self._print_table(outcomes)
        self._print_totals(totals)
        REPORT_PATH.write_text(self._report(outcomes, totals), encoding="utf-8")
        self.stdout.write(f"\nreport written to {REPORT_PATH}")

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            raise CommandError(f"Missing {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = data.get("questions") or []
        if not items:
            raise CommandError(f"{path} contains no questions.")
        return items

    def _eval_user(self) -> User:
        """A dedicated inactive user, so eval runs stay separable in the history."""
        user, _ = User.objects.get_or_create(
            username=EVAL_USERNAME, defaults={"is_active": False}
        )
        return user

    def _run_one(self, user: User, item: dict) -> Outcome:
        machine_id = item["machine"]
        try:
            machine = Machine.objects.get(machine_id=machine_id)
        except Machine.DoesNotExist as exc:
            raise CommandError(
                f"Machine {machine_id} is not registered. Run manage.py seed_demo first."
            ) from exc

        result = ask(user, machine, item["question"])
        log = result.query_log
        expected_status = item["expected_status"]

        cited = [f"{c.document_id} p{c.page_number}" for c in result.citations]
        expected_pairs = {
            f"{entry['document_id']} p{page}"
            for entry in item.get("expected_documents") or []
            for page in entry.get("pages") or []
        }
        if expected_status == QueryLog.STATUS_ANSWERED and expected_pairs:
            citation_ok = bool(cited) and all(pair in expected_pairs for pair in cited)
        else:
            citation_ok = not cited

        phrases = [str(phrase) for phrase in item.get("must_include") or []]
        quotes = " ".join(citation.quote.lower() for citation in result.citations)
        haystack = f"{log.answer_text.lower()} {quotes}"
        missing = [phrase for phrase in phrases if phrase.lower() not in haystack]

        violations = sum(
            1
            for citation in result.citations
            if citation.chunk is not None and citation.chunk.machine_id != machine.pk
        )

        return Outcome(
            machine=machine_id,
            question=item["question"],
            expected_status=expected_status,
            actual_status=log.status,
            status_ok=log.status == expected_status,
            citation_ok=citation_ok,
            phrases_ok=not missing,
            isolation_violations=violations,
            latency_ms=log.latency_ms_total,
            cited=cited,
            missing_phrases=missing,
        )

    @staticmethod
    def _totals(outcomes: list[Outcome]) -> dict:
        total = len(outcomes)
        answered = [
            outcome
            for outcome in outcomes
            if outcome.expected_status == QueryLog.STATUS_ANSWERED
        ]
        return {
            "total": total,
            "status_accuracy": _ratio(sum(o.status_ok for o in outcomes), total),
            "citation_precision": _ratio(
                sum(o.citation_ok for o in answered), len(answered)
            ),
            "phrase_hit_rate": _ratio(sum(o.phrases_ok for o in answered), len(answered)),
            "isolation_violations": sum(o.isolation_violations for o in outcomes),
            "average_latency_ms": round(
                sum(o.latency_ms for o in outcomes) / total if total else 0.0, 1
            ),
        }

    def _print_table(self, outcomes: list[Outcome]) -> None:
        header = "machine   expected               actual                 st  cit  phr  question"
        self.stdout.write(header)
        for outcome in outcomes:
            style = self.style.SUCCESS if outcome.passed else self.style.ERROR
            self.stdout.write(
                style(
                    f"{outcome.machine:<9} {outcome.expected_status:<22} "
                    f"{outcome.actual_status:<22} {_mark(outcome.status_ok):<3} "
                    f"{_mark(outcome.citation_ok):<4} {_mark(outcome.phrases_ok):<4} "
                    f"{outcome.question[:58]}"
                )
            )

    def _print_totals(self, totals: dict) -> None:
        self.stdout.write("")
        self.stdout.write(f"questions            {totals['total']}")
        self.stdout.write(f"status accuracy      {totals['status_accuracy']:.1%}")
        self.stdout.write(f"citation precision   {totals['citation_precision']:.1%}")
        self.stdout.write(f"key-phrase hit rate  {totals['phrase_hit_rate']:.1%}")
        self.stdout.write(f"average latency      {totals['average_latency_ms']} ms")
        violations = totals["isolation_violations"]
        style = self.style.SUCCESS if violations == 0 else self.style.ERROR
        self.stdout.write(style(f"ISOLATION VIOLATIONS {violations}"))

    @staticmethod
    def _report(outcomes: list[Outcome], totals: dict) -> str:
        lines = [
            "# ManualMind evaluation report",
            "",
            f"- Embedding provider: {settings.EMBEDDING_PROVIDER} / {settings.EMBEDDING_MODEL}",
            f"- LLM provider: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}",
            f"- Vector backend: {settings.VECTOR_BACKEND}",
            f"- RETRIEVAL_MIN_SCORE: {settings.RETRIEVAL_MIN_SCORE}",
            "",
            "## Totals",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Questions | {totals['total']} |",
            f"| Status accuracy | {totals['status_accuracy']:.1%} |",
            f"| Citation precision | {totals['citation_precision']:.1%} |",
            f"| Key-phrase hit rate | {totals['phrase_hit_rate']:.1%} |",
            f"| Average latency | {totals['average_latency_ms']} ms |",
            f"| Isolation violations | {totals['isolation_violations']} |",
            "",
            "## Per question",
            "",
            "| Machine | Question | Expected | Actual | Status | Citations | Phrases | Cited |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for outcome in outcomes:
            cited = ", ".join(outcome.cited) or "-"
            lines.append(
                f"| {outcome.machine} | {outcome.question} | {outcome.expected_status} "
                f"| {outcome.actual_status} | {_mark(outcome.status_ok)} "
                f"| {_mark(outcome.citation_ok)} | {_mark(outcome.phrases_ok)} | {cited} |"
            )

        failures = [outcome for outcome in outcomes if not outcome.passed]
        if failures:
            lines += ["", "## Items to look at", ""]
            for outcome in failures:
                detail = []
                if not outcome.status_ok:
                    detail.append(f"status {outcome.actual_status}")
                if not outcome.citation_ok:
                    detail.append("cited " + (", ".join(outcome.cited) or "nothing"))
                if outcome.missing_phrases:
                    detail.append("missing " + ", ".join(outcome.missing_phrases))
                lines.append(
                    f"- {outcome.machine}: {outcome.question} ({'; '.join(detail)})"
                )
        return "\n".join(lines) + "\n"
