# Manufacturing Manual Assistant: Winning Strategy + Claude Code Build Prompt

> **Before you use this:** the brief says the college will announce its policy on AI coding assistants and reused code. Check that policy first. Every member must also be able to explain their own part, so read what Claude Code produces; don't just run it.

---

## Part A: Strategy (read as a team, 5 minutes)

### Why most teams will look the same
Nearly every team will build the same thing: upload a PDF, chunk it, embed it, top-k search, send it to the LLM, show the answer. The judges will see that 10+ times. You won't win by having a different idea. You win by doing the **same idea with the habits of a production RAG system** (the approach used by Perplexity-style cited search and enterprise document assistants), and by **proving** it works while the judges watch.

### The 6 differentiators (each one is a talking point)

| # | Differentiator | What judges see | Why others won't have it |
|---|---|---|---|
| 1 | **Machine isolation enforced in the database**: the `machine_id` filter goes inside the SQL `WHERE` of the vector query, never applied afterwards in Python | Ask "What does E17 mean?" on HP-200, then on AC-90, and get two different correct answers | Most teams filter after retrieval or rely on the prompt |
| 2 | **Citations grounded by code**: the LLM returns chunk IDs plus quotes. The server only accepts chunk IDs that were actually retrieved, and the text shown as the "quote" always comes from the stored chunk (verbatim match, else closest excerpt). Each source card also shows a **rendered image of the cited PDF page** | "We can't show a source that isn't in the manual", with the physical page right there | Most teams trust whatever the LLM writes and just link to a PDF |
| 3 | **Two-gate "insufficient evidence"**: a retrieval-score gate *and* the LLM's structured verdict. If either fails, the answer is not shown | Pump price, torque, and other-machine questions get a clean, honest refusal | Most teams let the LLM ramble |
| 4 | **Hybrid search**: vector + Postgres full-text, fused with RRF | Exact codes like `E42`, `RF-20` and `AF-10` are always found | Pure-vector search often misses codes |
| 5 | **Live evaluation scoreboard**: `python manage.py eval_rag` runs a golden question set and prints accuracy, citation correctness and isolation violations (= 0) | You show *measured* quality, not a claim | Almost nobody evaluates their RAG |
| 6 | **Supervisor "Knowledge Gaps" view**: unanswered questions grouped by machine, plus latency and model stats per query | The business story: "this tells the plant which manuals are missing information" | Most teams stop at a history table |

### The non-technical winning layer
- **Safety-first product voice.** The manuals repeat that the AI *cannot authorize operation or return-to-service*. Show a persistent banner and have the assistant say so. Judges in manufacturing care about this more than about algorithms.
- **Every member owns a role.** The presentation needs Admin, Engineer and Supervisor, so split the build the same way (see Part C). Each person demos and explains the part they built.
- **Scalability story (one slide, 30 seconds):** "Retrieval sits behind a `VectorStore` interface: machine-prefiltered numpy cosine search today (instant at manual-corpus size, zero extra infrastructure), and a pgvector + HNSW backend one env switch away when the corpus grows. Ingestion is idempotent (SHA-256), revision-aware, and already sits behind a task interface that moves to Celery in Phase 2. LLM and embedding providers can be swapped through `.env`. The API is versioned (`/api/v1`) and stateless, and every row carries a `plant` field so the system is multi-site-ready."
- **Phase 2 head start.** The base is built so Phase 2 (visual inspection with Celery/Redis) plugs in as a new Django app that reuses auth, roles, layout and Docker Compose.

---

## Part B: The prompt (paste everything between the lines into Claude Code)

Put the student pack folder (with `Manuals/`, `machine_manual_index.csv`, etc.) in the project root as `student_pack/` first.

---

````text
You are building the BASE version of a hackathon project. Build a correct, demo-ready foundation with clean seams for later optimization. Do NOT spend time on the items in the "OPTIMIZATION BACKLOG" section. Leave them as TODO-OPT comments at the right seams.

Work in plan mode first: read this whole prompt, inspect ./student_pack, then present a short plan with milestones. After I approve, build milestone by milestone. At the end of each milestone: run the tests, fix failures, and make a git commit with a clear message. Create a CLAUDE.md that summarizes the architecture, commands and conventions so future sessions stay consistent.

# 1. PRODUCT

Name: "ManualMind" (placeholder; keep it in one settings constant).
A Django web app where:
- Administrator: logs in, registers machines, uploads PDF manuals with document ID, title, model and revision. Ingestion extracts the text page by page and indexes it.
- Engineer: logs in, selects a machine, asks a maintenance question, and gets a grounded answer with citations (supporting passage, document ID + title, revision, PDF page number, and a link that opens the PDF at that page). Can revisit their own saved Q&A history.
- Supervisor: read-only view of all question history, filterable, with an "Unanswered / Knowledge Gaps" view.
Roles are enforced on the SERVER (DRF permission classes), never only in the UI.

# 2. MANDATORY STACK (fixed by the hackathon rules, do not substitute)

- Frontend: Django templates + HTML/CSS/vanilla JavaScript + Bootstrap 5 (CDN). Pages call the DRF APIs with fetch() (session auth + CSRF). No React/Vue.
- Backend: Django 5.x + Django REST Framework. API prefix /api/v1/.
- DB: PostgreSQL 16 (psycopg 3). Embeddings are stored in a plain `ArrayField(FloatField)`, so the whole app runs on stock Postgres with NO extension. pgvector is an optional upgrade (see "Vector backend" below).
- PDF: PyMuPDF (`import pymupdf`).
- Auth: Django auth, with Groups "Administrator", "Engineer", "Supervisor". Django admin is allowed for admin tasks, but also build a simple admin upload page.
- Tests: pytest + pytest-django.
- Docker Compose with: postgres (use the pgvector/pgvector:pg16 image, but nothing may fail if the extension is not enabled) and web. Add a commented-out redis service with a note "enabled in Phase 2 for Celery".
- Config through .env (django-environ). Provide .env.example. NEVER commit real keys.

Vector backend: `VECTOR_BACKEND=numpy` is the DEFAULT (zero-risk). Implement a `VectorStore` interface with two backends.
- `numpy` (default): query `Chunk.objects.filter(machine_id=selected, manual__is_active=True, manual__status="INDEXED")` in SQL FIRST, load only those embeddings into a numpy matrix, and compute cosine similarity there. L2-normalise embeddings at ingestion so scoring is one matrix-vector product.
- `pgvector` (optional): used only when VECTOR_BACKEND=pgvector AND the extension initialises cleanly. `CREATE EXTENSION IF NOT EXISTS vector` lives in a separate optional step that is skipped when the backend is numpy. Query with `ORDER BY embedding::vector <=> %s::vector` and the same machine filter in the WHERE clause (TODO-OPT: HNSW expression index).
- In BOTH backends the machine filter happens in the database query, never after scoring. The /health/ check reports which backend is active.

# 3. PROJECT STRUCTURE

manualmind/            (project: settings, urls)
apps/accounts/         (roles, permissions, seed users, login/logout pages)
apps/machines/         (Machine model + APIs)
apps/manuals/          (Manual, Chunk models, upload API, ingestion service, secure PDF serving)
apps/assistant/        (retrieval, LLM providers, answer pipeline, QueryLog, history APIs)
apps/supervisor/       (history + knowledge-gap views/APIs)
apps/core/             (base templates, safety banner, utilities, health check)
templates/, static/
tests/
eval/golden_questions.yaml + management command eval_rag
Phase 2 will add apps/inspection/. Keep shared things (roles, base layout, API conventions) in accounts/core so they can be reused.

# 4. DATA MODEL (with migrations)

Machine: machine_id (unique slug, e.g. "M-HP200"), model ("HP-200"), name, plant (default "PLANT-1"), is_active, created_at.
Manual: document_id (unique, e.g. "HP-OPS-01"), machine FK, title, revision (string, e.g. "1.0"), file (FileField, stored under MEDIA_ROOT/manuals/, NOT publicly served), sha256 (unique per machine+revision), page_count, status (PENDING|INDEXED|FAILED), error_message, is_active, uploaded_by, created_at. The same document_id with a new revision supersedes the old one (old is_active=False). Several manuals for one machine can be active at once (they are complementary).
Chunk: manual FK, machine FK (DENORMALIZED for fast filtering, indexed), page_number (1-based PDF page), section_title, text, content_hash, char_start/char_end within the page, embedding (ArrayField(FloatField), L2-normalised, length = settings.EMBEDDING_DIM), search_vector (SearchVectorField + GIN index). Index machine + manual. (TODO-OPT: pgvector HNSW index when VECTOR_BACKEND=pgvector.)
QueryLog: user FK, machine FK, question, answer_text, status (ANSWERED | INSUFFICIENT_EVIDENCE | ERROR), retrieved_chunk_ids (JSON), top_score, llm_provider, llm_model, embedding_model, latency_ms_retrieval, latency_ms_llm, created_at.
QueryCitation: query FK, chunk FK, manual FK, document_id, revision, page_number, quote (always text from the stored chunk), quote_verified (bool), order.
AuditLog (small): user, action (UPLOAD, INGEST, DENIED_UPLOAD, LOGIN, ...), target, created_at. Log denied upload attempts. That gives a nice demo moment.

# 5. INGESTION (apps/manuals/services/ingest.py)

- Validate the upload: PDF only (check magic bytes "%PDF", not just the extension), max 20 MB, required metadata present, machine exists.
- Compute sha256. If the identical file is already indexed for that machine and revision, it's a no-op (idempotent).
- Extract with PyMuPDF page by page: page_number = index + 1. Use page.get_text("blocks") or "dict" to keep reading order. Detect section headings with a simple heuristic (short line, larger font or bold, no trailing period). Keep table rows together on one line ("Parameter | Value").
- Chunking: split within a page only (a chunk never crosses pages), by section, target ~500-900 chars, with a ~100-char overlap. Prefix each chunk's embedded text with context: "[{model} | {document_id} rev {revision} | page {n} | {section}]". Store the original text separately for display and quote verification.
- Strip repeated footer lines like "HP-OPS-01 | Rev 1.0 | Page 1" from the chunk text, but keep the page number in metadata.
- Embed in batches and save in a transaction. Set status INDEXED or FAILED with a readable error.
- Run ingestion through a thin task interface: `run_ingestion(manual_id)` called synchronously now, with a TODO-OPT note "dispatch via Celery .delay() in Phase 2". Keep it pure and testable.
- Only index what is uploaded through the app. Never index the challenge brief, START_HERE.txt or the CSV.

# 6. PROVIDERS (swappable through .env; model access is announced on event day)

apps/assistant/providers/:
- EmbeddingProvider interface: embed_documents(list[str]) -> list[list[float]], embed_query(str), name, dim.
  Implementations: OpenAICompatibleEmbeddings (base_url + api_key + model, which covers OpenAI, Azure-style gateways, Ollama /v1, LM Studio), GeminiEmbeddings (optional), SentenceTransformersEmbeddings (local, e.g. BAAI/bge-small-en-v1.5, 384-dim), FakeEmbeddings (deterministic hashing-based, for tests).
- LLMProvider interface: generate_json(system, user, schema) -> dict.
  Implementations: OpenAICompatibleLLM (JSON mode / response_format), GeminiLLM (optional), AnthropicLLM (optional), FakeLLM (for tests; returns schema-valid output built from the given chunks).
- EMBEDDING_DIM must match the embedding provider. Validate this at startup and fail with a clear message on a mismatch. Document in the README that changing the embedding model requires `python manage.py reindex_all`.
- Timeouts (30 s), 1 retry, and clear error messages. An LLM failure gives status=ERROR with a friendly UI message, never a fake answer.

# 7. RETRIEVAL + ANSWER PIPELINE (apps/assistant/services/rag.py). THIS IS THE CORE, BUILD IT CAREFULLY.

Input: user, machine_id, question.
Step 1. Normalize and analyze the query: extract alarm codes (regex E\d{2}), part identifiers (e.g. [A-Z]{2}-\d{2}), and model names mentioned. If the question explicitly names a DIFFERENT registered machine model than the selected one, still run retrieval only on the selected machine, and add a UI hint: "Your question mentions AC-90 but HP-200 is selected. Switch machine to ask about it." The hint must NOT reveal any content from the other machine.
Step 2. Hybrid retrieval, ALWAYS filtered by machine_id (and manual is_active=True, status=INDEXED) INSIDE the database query:
   a) Vector search: top 12 by cosine similarity through the active VectorStore backend (numpy by default, pgvector optional), with chunk.machine_id = selected applied in the database query.
   b) Keyword search: Postgres full-text (websearch_to_tsquery) top 12, same WHERE. Also boost exact matches of the extracted codes/part IDs (ILIKE) with the same filter.
   c) Fuse with Reciprocal Rank Fusion (k=60) and take the top 6 as context. Keep raw vector similarity for the gate.
   Put retrieval behind a VectorStore/Retriever class so it can be swapped (TODO-OPT: reranker).
Step 3. Evidence gate 1: if there are no chunks, or the best vector similarity is below RETRIEVAL_MIN_SCORE (configurable, calibrate it with the eval set) AND there's no exact code/part match, return INSUFFICIENT_EVIDENCE without calling the LLM.
Step 4. Generation: send the chunks as a numbered list with chunk_id, document_id, revision, page and text. System prompt rules (write them strictly):
   - Answer ONLY from the provided passages, which all belong to machine {model}. No general knowledge.
   - If the passages don't contain the answer, set status "INSUFFICIENT_EVIDENCE". This includes the case where a passage says the information is "not provided".
   - When the answer needs passages from several documents, cite each of them.
   - Every factual sentence must be supported by a citation, with the quote copied EXACTLY from the passage (a short verbatim span, under 300 chars).
   - Respect "whichever occurs first" logic and exact thresholds; don't round or convert units.
   - Never state or imply that the assistant authorizes operation, repair or return to service.
   - Output JSON: {"status": "ANSWERED"|"INSUFFICIENT_EVIDENCE", "answer": str, "citations": [{"chunk_id": int, "quote": str}], "record_before_escalation": [str] (only if the passages list such items, else [])}
Step 5. Evidence gate 2, CITATION VERIFICATION in code:
   - Drop any citation whose chunk_id was not in the provided context (an invented chunk_id is never accepted).
   - For each remaining citation, normalize whitespace/quotes/dashes and check that the quote is a substring of that chunk's stored text. If not, try a fuzzy match (difflib ratio ≥ 0.9 on a sliding window) and use the matched span. If that also fails (the LLM paraphrased), DO NOT drop the citation: replace the quote with the first 200 characters of the stored chunk text and set quote_verified=false. The text displayed as a quote must ALWAYS be copied from the stored chunk, never the LLM's own wording.
   - If the LLM returns ANSWERED with at least one citation whose chunk_id is in the retrieved context, NEVER downgrade to INSUFFICIENT_EVIDENCE just because exact string matching failed.
   - Downgrade to INSUFFICIENT_EVIDENCE only if status is ANSWERED but zero citations have a valid chunk_id.
   - If status is INSUFFICIENT_EVIDENCE, show this standard message: "The available manuals for {model} do not contain enough information to answer this question." Don't show partial content.
Step 6. Persist the QueryLog + QueryCitations (including insufficient and error cases) with latencies and model names. Return the API response.

# 8. API (DRF, /api/v1/, session auth, consistent JSON errors)

POST /auth/login, POST /auth/logout, GET /auth/me (returns username + role)
GET /machines/ (all authenticated users), POST /machines/ (Administrator only)
GET /manuals/?machine=, POST /manuals/ (multipart; Administrator only → 403 for others + AuditLog DENIED_UPLOAD), POST /manuals/{id}/reindex/ (Administrator)
GET /manuals/{id}/pdf/ (any authenticated user; streams the file through Django with Content-Disposition inline; never a public media URL)
GET /manuals/{id}/page/{page_number}/preview/ (any authenticated user; renders that page of the stored PDF with PyMuPDF: `page.get_pixmap(dpi=150).tobytes("png")`, returned as image/png. Validate 1 <= page_number <= page_count else 404; only for manuals the user may see; add a short Cache-Control max-age; TODO-OPT: disk cache keyed by sha256+page)
POST /assistant/ask/ {machine_id, question} (Engineer only; also allow Administrator for testing if simple)
GET /assistant/history/ (Engineer: only their own queries; Supervisor/Administrator: all) with filters: machine, status, date range, search text; paginated
GET /assistant/history/{id}/ (the same ownership rules)
GET /supervisor/knowledge-gaps/ (Supervisor/Administrator): INSUFFICIENT_EVIDENCE queries grouped by machine, with counts and the latest examples
GET /health/ (DB + provider config check)
Write the permission classes once (IsAdministrator, IsEngineer, IsSupervisor, IsSupervisorOrAdmin) in accounts/permissions.py and reuse them.

# 9. UI PAGES (Bootstrap 5; clean, professional, industrial look; works on a laptop projector)

- Login page. After login, redirect by role.
- Top navbar shows the user, a role badge, and only the links that role is allowed to use (the server still enforces access).
- Persistent safety banner: "Fictional training dataset. Answers summarize the manuals; they do not authorize operation, repair, or return to service."
- Admin: machines list + register form; manuals list with status badges (PENDING/INDEXED/FAILED, page count, chunk count) + upload form (machine dropdown, document ID, title, revision, file) + reindex button.
- Engineer "Ask": a machine selector (required, shown prominently as a coloured pill so the selected machine is always visible), question box, and 4 clickable example questions. Answer card: status badge (green ANSWERED / amber INSUFFICIENT EVIDENCE / red ERROR), answer text, an optional "Record before escalation" checklist, and Source cards (document ID + title, Rev, Page N, the verified quote highlighted, an INLINE IMAGE of the cited page (`<img src="/api/v1/manuals/{id}/page/{N}/preview/">`, shown beside the quote, click to enlarge in a Bootstrap modal so judges see the physical page proof immediately), and an "Open PDF at page N" button → /api/v1/manuals/{id}/pdf/#page=N in a new tab). Show "answered in X.Xs".
- Engineer "My History": table → click to reopen the full stored answer with its citations.
- Supervisor "Question Log": read-only table with filters (machine, status, date, text) + a "Knowledge Gaps" tab showing unanswered questions grouped by machine with counts.
- Show friendly empty states and error toasts. No stack traces in the UI.

# 10. SEED + DEMO RELIABILITY

management command `seed_demo`:
- Creates the groups and three users: admin1 / engineer1 / supervisor1 (passwords from .env, with defaults like "Demo@1234" documented in the README).
- Reads student_pack/machine_manual_index.csv (columns: machine_id, model, machine_name, document_id, revision, pdf_filename) and creates the machines and manuals, ingesting the PDFs from student_pack/Manuals/.
- Is idempotent (safe to run twice).
- Flag `--no-manuals` so the Admin upload can be shown live during the demo.
Known pack contents (for reference only; do NOT hardcode answers in the app code):
  M-HP200 / HP-200 / Hydraulic forming press: HP-OPS-01 rev 1.0 (HP200_Operations_Rev1_0.pdf), HP-MNT-01 rev 1.0 (HP200_Maintenance_Rev1_0.pdf), complementary
  M-AC90 / AC-90 / Air compressor: AC-OM-01 rev 1.0 (AC90_Operations_Maintenance_Rev1_0.pdf)
  Each PDF has 3 pages; PDF page numbers = printed page labels.

# 11. TESTS (pytest; run with FakeEmbeddings + FakeLLM so no API keys are needed)

Required by the brief, these must exist and pass:
  test_engineer_cannot_upload_manual: an Engineer POST to /api/v1/manuals/ gets 403, no Manual is created, and an AuditLog DENIED_UPLOAD is written. (Also: a Supervisor gets 403, an anonymous user gets 401/403, an Administrator gets 201.)
  test_retrieval_excludes_other_machine: ingest small synthetic manuals for two machines, both containing the code "E17" with different meanings. Retrieval for machine A returns ONLY machine A chunks, for vector, keyword and fused results alike, and that holds even for a query that literally contains machine B's unique text.
Additional tests:
  - citation grounding: a chunk_id outside the context is dropped; a paraphrased or fabricated quote with a VALID chunk_id is kept but replaced by real chunk text (first 200 chars) with quote_verified=false, and the answer stays ANSWERED; ANSWERED with zero valid chunk_ids is downgraded to INSUFFICIENT_EVIDENCE.
  - page preview: returns a PNG for a valid page, 404 for page 0 or page_count+1, and requires login.
  - vector backend: with VECTOR_BACKEND=numpy the app works with no pgvector extension installed.
  - gate 1: a low-score retrieval returns INSUFFICIENT_EVIDENCE and the LLM is not called (mock asserts no call).
  - history isolation: engineer1 cannot read engineer2's query (404); a Supervisor can read all of them; a Supervisor cannot POST /ask (403).
  - persistence: every /ask call creates a QueryLog with the correct status and citations.
  - ingestion: page numbers are 1-based; re-uploading an identical file is a no-op; a non-PDF with a .pdf extension is rejected.
  - PDF serving requires login.
Write test output to test-results.txt too (needed for submission).

# 12. EVALUATION HARNESS (eval/golden_questions.yaml + `python manage.py eval_rag`)

Uses the REAL configured providers on the seeded data. For each item: machine, question, expected_status, expected_documents (+ pages), and must_include key phrases. Report a table per question and these totals: status accuracy, citation precision (cited doc+page ∈ expected), key-phrase hit rate, ISOLATION VIOLATIONS (any cited chunk from another machine; must be 0), and average latency. Save the report as eval/report.md. Seed it with:
  - HP-200 | What does E17 mean? | ANSWERED | HP-OPS-01 p2 | "low hydraulic pressure", "110 bar"
  - AC-90 | What does E17 mean? | ANSWERED | AC-OM-01 p2 | "high discharge temperature"
  - HP-200 | What is the normal operating pressure range? | ANSWERED | HP-OPS-01 p1 | "120", "140"
  - AC-90 | What is the normal operating pressure range? | ANSWERED | AC-OM-01 p1 | "7.0", "8.0"
  - HP-200 | How often is the filter checked? | ANSWERED | HP-MNT-01 p2 | "50", "RF-20"
  - AC-90 | How often should the AF-10 filter indicator be checked, and when is the planned filter replacement due? | ANSWERED | AC-OM-01 p3 | "100", "600"
  - HP-200 | What triggers E17 and what should be inspected first? | ANSWERED | HP-OPS-01 p2 AND HP-MNT-01 p3 | "110 bar", "reservoir"
  - HP-200 | What does E31 mean? | ANSWERED | HP-OPS-01 p2 | "guard"
  - AC-90 | What does E31 mean? | ANSWERED | AC-OM-01 p2 | "condensate"
  - HP-200 | Oil has been in service 12 months but only 1,400 hours. Is replacement due? | ANSWERED | HP-MNT-01 p2 | "12 months"
  - AC-90 | What should be recorded before escalation? | ANSWERED | AC-OM-01 p3 | "M-AC90"
  - HP-200 | Can the assistant approve return to service? | ANSWERED | HP-MNT-01 p3 | "supervisor"
  - HP-200 | When is the AF-10 filter replaced? | INSUFFICIENT_EVIDENCE (other machine's part)
  - AC-90 | What is the H46 oil replacement interval? | INSUFFICIENT_EVIDENCE (other machine)
  - HP-200 | What is the pump replacement price? | INSUFFICIENT_EVIDENCE
  - AC-90 | What is the tightening torque for the motor mount? | INSUFFICIENT_EVIDENCE
  - HP-200 | What is the capital of France? | INSUFFICIENT_EVIDENCE
Use the results to calibrate RETRIEVAL_MIN_SCORE and the system prompt. NEVER special-case these questions in the app code; judges will use unseen questions.

# 13. NON-FUNCTIONAL

- Security: CSRF on; login_required everywhere; uploaded files never under a public static path; filenames sanitized/UUID-renamed; DEBUG from env; secrets only from env; ALLOWED_HOSTS from env.
- Structured logging (one log line per /ask with machine, status, latencies; no secrets).
- Type hints, docstrings on services, small functions. Business logic lives in services/, not in views.
- Pin requirements in requirements.txt.

# 14. DELIVERABLES

- README.md: what it is; quick start (Docker and non-Docker); .env setup for each provider; `migrate`, `seed_demo`, `runserver`, `pytest`, `eval_rag` commands; demo credentials; an architecture section with a Mermaid diagram (Browser → Django/DRF → services → Postgres+pgvector / LLM API); "How isolation and citation verification work" (5 bullets); "Scalability" (machine-prefiltered numpy search by default with a pgvector/HNSW switch, idempotent revision-aware ingestion, Celery-ready task seam, provider abstraction, versioned stateless API, plant field); "Phase 2 reuse plan"; known limitations.
- test-results.txt and eval/report.md generated.
- docs/DEMO_SCRIPT.md: a 7-minute demo with the exact questions (taken from the demonstration checklist: a supported question + open the page, a two-HP-200-manual question, an other-machine question, an unanswerable question, an Engineer upload denial, reopening history), split across the Administrator / Engineer / Supervisor presenters.

# 15. MILESTONES (commit after each; keep the app runnable at every commit)

M0 Scaffold: project, Docker Compose, settings/env, apps, base template, health check, pytest config.
M1 Auth + roles + Machine/Manual models + permissions + seed users + the upload-denied test.
M2 Ingestion (PyMuPDF, chunking, embeddings via providers) + secure PDF serving + page-preview PNG endpoint + Admin UI + seed_demo.
M3 Retrieval (hybrid, machine-filtered) + the isolation test.
M4 Generation + citation verification + gates + QueryLog + Engineer Ask UI + history.
M5 Supervisor log + knowledge gaps.
M6 Eval harness + calibration + README + demo script + full test run.
If time is short, M0–M4 plus the two required tests are the MUST-HAVES. Report progress against this list.

# 16. OPTIMIZATION BACKLOG (do NOT build now; leave TODO-OPT seams)

- Cross-encoder reranker (e.g. bge-reranker) after RRF.
- PDF.js viewer that highlights the exact quote on the page.
- Streaming answers (SSE).
- Query-embedding cache and answer cache keyed by (machine, normalized question, index version).
- Celery async ingestion with progress (Phase 2 infrastructure).
- Engineer thumbs-up/down feedback feeding the eval set.
- Query rewriting/multi-query for vague questions.
- Per-plant tenancy enforcement, rate limiting, token-cost tracking dashboard.
- OCR for scanned PDFs (out of scope for this round).

Start now: inspect ./student_pack, then show me the plan.
````

---

## Part C: Team split (3 members = the 3 presenter roles)

| Member | Builds | Presents as | Can explain |
|---|---|---|---|
| **A** | Auth, roles, permissions, machines, manuals upload, ingestion (PyMuPDF + chunking), seed_demo, AuditLog | **Administrator** | Live upload → INDEXED; page-number preservation; idempotent and revision-aware ingestion; the upload-denied test |
| **B** | Providers, hybrid retrieval, RAG pipeline, citation verifier, gates, Engineer UI | **Engineer** | The isolation-in-SQL design, citation verification, insufficient evidence, E17 on both machines |
| **C** | History APIs, Supervisor log + Knowledge Gaps, tests, eval harness, README, demo script | **Supervisor** | History and gaps, `pytest` output, the **eval scoreboard (0 isolation violations)**, the scalability slide |

**Time plan (6.5 h):** 0:00–0:30 environment + M0 · 0:30–1:30 M1 · 1:30–3:00 M2 + M3 · 3:00–4:30 M4 · 4:30–5:15 M5 · 5:15–6:00 M6 + calibration · 6:00–6:30 freeze, run seed + tests + eval, commit/ZIP. **Do not start backlog items before 5:15.**

## Part D: Before the event (the brief says environments must be ready beforehand)

- [ ] Docker + `pgvector/pgvector:pg16` image pulled (pgvector is optional; the app runs on stock Postgres with the default numpy backend)
- [ ] Python 3.11/3.12 venv with requirements installed; if you use local embeddings, download the model once in advance
- [ ] Test an OpenAI-compatible endpoint plus a fallback (local Ollama if allowed)
- [ ] Rehearse the 7-minute demo twice; have `seed_demo` ready in case a live upload fails
- [ ] Prepare answers to likely judge questions: *"What if the LLM invents a page?"* (verifier) · *"How do you stop AC-90 leaking into HP-200?"* (SQL WHERE + test + eval) · *"How does this scale to 10,000 manuals?"* (machine-prefiltered search, one-switch pgvector/HNSW backend, async ingestion) · *"Why hybrid search?"* (exact alarm codes)
