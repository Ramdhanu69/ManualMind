# ManualMind: 7-minute demo script

Three presenters, one role each. Times are cumulative. Keep the safety banner
visible the whole time; it is part of the pitch, not decoration.

**Before you start**

```bash
python manage.py migrate
python manage.py seed_demo --no-manuals   # machines and users only, so the upload is live
python manage.py runserver
```

Have a second terminal ready with `python -m pytest` and
`python manage.py eval_rag` already run, so the output is on screen.
Keep `seed_demo` (without the flag) as the fallback if the live upload fails.

---

## 0:00-0:30 - Framing (Supervisor presents)

> "Two machines, three manuals, and a question that has a different correct answer
> on each machine. Everything you see is tied back to a page of a manual. The
> system is also allowed to say it does not know."

Point at the banner: the assistant summarises manuals, it does not authorize
operation, repair or return to service.

---

## 0:30-2:00 - Administrator

Sign in as `admin1`.

1. **Machines list** already shows `M-HP200` and `M-AC90`.
2. **Upload live.** Machine `M-HP200`, Document ID `HP-OPS-01`, Title
   `HP-200 Operations Manual`, Revision `1.0`, file
   `student_pack/Manuals/HP200_Operations_Rev1_0.pdf`.
   Say while it runs: *"text is extracted page by page, chunked inside each page,
   embedded, and indexed with a Postgres full-text vector."*
   The row turns **INDEXED** with 3 pages and 16 chunks.
3. Upload `HP200_Maintenance_Rev1_0.pdf` as `HP-MNT-01` and
   `AC90_Operations_Maintenance_Rev1_0.pdf` as `AC-OM-01`.
4. **Upload the same file again.** It reports that the file is already indexed and
   nothing changes.
   > "Ingestion is idempotent on the SHA-256, and a new revision supersedes the
   > old row instead of overwriting it."

**If a judge asks:** page numbers are 1-based and match the printed label; a
chunk never crosses a page, so a citation can always name one real page.

---

## 2:00-4:30 - Engineer

Sign out, sign in as `engineer1`. The machine pill shows the selected machine at
all times.

1. **Supported question.** `HP-200` selected, ask **"What does E17 mean?"**
   Answer is **ANSWERED** with a source card: `HP-OPS-01`, Rev 1.0, Page 2, the
   verified quote, and **an image of that actual page** next to it. Click the image
   to enlarge, then click **Open PDF at page 2**.
   > "The quote is not what the model wrote. The model returns a chunk id and a
   > quote; the server checks the id against what it actually retrieved, finds the
   > quote inside the stored chunk, and displays the stored text."

2. **The isolation moment.** Switch the machine to `AC-90` and ask **the same
   question**: **"What does E17 mean?"**
   A different, correct answer: high discharge temperature, cited to `AC-OM-01`
   page 2.
   > "The machine filter is inside the SQL WHERE clause of the vector query, not
   > applied afterwards in Python. The other machine's passages are never scored."

3. **Two manuals, one answer.** Back to `HP-200`, ask
   **"What triggers E17 and what should be inspected first?"**
   The answer cites `HP-OPS-01` page 2 for the trigger and `HP-MNT-01` page 3 for
   the checks: two complementary manuals, both current.

4. **The other-machine question.** With `HP-200` still selected, ask
   **"When is the AF-10 filter replaced?"**
   Insufficient evidence, plus the hint *"Your question mentions AC-90 but HP-200
   is selected."*
   > "The hint names the machine but reveals nothing from its manual."

5. **The unanswerable question.** Ask **"What is the pump replacement price?"**
   A clean refusal, no partial content.
   > "Two gates: a retrieval-score gate before any model call, and the model's own
   > structured verdict. If either refuses, nothing is shown."

6. **Upload denial.** Open `/admin-console/` as the engineer: refused by the
   server with the role named.
   > "That attempt is now an audit row, `DENIED_UPLOAD`."

7. **My History.** Click a past question and reopen the stored answer with its
   citations intact.

---

## 4:30-6:00 - Supervisor

Sign out, sign in as `supervisor1`.

1. **Question Log.** Every question from every engineer, read-only, filterable by
   machine, status, date and text. Filter to `INSUFFICIENT_EVIDENCE`.
2. **Knowledge Gaps tab.** Unanswered questions grouped by machine with counts,
   plus questions asked, average retrieval latency and the models used.
   > "This is the business output. It tells the plant which manuals are missing
   > information, machine by machine."
3. Try `POST /api/v1/assistant/ask/` as the supervisor: 403. Read-only means
   read-only on the server.

---

## 6:00-7:00 - Measured quality (Supervisor presents)

Switch to the terminal.

1. **`python -m pytest`** - 46 passed, including the two tests the brief requires:
   `test_engineer_cannot_upload_manual` and
   `test_retrieval_excludes_other_machine`.
2. **`python manage.py eval_rag`** - 17 golden questions, and the line that
   matters:

   ```
   ISOLATION VIOLATIONS 0
   ```

   Retrieval recall is 12/12: for every answerable question, the expected document
   and page is inside the 6-passage context.
   > "We measured it rather than claiming it. The report is committed as
   > `eval/report.md`, and we never special-case these questions in the app, because
   > you will ask different ones."

3. **Closing line, 30 seconds on scalability.**
   > "Retrieval sits behind a VectorStore interface: machine-prefiltered numpy
   > search today, pgvector with HNSW one env switch away. Ingestion is idempotent,
   > revision-aware and already behind a task interface that becomes Celery in
   > Phase 2. Providers swap through .env, the API is versioned and stateless, and
   > every machine carries a plant field, so this is multi-site ready."

---

## Likely judge questions

| Question | Answer |
| --- | --- |
| What if the model invents a page? | The chunk id is checked against what was retrieved and dropped if it was not. The quote shown is always a span of the stored chunk. |
| How do you stop AC-90 leaking into HP-200? | The `machine_id` filter is in the SQL `WHERE` of every retrieval path, there is a test for the vector, keyword, exact and fused paths, and `eval_rag` reports isolation violations. |
| How does this scale to 10,000 manuals? | The machine filter runs before scoring, so the scored set tracks one machine. Then the pgvector + HNSW backend, and async ingestion. |
| Why hybrid search? | Pure vector search misses exact alarm codes and part identifiers. The exact `ILIKE` pass plus RRF is what guarantees `E42`, `RF-20` and `AF-10` are found. |
| Why does it refuse so confidently? | The manuals state which details they do not supply, and the system prompt treats "not provided" as insufficient evidence. |
