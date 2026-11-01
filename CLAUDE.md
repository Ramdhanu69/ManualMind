# ManualMind: working notes for future sessions

Django 5 + DRF app that answers maintenance questions from equipment manuals with
verified citations. Read `README.md` first for the product and the commands; this
file records the conventions and the decisions that are easy to break.

## Layout

```
manualmind/          settings, urls, wsgi
apps/core/           AuditLog, health check, base templates, forbidden page
apps/accounts/       roles.py (Group names), permissions.py, login + auth API, seed_demo
apps/machines/       Machine model + API
apps/manuals/        Manual, Chunk, upload API, secure PDF + page PNG,
                     services/extract.py (PDF to text), services/ingest.py (pipeline)
apps/assistant/      QueryLog, QueryCitation, ask + history API,
                     providers/ (embeddings, llm, http), services/rag.py,
                     services/vectorstore.py, services/citations.py, eval_rag
apps/supervisor/     knowledge gaps + stats API, question log page
templates/, static/  Django templates, app.css, api.js + one JS file per page
tests/               pytest, runs on FakeEmbeddings + FakeLLM
eval/                golden_questions.yaml, report.md
student_pack/        the supplied manuals and index CSV. Never index anything else
```

## Conventions

- Business logic goes in `services/`. Views validate, call a service, serialise.
- Role checks use the classes in `apps/accounts/permissions.py`. Never check a
  role inline in a view body, and never rely on the template hiding a link.
- API paths live under `/api/v1/`. Errors are `{"detail": str, "errors": {...}}`
  via `apps/core/exceptions.py`.
- Type hints on service functions. Comments explain *why*, not *what*.
- Page JavaScript lives in `static/js/<page>.js` and uses the helpers in
  `api.js` (`mmFetch`, `mmToast`, `mmEscape`, `mmSourceCard`, ...). Values are
  escaped before being put into HTML.
- `TODO-OPT` marks a deliberate optimisation seam from the build brief. Leave
  them; they are the scalability story.

## Rules that must not be broken

1. **The machine filter belongs in the database query.** Start every retrieval
   from `rag.machine_chunks(machine)`. If you add a retrieval path, it must use
   that queryset. `tests/test_retrieval.py::test_retrieval_excludes_other_machine`
   checks the vector, keyword, exact and fused paths separately.
2. **Never display a quote the model wrote.** `services/citations.py` always
   returns a span of the stored chunk text. A paraphrase keeps the citation and
   clears `quote_verified`; it does not invent a quote and does not delete the
   citation.
3. **Never downgrade an answer because string matching failed.** Downgrade only
   when no citation has a chunk id that was actually retrieved.
4. **`page_number` is 1-based** and equals the printed page label. Chunks never
   cross a page.
5. **Uploaded files are never publicly served.** `MEDIA_URL` is intentionally
   unrouted; use the login-protected streaming views.
6. **Do not special-case the golden questions in app code.** The judges use unseen
   questions. Calibrate `RETRIEVAL_MIN_SCORE` and the system prompt instead.

## Things that surprised us

- The PDF tables are grids whose cells wrap independently and are vertically
  centred, so one logical row reaches PyMuPDF as several lines whose baselines
  interleave with the neighbouring row. Line pitch cannot separate a wrapped cell
  (13.2 pt here) from a wrapped paragraph (14.5 pt). `extract.py` therefore
  classifies a line as table content by its *x* offset from the prose margin, then
  anchors rows on the first column. `page.find_tables()` segfaults in PyMuPDF 2.0,
  so it is not an option.
- `EMBEDDING_DIM` mismatches are silent and poisonous, so
  `providers.check_provider_config()` runs from `AssistantConfig.ready()`.
- Gate 1 cannot reject out-of-scope questions; the score ranges overlap. See the
  calibration note in `README.md`.
- A DRF permission failure happens before the view body, so the
  `DENIED_UPLOAD` audit row is written from `permission_denied()`.

## Local verification

Needs PostgreSQL 16 (ArrayField, `SearchVectorField`, `websearch_to_tsquery`).
Tests default to `fake` providers, so no API key is required.

```bash
python manage.py check
python -m pytest
python manage.py seed_demo
python manage.py eval_rag
```
