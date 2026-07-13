# Praxis — Architecture Document

**App:** Personal AI English Learning Coach
**Version:** 1.1 (MVP, patched)
**Baseline:** v1.0 — this document applies a targeted set of refinements on top of v1.0 and does not revisit any decision not listed below
**Platform:** Local web application (Python backend + React frontend), single device, single user
**Architecture Pattern:** Layered service architecture (FastAPI), feature-folder SPA frontend
**Document Status:** Implementation-Ready

---

## Patch Notes (v1.0 → v1.1)

This revision resolves six implementation ambiguities identified during pre-implementation review. Every other decision in this document — including anything not listed here — is unchanged from v1.0. Sections touched by each item are marked inline with a *(v1.1)* tag.

1. **`Correction` split into `LearningCorrection` and `PerformanceError`.** v1.0 conflated two different concepts under one entity. Affects: Executive Summary, ADR-05, Sections 4.1–4.3, 6.2–6.5, 7.
2. **Vault Watcher robustness.** Explicit handling for atomic saves, duplicate filesystem events, debounce, and hash-based dedup. Affects: new ADR-11, Section 6.1.
3. **FTS5 synchronization.** Confirmed and reinforced as trigger-based (this was already the v1.0 design in Section 7.3 — a cross-reference in ADR-02 pointed to the wrong section; fixed here). Affects: ADR-02, Section 7.3.
4. **Deterministic evaluation settings.** New ADR-12 pins low/zero temperature and a fixed seed (where supported) specifically for grading and evaluation calls. Affects: new ADR-12, Section 9.
5. **Evaluation versioning.** New ADR-13 adds evaluator/prompt/rubric version metadata to graded and evaluated rows. Affects: new ADR-13, Section 7.1, Section 9.
6. **Everything else preserved as-is.** No renames, restructuring, or reconsideration beyond what the five items above require.

---

## 1. Executive Summary

Praxis is a local-first application that turns a learner's freeform Obsidian notes into a structured, queryable knowledge base, then uses that knowledge base to generate quizzes, evaluate writing, and produce weekly progress reports. It runs as a single Python process on one laptop: a FastAPI backend owns a SQLite database and a background file-watcher thread, and a React single-page frontend consumes it over a local REST API.

Every AI-generated artifact falls into one of three categories *(v1.1)*: **(a) new knowledge** — parsed vocabulary, learning corrections, suggested phrasing — gated behind an explicit human approval step before it affects the permanent learning record; **(b) performance data** — a record that a specific mistake happened during a quiz or writing task — stored immediately without approval, because it is a factual record of something the learner already did, not new content proposed to them; or **(c) fully ephemeral artifacts** (an in-progress quiz question, a narrative draft) that never persist as authoritative state at all. This rule is enforced structurally, not just by convention: there is exactly one code path (`ApprovalService.approve()`/`approve_edited()`) permitted to insert `LearningItem` or `LearningCorrection` rows, and exactly one pair of call sites (`QuizService.grade_session()`, `WritingService.submit_and_evaluate()`) permitted to insert `PerformanceError` rows. The two paths are kept structurally separate — see ADR-05 — so "new knowledge" and "observed performance" can never be confused in the codebase, even though both can originate from the same underlying AI call.

The system deliberately avoids infrastructure it doesn't need: no task queue, no scheduler library, no vector database, no multi-process deployment, no auth layer. Every one of those omissions is a documented decision (Section 3), not an oversight — and each has a stated, non-blocking path to being added later if real usage proves it necessary.

---

## 2. Architecture Principles

| Principle | What it means in this system |
|---|---|
| **Local-first, single-user** | No network calls except to the configured LLM host. No auth, no multi-tenancy, no cloud dependency for core function. |
| **AI-assisted, not AI-driven** | The AI never writes directly to the permanent knowledge base. It proposes; the learner disposes. This is enforced at the service layer, not just the UI layer — `LearningItem` rows can only be created by `ApprovalService`. |
| **Model-agnostic by construction** | All LLM access goes through the `Generator`/`Evaluator` interface (Section 3, Section 9). No component outside `app/llm/` knows what model or provider is in use. |
| **Event-driven over scheduled** | Every backend action is triggered by something happening (a file save, an HTTP request, an approval action) rather than by wall-clock polling. The one exception (daily backup) is satisfied by a startup check + post-write hook, not a scheduler library (Section 3, ADR-05). |
| **Structural simplicity over premature abstraction** | One process, one database file, one ORM, one frontend framework. Every additional moving part in this document had to justify itself against "could this just be a function call."|
| **Correctness over cleverness in scheduling/grading** | The SM-2-inspired scheduler and mastery decay logic are simple, well-understood, and entirely swappable — they influence *what appears in a quiz*, nothing more consequential. |
| **The database is the source of truth** | The frontend holds no authoritative state. TanStack Query treats every piece of UI data as a cache of server state, not owned client state. |

---

## 3. Architecture Decisions

Each decision below follows: Context → Alternatives Considered → Decision → Trade-offs.

### ADR-01: SQLite as the sole datastore

**Context:** Single user, single device, low write concurrency (one human, occasional background parsing), data volume in the low thousands of rows even after years of use.

**Alternatives considered:**
- PostgreSQL — would require running a separate DB server process, entirely unjustified at this scale.
- A document store (e.g., embedded JSON files per entity) — would lose relational integrity (foreign keys, joins for dashboard aggregation) for no benefit.

**Decision:** SQLite, WAL (Write-Ahead Logging) journal mode, one file at a configurable path (default `data/praxis.db`).

**Trade-offs:** SQLite has weaker concurrent-write guarantees than a server RDBMS, but WAL mode allows one writer + many concurrent readers, which is exactly this system's access pattern (the watcher thread and the API server both write occasionally; the frontend only reads except during explicit user actions). If Praxis ever needs multi-device access, this is the component that changes (Section 15).

### ADR-02: FastAPI + SQLModel

**Context:** Backend needs an async-capable web framework (LLM calls are I/O-bound and benefit from `async`/`await`) and an ORM/schema layer that doesn't duplicate model definitions between "the database shape" and "the API shape."

**Alternatives considered:**
- Flask — simpler, but synchronous by default and would require bolt-on async support for LLM calls.
- Raw `sqlite3` + hand-written SQL — maximally transparent, minimal dependency footprint, but means maintaining two parallel definitions of every entity (DB row shape and Pydantic API schema) — direct duplication risk as the schema evolves across 12+ entities.
- SQLAlchemy Core without SQLModel — more mature/battle-tested but more boilerplate for the FastAPI+Pydantic integration SQLModel gives for free.

**Decision:** FastAPI (ASGI, async endpoints where the underlying I/O is async — notably all LLM calls) + SQLModel (one class = ORM table + Pydantic schema) + Alembic for migrations.

**Trade-offs:** SQLModel is less mature than plain SQLAlchemy and occasionally requires dropping to raw SQLAlchemy Core for advanced queries (e.g., the FTS5 virtual table, which SQLModel doesn't model natively — see Section 7.3). This is an accepted, contained trade-off. *(v1.1 clarification: the FTS5 index is kept in sync via SQLite triggers defined in an Alembic migration — see Section 7.3 — not by any application-level dual-write. This was already the v1.0 design; the mistaken cross-reference to "Section 8" is fixed here and Section 7.3's wording is strengthened to rule out application-level sync explicitly.)*

### ADR-03: Single-process, in-thread event-driven architecture (no task queue, no scheduler library)

**Context:** The system has exactly one background responsibility that isn't triggered by an HTTP request: watching the Obsidian vault for file changes. Everything else (quiz generation, writing evaluation, approvals, backups) is either a direct HTTP request or a hook attached to one.

**Alternatives considered:**
- Celery/RQ/arq task queue — standard pattern for background LLM work, but requires a message broker (Redis, at minimum) as a second running process. For a single user triggering one parse at a time, this is infrastructure with no payoff.
- APScheduler for periodic jobs (backups, decay recomputation) — rejected per the PRD's own reasoning (Section 11.3 of the PRD): decay is computed lazily at read time (ADR-04), and backups are triggered by a startup check plus a post-approval-commit hook, so there is no genuine wall-clock-driven need.

**Decision:** The `watchdog` Observer runs as a background thread started in FastAPI's `lifespan` context manager, sharing the process with the API server. It writes to SQLite through its own `Session`, relying on WAL mode for writer/reader concurrency safety. No separate worker process, no message broker, no scheduler library.

**Trade-offs:** If parsing volume or evaluation latency ever becomes high enough to block the single process meaningfully (unlikely for one user doing a few notes/quizzes a day), this is the first thing to revisit — and the `Generator`/`Evaluator` interface (ADR-06) already isolates the seam where a task queue would be inserted, so this is an additive change, not a rewrite.

### ADR-04: Lazy, read-time mastery decay (no cron)

**Context:** Mastery scores must reflect "current" ability, decaying with time since last practice, without a background job "aging" every row on a schedule.

**Decision:** `mastery_score` is stored as-of `last_reviewed_at`. Every read path applies `decayed = mastery_score * exp(-DECAY_RATE * days_since(last_reviewed_at))` at query time (implemented as a Python post-processing step after the SQL fetch, not as SQL — see Section 8 for why). No stored value is ever mutated by decay; only quiz/writing interactions mutate `mastery_score` directly.

**Trade-offs:** Every dashboard read does a small amount of extra computation (negligible at this row count — low thousands of items, sub-millisecond). This is strictly simpler than any scheduled alternative and was already validated in the PRD.

### ADR-05: Approval workflow as a structural gate, not a UI convention *(amended v1.1)*

**Context:** The product philosophy requires that nothing AI-generated silently enters the permanent learning record. v1.1 makes explicit a distinction that v1.0's single `Correction` entity blurred: **new knowledge** extracted from notes or writing feedback (a candidate collocation, idiom, or corrected expression the learner should retain) is not the same thing as **a record that a specific mistake happened** during a quiz or writing task (something that already occurred and is being logged, not proposed as new content).

**Decision:** `LearningItem` and `LearningCorrection` rows — new knowledge — can only be inserted by `ApprovalService.approve()` / `approve_edited()`. The parser, the writing evaluator, and the quiz-feedback pipeline all write exclusively to `ApprovalQueue` for this category — none of them have a code path that touches `LearningItem` or `LearningCorrection` directly. This is enforced by module boundaries: `app/llm/`, `app/ingestion/`, and `app/writing/` do not import either model's write methods at all; only `app/approvals/service.py` does.

`PerformanceError` rows — a record that a mistake occurred, not new content — are a deliberate, narrow exception to this gate: they are inserted directly by `QuizService.grade_session()` and `WritingService.submit_and_evaluate()` at the moment of grading/evaluation, with no approval step. This is intentional: a `PerformanceError` never adds anything to the learner's knowledge base beyond what they already (mis)produced themselves, so the trust risk the approval gate exists to mitigate — an AI silently inventing content the learner never actually studied or wrote — doesn't apply. Gating it behind approval would only add review friction (PRD Section 26's approval-friction success metric) with no corresponding benefit.

**Trade-offs:** None meaningful for the `LearningItem`/`LearningCorrection` gate itself — unchanged from v1.0. The `PerformanceError` exception is a considered trade-off: not every AI-derived row is approval-gated, which is a narrower framing than v1.0's original wording implied. This is accepted because `PerformanceError` data is consumed only internally (mastery updates, analytics, weekly-report weakness patterns) and never re-surfaces as if it were learner-authored or approved content. The exception is kept structurally narrow the same way the main gate is: exactly two call sites write to `performance_error`, and no other module does — so it cannot silently widen into a general loosening of the approval principle.

### ADR-06: `Generator`/`Evaluator` abstraction over Ollama, using native structured outputs

**Context:** Model-agnosticism is a hard product requirement. Additionally, Ollama (as of the version targeted here) supports passing a JSON Schema via the `format` parameter, which constrains decoding at the token level (grammar-constrained generation) rather than relying on prompt instructions alone — this is materially more reliable than "ask nicely for JSON."

**Alternatives considered:**
- LangChain/LlamaIndex as an abstraction layer — rejected; these bring significant dependency weight and abstraction overhead for what is, at MVP scope, four task types calling one provider.
- Prompt-only JSON enforcement (no `format` parameter) — rejected now that schema-constrained decoding is confirmed available; using it is strictly better with no downside.

**Decision:** A small first-party interface:
```python
class Generator(Protocol):
    async def generate(self, task: str, context: dict, output_schema: type[BaseModel]) -> BaseModel: ...

class Evaluator(Protocol):
    async def evaluate(self, task: str, content: str, context: dict, output_schema: type[BaseModel]) -> BaseModel: ...
```
The default `OllamaAdapter` implements both by calling `/api/chat` with `format=output_schema.model_json_schema()`, parses the response with `output_schema.model_validate_json()`, and retries once on validation failure (Section 9, Section 11).

**Trade-offs:** Schema-constrained decoding guarantees syntactic validity, not semantic correctness (Section 11) — the model can still produce an empty array, a nonsensical value, or a technically-valid-but-wrong classification. Validation therefore still includes light semantic checks per task (Section 9), not just Pydantic parsing.

### ADR-07: SQLite FTS5 instead of a vector database

**Context:** Duplicate detection and "surface a known relevant expression during writing feedback" both need text-similarity search.

**Decision:** A `learning_item_fts` FTS5 virtual table mirrors `LearningItem.text` + `definition`, queried via `MATCH` with BM25 ranking. No embeddings, no vector store.

**Trade-offs:** Purely lexical — will not connect a paraphrase to a semantically related idiom without token overlap (documented in the PRD, Section 15.1, as an accepted MVP limitation with a clear upgrade path). At this data scale (hundreds to low thousands of rows), FTS5 query latency is not a concern.

### ADR-08: Synchronous HTTP endpoints for MVP (no background job queue for user-triggered LLM calls)

**Context:** Quiz generation and writing evaluation can take several seconds to roughly a minute depending on the hosted model. A polling/job-queue pattern is more resilient to long waits but adds real complexity (job table, polling endpoint, frontend state machine for job status).

**Decision:** All user-triggered LLM-backed endpoints (`POST /quizzes`, `POST /writing/evaluate`, `POST /reports/weekly`) are synchronous — the HTTP request stays open until the LLM call completes, and the frontend shows a loading state for the duration. The one exception is note parsing, which is triggered by a file save (not a user click) and is handled entirely server-side with no request/response cycle to block at all — the frontend just polls the lightweight `GET /approvals/pending-count` endpoint on its own normal refresh cadence, which is not a special-purpose job-polling mechanism, just a normal data fetch.

**Trade-offs:** A very slow model host could produce a multi-minute blocked request. Explicitly accepted for MVP simplicity per product owner direction; FastAPI's `timeout` and the frontend's request timeout should both be set generously (Section 11) rather than aggressively, since a timeout here would lose the learner's quiz/writing session state.

### ADR-09: React + TypeScript + Vite, feature-folder structure, TanStack Query, Tailwind CSS

**Context:** Covered in the PRD (Section 11.4); restated here with the concrete patterns needed for implementation.

**Decision:**
- **Feature-folder structure** (`src/features/{dashboard,approvals,quizzes,writing,reports,settings}/`), mirroring the backend's own domain boundaries, rather than a global `components/`/`hooks/` split — keeps each domain's UI, data-fetching hooks, and local logic co-located, which matters for a solo maintainer navigating the codebase months apart.
- **TanStack Query** as the only server-state layer; no Redux/Zustand/Context-based global store. Every screen fetches what it needs via a `useQuery`/`useMutation` hook scoped to its feature folder; cache invalidation on mutation (e.g., approving an item invalidates the pending-count and item-browser queries) is TanStack Query's built-in `invalidateQueries`, not manual state plumbing.
- **Tailwind CSS** for styling — utility classes directly in JSX, no separate CSS-in-JS runtime or design-token abstraction layer needed at this scope.

**Trade-offs:** Tailwind's utility-class density can read as visually noisy in JSX; accepted in exchange for zero additional styling-architecture decisions being needed.

### ADR-10: SQLite Online Backup API instead of raw file copy

**Context:** A raw `cp`/`shutil.copy` of a live SQLite file, even under WAL mode, is not guaranteed transactionally consistent if a write is in progress at the exact moment of copy.

**Decision:** `BackupService` uses Python's built-in `sqlite3.Connection.backup(target_connection)` method, which performs SQLite's own online backup protocol (page-by-page, safe against concurrent writers) directly to a destination `.db` file.

**Trade-offs:** Negligible additional code (a few lines) versus a raw copy, for meaningfully stronger correctness guarantees. No real trade-off.

### ADR-11: Vault Watcher event normalization *(new in v1.1)*

**Context:** `watchdog`'s raw filesystem events do not map cleanly onto "the learner saved a note." Two concrete problems surface with real editors, Obsidian included: (1) many editors save atomically — write to a temp file, then rename it over the target — which raises `on_created`/`on_moved` events rather than `on_modified`, so a handler that only listens for modification will silently miss saves; (2) a single logical save frequently raises more than one raw event in quick succession (e.g., a metadata flush followed by the content write), which without debouncing would trigger duplicate parse calls — wasted LLM calls at best, racing `ApprovalQueue` writes at worst.

**Alternatives considered:**
- Listen only for `on_modified` (v1.0's implicit assumption) — rejected now that it's understood to miss atomic-save saves, which are common enough (many editors, and Obsidian under certain settings) to not be an edge case.
- A polling-based watcher instead of `watchdog` — rejected; strictly worse latency and CPU behavior for no reliability gain, since the debounce/hash logic below solves the real problem regardless of event source.

**Decision:** `VaultWatcher` normalizes all three relevant `watchdog` event types (`on_created`, `on_modified`, `on_moved`) into a single internal `handle_event(path)` entry point, which:
1. **Debounces** — events for the same `vault_path` within a short window (default 2s, configurable) are coalesced into a single downstream call, so a burst of raw events from one save produces one `IngestionService.process_note()` invocation.
2. **Hash-compares before dispatch** — after debouncing, the file's current `content_hash` is computed and compared against the stored `Note.content_hash` (if a `Note` row already exists for that `vault_path`). If unchanged, the event is a no-op (common with editors that touch a file's mtime without changing content) and `IngestionService` is never called. This is the same hash field FR-1.1/FR-1.3 already use for "new note" and "changed since processed" detection (PRD Section 7.1) — v1.1 additionally uses it as the dedup gate before ingestion, not only after.
3. **Treats `on_created` and `on_moved` (rename-into-place) identically to `on_modified`** for dispatch purposes — all three lead to the same debounce → hash-compare → `IngestionService.process_note()` path, since from Praxis's perspective they all mean "this file's content may need to be (re-)considered."

**Trade-offs:** A small amount of additional state (`{vault_path: last_event_time}` in-memory, cleared on dispatch) lives in `VaultWatcher` itself; this is process-local and does not need to survive a restart (a missed debounce window at worst causes one redundant parse, not data loss). The 2s debounce window is a config value, not hardcoded, since different editors and filesystems may need tuning.

### ADR-12: Deterministic inference settings for grading and evaluation calls *(new in v1.1)*

**Context:** Progress scores (mastery, writing dimension scores) are meant to be comparable across weeks and months. Default LLM sampling (temperature > 0) means the same submission graded twice can legitimately receive different scores, which is fine for *content generation* (a quiz shouldn't ask identically-phrased questions every time; a narrative report benefits from natural variation) but undesirable for *grading/evaluation*, where inconsistency directly undermines the "trend visibility" success metric (PRD Section 26) and the learner's trust that a score change reflects real ability change rather than sampling noise.

**Decision:** `OllamaAdapter` maintains a small per-`task` inference-settings table (`app/llm/inference_settings.py`), not a change to the `Generator`/`Evaluator` Protocol itself (Section 3, ADR-06 is unaffected — the interface still takes only `task`, `context`/`content`, `output_schema`). Tasks classified as grading/evaluation — `grade_quiz_answer`, `mini_writing_eval`, `weekly_writing_eval` — are called with `temperature=0` (or the lowest value the model supports, if the runtime does not accept exactly 0) and a fixed `seed` where the Ollama model/runtime supports the `options.seed` parameter. Tasks classified as generation — `parse_note`, `quiz_{mode}`, `weekly_topic`, `weekly_narrative` — retain default sampling, since variety is a feature there, not noise.

**Trade-offs:** `temperature=0` and a fixed seed reduce, but do not eliminate, non-determinism — local model runtimes can still produce small variation across hardware, batch size, or quantization/runtime version changes even with identical inputs and settings. This is a real, accepted limitation, not a guarantee; it's the reason ADR-13 (evaluation versioning) exists as a complementary mitigation — when a score shift can't be explained by learner behavior, the version metadata lets it be explained by a model/runtime change instead of presented as unexplained noise.

### ADR-13: Evaluation provenance and versioning metadata *(new in v1.1)*

**Context:** Prompt templates and rubrics will be iterated on after real usage begins (Section 16's top-ranked risk, "prompt/schema iteration churn"), and the underlying model may itself be swapped (ADR-06, ADR-15.1's named extension path). Without a record of *which* prompt, rubric, and model produced a given score, a future prompt tweak or model upgrade would silently invalidate historical trend comparisons — a score change would be indistinguishable from real progress or regression.

**Decision:** Every graded or evaluated row (`WritingEvaluation`; `QuizQuestion` rows where `graded_by = LLM`) carries four provenance fields, stamped by the calling service at insert time — never by the model, since these are properties of the *call*, not the model's output: `evaluator_provider` (e.g. `"ollama"`), `evaluator_model` (e.g. `"gemma4:31b"` — already present on `WritingEvaluation` per PRD Section 12; v1.1 extends it to `QuizQuestion`), `prompt_version` (a version tag defined as a constant alongside the relevant template in `app/llm/prompts/`, e.g. `WEEKLY_WRITING_EVAL_PROMPT_VERSION = "v1"`), and `rubric_version` (versioned independently of the prompt, since rubric *wording* and prompt *scaffolding* can each change without the other — e.g. `WEEKLY_WRITING_RUBRIC_VERSION = "v1"`). `evaluator_provider`/`evaluator_model` are read from the active `Config` values (Section 12.1) at call time; `prompt_version`/`rubric_version` are read from the constants co-located with the template that was actually used.

**Trade-offs:** Four additional nullable columns on two tables, and a small amount of ongoing discipline (remembering to bump a version constant when a prompt or rubric changes materially). The discipline cost is mitigated by co-locating each version constant directly with the prompt text it describes, making it hard to change one without noticing the other. No schema migration risk beyond the initial column addition — these are additive, nullable fields, consistent with the "additive, never destructive" data-integrity principle (PRD Section 8).

---

## 4. High-Level System Architecture

### 4.1 Component Diagram (Textual)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Obsidian Vault (Markdown)                       │
│                    learner-owned, never written to by Praxis            │
└───────────────────────────────┬─────────────────────────────────────────┘
                                 │ filesystem events (create/modify)
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     PRAXIS BACKEND — single Python process               │
│                                                                          │
│  ┌──────────────────┐        lifespan-managed background thread         │
│  │  VaultWatcher      │◀──────────────────────────────────────────────  │
│  │  (watchdog)         │                                                 │
│  └─────────┬─────────┘                                                  │
│            │ enqueue_note_for_parsing(path)                             │
│            ▼                                                            │
│  ┌──────────────────┐     ┌──────────────────┐                          │
│  │ IngestionService   │────▶│ Generator (parse) │──▶ OllamaAdapter        │
│  └─────────┬─────────┘     └──────────────────┘                          │
│            │ writes ApprovalQueue rows                                  │
│            ▼                                                            │
│  ┌──────────────────┐   FastAPI routers (REST/JSON, sync handlers)      │
│  │ ApprovalService     │◀── /approvals/*                                 │
│  └─────────┬─────────┘                                                  │
│            │ writes LearningItem / LearningCorrection (ONLY entry point) │
│            ▼                                                            │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                SQLite DB (WAL) + FTS5 virtual table              │    │
│  └───────┬─────────────────────┬─────────────────────┬─────────────┘    │
│          │                     │                     │                  │
│  ┌───────▼───────┐   ┌─────────▼────────┐   ┌────────▼────────┐          │
│  │ SchedulerModule │   │ RetrievalService  │   │ DashboardService │          │
│  │ (mastery/decay) │   │ (SQL + FTS5)      │   │ (aggregations)   │          │
│  └───────┬───────┘   └─────────┬────────┘   └────────┬────────┘          │
│          └──────────┬──────────┘                     │                  │
│                      ▼                                │                  │
│  ┌────────────────────────────────────┐               │                  │
│  │ QuizService / WritingService /       │               │                  │
│  │ ReportService                        │───────────────┘                  │
│  └──────────────┬─────────────────────┘                                  │
│                 │ Generator.generate() / Evaluator.evaluate()            │
│                 ▼                                                        │
│  ┌────────────────────────┐                                             │
│  │ Generator/Evaluator      │──▶ OllamaAdapter ──▶ hosted Ollama endpoint  │
│  │ Interface (app/llm/)     │                                             │
│  └────────────────────────┘                                             │
│                                                                          │
│  ┌────────────────────────┐                                             │
│  │ BackupService             │──▶ local rotating .db snapshots            │
│  └────────────────────────┘                                             │
└───────────────────────────────┬──────────────────────────────────────────┘
                                 │  REST/JSON over localhost
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Frontend SPA (React + Vite)                        │
│   Dashboard │ Approvals │ Quizzes │ Writing │ Reports │ Settings          │
│   TanStack Query (server state) + Tailwind CSS                          │
└────────────────────────────────────────────────────────────────────────┘
```
*(v1.1)* Not shown to keep the diagram legible: `QuizService` and `WritingService` (in the `QuizService / WritingService / ReportService` box) also write directly to a `PerformanceError` table in the SQLite DB, bypassing `ApprovalService` entirely — this is the documented exception in ADR-05. `PerformanceError` is a record of a mistake that already happened (a wrong quiz answer, a grammar error caught during writing evaluation), not new content being proposed, so it does not go through the approval gate the diagram's main data path illustrates.

### 4.2 Component Responsibility Table

| Component | Responsibility | Lives in |
|---|---|---|
| `VaultWatcher` | Observes vault directory; normalizes create/modify/moved events, debounces, hash-compares before dispatch *(v1.1, ADR-11)*, creates/updates `Note` row, hands off to `IngestionService`. No parsing logic itself. | `app/ingestion/watcher.py` |
| `IngestionService` | Reads note content, calls `Generator` with the parse task, validates output, runs duplicate detection, writes `ApprovalQueue` rows, manages `Note` state transitions. | `app/ingestion/service.py` |
| `ApprovalService` | The **only** writer of `LearningItem`/`LearningCorrection` *(renamed v1.1)*. Handles approve/edit-approve/reject actions, single-item and batch. | `app/approvals/service.py` |
| `SchedulerModule` | Pure functions: `select_eligible_items()`, `update_mastery(item, result)`, `decayed_score(item)`. No I/O of its own beyond the DB session passed in. | `app/scheduler/mastery.py` |
| `RetrievalService` | All read-side structured queries (week-scoped items, FTS5 duplicate/relevance search, quiz eligibility joins, `PerformanceError` weakness aggregation *(v1.1)*). The single place SQL for cross-cutting reads lives, so pipelines don't hand-roll queries. | `app/retrieval/service.py` |
| `QuizService` | Orchestrates: eligibility selection → prompt construction → `Generator.generate()` → grading → mastery update → persistence. Writes `PerformanceError` directly on incorrect/low-score answers *(v1.1, ADR-05 exception)*. | `app/quizzes/service.py` |
| `WritingService` | Orchestrates mini and weekly writing flows: prompt generation (with repetition avoidance), submission storage, `Evaluator.evaluate()`, suggested-item routing to `ApprovalQueue`. Writes `PerformanceError` directly for each itemized correction identified during evaluation *(v1.1, ADR-05 exception)*. | `app/writing/service.py` |
| `ReportService` | Assembles a `WeeklyReport` from that week's quiz/writing/mastery data; calls `Generator` for the narrative summary. | `app/reports/service.py` |
| `DashboardService` | Read-only aggregation queries for the dashboard screens (no mutation). | `app/dashboard/service.py` |
| `Generator` / `Evaluator` interface | Abstract contract; decouples every pipeline above from any specific model/provider. | `app/llm/interface.py` |
| `OllamaAdapter` | Default implementation; HTTP calls to Ollama's `/api/chat` with schema-constrained `format`; retry/timeout handling. | `app/llm/ollama_adapter.py` |
| `BackupService` | Online-backup snapshot + rotation, triggered on startup and after approval-commit batches. | `app/backup/service.py` |
| Frontend feature modules | UI + data-fetching hooks per domain; no business logic beyond client-side form validation and optimistic-update handling. | `frontend/src/features/*` |

### 4.3 Backend Project Structure

```
backend/
├── app/
│   ├── main.py                      # FastAPI() instance, lifespan (starts VaultWatcher thread, runs startup backup check)
│   ├── config.py                    # pydantic-settings Settings, loaded from .env
│   │
│   ├── db/
│   │   ├── engine.py                # SQLModel engine + get_session() dependency
│   │   ├── models/
│   │   │   ├── source.py            # Source, Lesson
│   │   │   ├── note.py              # Note
│   │   │   ├── approval.py          # ApprovalQueue
│   │   │   ├── learning_item.py     # LearningItem, Tag, LearningItemTag
│   │   │   ├── learning_correction.py # LearningCorrection            [v1.1: split from correction.py]
│   │   │   ├── performance_error.py   # PerformanceError               [v1.1: split from correction.py]
│   │   │   ├── quiz.py              # QuizSession, QuizQuestion
│   │   │   ├── writing.py           # WritingPrompt, WritingSubmission, WritingEvaluation
│   │   │   ├── report.py            # WeeklyReport
│   │   │   └── system.py            # Config, AuditLog
│   │   └── migrations/              # Alembic env + versions/
│   │
│   ├── llm/
│   │   ├── interface.py             # Generator, Evaluator Protocols
│   │   ├── ollama_adapter.py        # OllamaAdapter(Generator, Evaluator)
│   │   ├── schemas.py               # Pydantic output schemas: ParsedNote, QuizQuestionOutput, WritingEvaluationOutput, WeeklyReportOutput
│   │   └── prompts/
│   │       ├── parser.py
│   │       ├── quiz.py
│   │       ├── writing_eval.py
│   │       └── weekly_report.py
│   │
│   ├── ingestion/
│   │   ├── watcher.py                # VaultWatcher (watchdog thread)
│   │   ├── service.py                # IngestionService
│   │   └── duplicate_detection.py    # FTS5 query helpers
│   │
│   ├── approvals/
│   │   ├── service.py                # ApprovalService
│   │   └── router.py                 # /approvals/*
│   │
│   ├── scheduler/
│   │   └── mastery.py                # pure functions, no router (used internally by quizzes/)
│   │
│   ├── retrieval/
│   │   └── service.py                # RetrievalService
│   │
│   ├── quizzes/
│   │   ├── service.py
│   │   ├── grading.py                # deterministic + LLM-fallback grading
│   │   └── router.py                 # /quizzes/*
│   │
│   ├── writing/
│   │   ├── service.py
│   │   └── router.py                 # /writing/*
│   │
│   ├── reports/
│   │   ├── service.py
│   │   └── router.py                 # /reports/*
│   │
│   ├── dashboard/
│   │   ├── service.py
│   │   └── router.py                 # /dashboard/*
│   │
│   └── backup/
│       └── service.py                # BackupService
│
├── tests/
│   ├── unit/                         # scheduler, grading, duplicate_detection — pure logic
│   ├── integration/                  # service-level tests against an in-memory/temp SQLite DB
│   └── fixtures/                     # sample notes, mocked Generator/Evaluator responses
│
├── alembic.ini
├── pyproject.toml
└── .env.example
```

### 4.4 Frontend Project Structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                       # React Router setup, top-level layout
│   │
│   ├── api/
│   │   ├── client.ts                 # fetch wrapper (base URL, JSON handling, error normalization)
│   │   └── types.ts                  # TypeScript types mirroring backend Pydantic schemas
│   │
│   ├── features/
│   │   ├── dashboard/
│   │   │   ├── components/           # ProficiencyCard, TrendChart, MasteryBreakdownChart
│   │   │   ├── hooks/                # useOverview, useMasteryBreakdown, useTrends
│   │   │   └── DashboardPage.tsx
│   │   ├── approvals/
│   │   │   ├── components/           # ApprovalCard, ApprovalBatchActions
│   │   │   ├── hooks/                # usePendingApprovals, useApproveItem
│   │   │   └── ApprovalsPage.tsx
│   │   ├── quizzes/
│   │   │   ├── components/           # QuizModeSelector, QuestionCard (per type), SessionSummary
│   │   │   ├── hooks/                # useStartQuiz, useSubmitAnswer
│   │   │   └── QuizPage.tsx
│   │   ├── writing/
│   │   │   ├── components/           # WritingEditor, EvaluationFeedback (inline annotations)
│   │   │   ├── hooks/                # useMiniTask, useWeeklyAssessment
│   │   │   └── WritingPage.tsx
│   │   ├── reports/
│   │   │   ├── components/           # ReportSummaryCard
│   │   │   ├── hooks/                # useWeeklyReports, useStartWeeklyReview
│   │   │   └── ReportsPage.tsx
│   │   └── settings/
│   │       ├── hooks/                # useConfig, useUpdateConfig
│   │       └── SettingsPage.tsx
│   │
│   └── shared/
│       ├── components/                # Button, Card, ScoreBadge, LoadingSpinner, EmptyState
│       └── lib/                       # date formatting, score-color mapping
│
├── index.html
├── package.json
├── tailwind.config.ts
└── vite.config.ts
```

---

## 5. Component Interaction

- **VaultWatcher → IngestionService:** in-process function call (same Python process, different thread — the watcher thread calls into `IngestionService` synchronously via its own DB session; no queue between them since parsing one note at a time is acceptable latency for a background file-save trigger).
- **IngestionService / QuizService / WritingService / ReportService → Generator/Evaluator:** in-process `await` calls against the `Generator`/`Evaluator` Protocol; the concrete adapter (`OllamaAdapter`) makes the actual outbound HTTP call to the Ollama host.
- **All services → SQLite:** through SQLModel `Session` objects obtained via FastAPI's dependency injection (`Depends(get_session)`) for request-triggered work, or a locally constructed `Session` for the watcher thread's background work.
- **Frontend → Backend:** REST/JSON exclusively, over `http://localhost:<port>`. No WebSockets, no Server-Sent Events in MVP (ADR-08 — synchronous request/response is sufficient).
- **Frontend internal:** TanStack Query mediates all component-to-server-state interaction; components never call `fetch` directly, always through a feature-scoped hook that wraps a `useQuery`/`useMutation`.

---

## 6. Sequence Diagrams

### 6.1 Save Note → Parser Pipeline → Approval Queue *(event handling updated in v1.1, ADR-11)*

```
Learner saves note.md in Obsidian
        │
        ▼
watchdog raises on_created / on_modified / on_moved(path)   [v1.1: all three, not modified-only — ADR-11]
        │
        ▼
VaultWatcher._raw_event_handler(path, event_type)
   ├── debounce: record (path, now); if a call for this path is already pending within
   │        the debounce window (default 2s), coalesce — only the last one proceeds   [v1.1, ADR-11]
   └── after debounce window elapses → VaultWatcher.handle_event(path)
        │
        ▼
VaultWatcher.handle_event(path)
   ├── new_hash = compute content_hash(path)
   ├── existing = fetch Note row by vault_path, if any
   ├── if existing and existing.content_hash == new_hash → RETURN (no-op; mtime-only touch, not a real change)   [v1.1, ADR-11]
   ├── upsert Note row (status=NEW, content_hash=new_hash)
   └── call IngestionService.process_note(note_id)
        │
        ▼
IngestionService.process_note(note_id)
   ├── Note.status = PARSING
   ├── content = read file
   ├── result = await Generator.generate(
   │        task="parse_note",
   │        context={"note_content": content, "recent_items": [...]},
   │        output_schema=ParsedNoteOutput)
   │        └──▶ OllamaAdapter POST /api/chat  (format=ParsedNoteOutput.schema())
   │                 └──▶ hosted Ollama model
   ├── on schema validation failure → retry once with error-correction prompt
   │        └── on second failure → Note.status = PARSE_FAILED; AuditLog entry; RETURN
   ├── for each candidate item in result.items:
   │        ├── duplicates = RetrievalService.find_similar(item.text)   [FTS5 MATCH]
   │        └── INSERT ApprovalQueue row (status=PENDING, possible_duplicate_of=...)
   └── Note.status = PENDING_APPROVAL
```

**Why both a debounce and a hash-compare** *(v1.1, ADR-11)*: the debounce absorbs multiple raw filesystem events from one save arriving in quick succession; the hash-compare separately catches the case where a single, cleanly-debounced event still doesn't represent a real content change (e.g. an editor rewriting a file with identical content, or a filesystem `touch`). Neither alone is sufficient — a fast succession of genuinely different saves must still each be processed once debounced, and a single event with unchanged content must still be skipped even with no debounce collision.

### 6.2 Approval Action

```
Learner clicks "Approve" on an ApprovalQueue item (frontend)
        │
        ▼
POST /approvals/{id}/approve   (or /approve-edited with payload)
        │
        ▼
ApprovalService.approve(approval_id, edited_payload=None)
   ├── BEGIN transaction
   ├── fetch ApprovalQueue row
   ├── INSERT LearningItem (mastery_score=0.3, review_count=0, ...)
   │        or INSERT LearningCorrection, depending on item_type   [renamed v1.1]
   ├── UPDATE ApprovalQueue.status = APPROVED | EDITED_APPROVED
   ├── COMMIT
   └── BackupService.maybe_backup()   [post-write hook, ADR-03]
        │
        ▼
Response 200 { learning_item_id }
        │
        ▼
Frontend: TanStack Query invalidates ["approvals","pending"], ["items"], ["dashboard","mastery"]
```

### 6.3 Ad-hoc Quiz Generation & Grading

```
Learner selects quiz mode + size, clicks "Start Quiz" (frontend)
        │
        ▼
POST /quizzes  { mode, size }                       (synchronous, ADR-08)
        │
        ▼
QuizService.start_session(mode, size)
   ├── items = SchedulerModule.select_eligible_items(session, size, category_balance=0.6)
   ├── INSERT QuizSession (status=IN_PROGRESS)
   ├── for each item (or 7 random modes if mode == RANDOM):
   │        ├── prompt_ctx = RetrievalService.item_context(item)
   │        ├── q = await Generator.generate(task=f"quiz_{item_mode}", context=prompt_ctx, output_schema=QuizQuestionOutput)
   │        └── INSERT QuizQuestion (prompt=q.prompt_text, correct_answer=q.correct_answer, ...)
   └── return QuizSession + QuizQuestion[] (prompts only, no answers) to frontend
        │
        ▼
Learner answers each question (frontend, local state until submit)
        │
        ▼
POST /quizzes/{session_id}/answers   { question_id, user_answer }[]
        │
        ▼
QuizService.grade_session(session_id, answers)
   ├── for each answer:
   │        ├── if deterministic type → GradingModule.grade_deterministic(question, answer)
   │        │        └── on ambiguous free-text mismatch → fallback to LLM grading
   │        ├── else → await Evaluator.evaluate(task="grade_quiz_answer", content=answer, context=question,
   │        │        output_schema=GradedAnswerOutput)   [temperature=0 + fixed seed where supported — ADR-12]
   │        ├── UPDATE QuizQuestion (user_answer, is_correct/score, feedback, graded_by,
   │        │        evaluator_provider, evaluator_model, prompt_version, rubric_version)   [v1.1, ADR-13 — only when graded_by=LLM]
   │        ├── if not correct (score < CORRECT_THRESHOLD or is_correct=false):
   │        │        └── INSERT PerformanceError (learning_item_id=question.learning_item_id, wrong_form=user_answer,
   │        │                 correct_form=question.correct_answer, explanation=feedback,
   │        │                 source_type=QUIZ, source_id=question.id)   [v1.1, direct write — no approval, ADR-05 exception]
   │        └── SchedulerModule.update_mastery(learning_item, result)   [Section 8.4 formula]
   ├── UPDATE QuizSession.completed_at = now
   └── return session summary
```

### 6.4 Weekly Writing Assessment

```
Learner clicks "Start Weekly Review" → writing step reached (frontend)
        │
        ▼
POST /reports/weekly/writing-prompt
        │
        ▼
WritingService.generate_weekly_prompt()
   ├── recent_topics = RetrievalService.recent_prompts(type=WEEKLY, limit=12)
   ├── prompt = await Generator.generate(task="weekly_topic", context={"avoid": recent_topics}, output_schema=TopicOutput)
   └── INSERT WritingPrompt (prompt_type=WEEKLY)
        │
        ▼
Learner writes essay in WritingEditor (frontend, local draft state)
        │
        ▼
POST /writing/submissions   { prompt_id, text }
        │
        ▼
WritingService.submit_and_evaluate(prompt_id, text)
   ├── INSERT WritingSubmission
   ├── ctx = RetrievalService.writing_context(text)     [weak categories + FTS5-matched known items]
   ├── result = await Evaluator.evaluate(task="weekly_writing_eval", content=text, context=ctx,
   │        output_schema=WeeklyWritingEvalOutput)   [temperature=0 + fixed seed where supported — ADR-12]
   │        └── on failure → WritingEvaluation.status = EVALUATION_FAILED; submission preserved; RETURN error to frontend (retry available)
   ├── INSERT WritingEvaluation (5 scores + feedback_json + suggested_items_json +
   │        evaluator_provider, evaluator_model, prompt_version, rubric_version)   [v1.1, ADR-13]
   ├── for each itemized correction in result (mini-task path only — see note below):
   │        └── INSERT PerformanceError (learning_item_id=null, wrong_form=correction.wrong,
   │                 correct_form=correction.correct, explanation=correction.explanation,
   │                 source_type=WRITING_MINI, source_id=writing_evaluation.id)   [v1.1, direct write — no approval, ADR-05 exception]
   └── for each suggested_item → INSERT ApprovalQueue (source_type=WRITING_FEEDBACK)
        │
        ▼
Response: full evaluation to frontend for inline display
```
*(v1.1)* `submit_and_evaluate` is shared by both the mini and weekly writing flows (Section 4.2), differing by `task`/`output_schema`. The `PerformanceError` step applies to the mini-task path (`MiniWritingEvalOutput.corrections`, Section 9.4), which returns an itemized wrong/correct list; the weekly path (diagrammed above) produces five qualitative `DimensionScore` values with no itemized mistake list in v1.1, so it does not generate `PerformanceError` rows directly — its scores still feed mastery/analytics through `WritingEvaluation` itself, per the existing PRD Section 17.4 blend. Extending itemized `PerformanceError` extraction to the weekly rubric is a reasonable future addition, not required for this patch.

### 6.5 Weekly Report Assembly

```
(after weekly quiz + weekly writing steps both complete)
        │
        ▼
POST /reports/weekly/finalize   { week_start, week_end }
        │
        ▼
ReportService.assemble(week_start, week_end)
   ├── items_this_week = RetrievalService.items_created_between(week_start, week_end)
   ├── quiz_summary = RetrievalService.quiz_summary_for_week(...)          [now aggregates PerformanceError rows, source_type=QUIZ — v1.1]
   ├── mini_writing_summary = RetrievalService.mini_writing_summary_for_week(...)   [now aggregates PerformanceError rows, source_type=WRITING_MINI, for recurring-error patterns per PRD 19.3 — v1.1]
   ├── weekly_writing_eval = RetrievalService.weekly_writing_eval_for_week(...)
   ├── mastery_snapshot = DashboardService.category_mastery_snapshot()
   ├── narrative = await Generator.generate(task="weekly_narrative",
   │        context={quiz_summary, mini_writing_summary, weekly_writing_eval},
   │        output_schema=WeeklyNarrativeOutput)
   └── INSERT WeeklyReport (all of the above + narrative_report)
        │
        ▼
Response: full WeeklyReport to frontend
```

### 6.6 Dashboard Refresh

```
Learner navigates to Dashboard (frontend)
        │
        ▼
TanStack Query fires 3 independent queries in parallel:
   ├── GET /dashboard/overview          → DashboardService.overview()
   │        ├── proficiency = blend(category_mastery_avg, recent_writing_avg)   [decay applied at read-time, ADR-04]
   │        └── returns { proficiency, trend_delta, week_snapshot, pending_approvals_count }
   ├── GET /dashboard/mastery-breakdown → DashboardService.mastery_by_category()
   └── GET /dashboard/trends?range=90d  → DashboardService.trend_series()
        │
        ▼
Each hook independently resolves; components render progressively as each query settles
(no single blocking "load everything" call — matches TanStack Query's per-query caching model)
```

### 6.7 Backup

```
Trigger A: FastAPI lifespan startup
   └── BackupService.check_and_backup_if_needed()
        ├── last_backup = Config["last_backup_at"]
        └── if last_backup is None or date(last_backup) < date(today): perform_backup()

Trigger B: post-approval-commit hook (Section 6.2, end of ApprovalService.approve())
   └── BackupService.maybe_backup()   [same check_and_backup_if_needed logic — idempotent, cheap no-op if already backed up today]

BackupService.perform_backup()
   ├── src_conn = sqlite3.connect(db_path)
   ├── dst_conn = sqlite3.connect(backups/praxis_YYYY-MM-DD.db)
   ├── src_conn.backup(dst_conn)          [SQLite Online Backup API, ADR-10]
   ├── rotate(): keep last 14 daily + last 6 monthly, delete the rest
   ├── Config["last_backup_at"] = now
   └── AuditLog INSERT (event_type=BACKUP_TAKEN)
```

---

## 7. Data Architecture

This elaborates the PRD's Section 12 with the indexing, constraint, and timestamp/status discipline needed for implementation.

### 7.1 Cross-cutting conventions

- Every table has `created_at` (server-set, `default=datetime.utcnow`). Mutable entities additionally track the specific timestamp that matters for their domain (`last_reviewed_at`, `reviewed_at`, `processed_at`) rather than a generic `updated_at` — this keeps intent explicit per the reference document's own pattern of purpose-specific timestamps.
- Every entity with a lifecycle (`Note`, `ApprovalQueue`, `QuizSession`, `WritingEvaluation`) has an explicit `status` enum column, never a set of nullable boolean flags standing in for state. `PerformanceError` *(v1.1)* is a deliberate exception: it has no `status`/lifecycle at all — it's written once, atomically, at grading time, and never transitions or gets edited, consistent with it being a factual record rather than something that gets reviewed.
- Foreign keys are enforced (`PRAGMA foreign_keys = ON` set at connection time — SQLite does not enforce FKs by default).
- All primary keys are `INTEGER` autoincrement (SQLite `ROWID`-backed) — no UUIDs needed; this is a single-writer-dominant, single-database system with no distributed-ID requirement.
- **Evaluation metadata** *(v1.1, ADR-13)*: any row produced by an LLM grading/evaluation call (`WritingEvaluation`; `QuizQuestion` where `graded_by=LLM`) carries four nullable fields — `evaluator_provider`, `evaluator_model`, `prompt_version`, `rubric_version` — stamped by the calling service at insert time, never by the model. `PerformanceError` does not duplicate these fields; it inherits provenance from its `source_id` (the `QuizQuestion`/`WritingEvaluation` row that produced it).

### 7.2 Indexes (beyond primary keys)

| Table | Index | Purpose |
|---|---|---|
| `note` | `idx_note_vault_path` (unique) | Fast lookup/upsert on file save by path |
| `note` | `idx_note_status` | Watcher/dashboard queries for `PARSE_FAILED`/`PENDING_APPROVAL` notes |
| `approval_queue` | `idx_approval_status` | Approval inbox query (`WHERE status = PENDING`) |
| `approval_queue` | `idx_approval_source` (`source_type`, `source_id`) | Grouping approval items by originating note/evaluation |
| `learning_item` | `idx_item_next_review_due` | Scheduler eligibility query (`WHERE next_review_due <= now`) |
| `learning_item` | `idx_item_type_suspended` (`item_type`, `suspended`) | Category-balanced quiz selection |
| `learning_item` | `idx_item_created_at` | Weekly-review "items studied this week" query |
| `quiz_question` | `idx_question_session` (`quiz_session_id`) | Fetching all questions for a session |
| `quiz_question` | `idx_question_item` (`learning_item_id`) | Mastery-update joins |
| `writing_submission` | `idx_submission_created_at` | Weekly-window queries |
| `weekly_report` | `idx_report_week_start` (unique) | One report per week; archive ordering |
| `audit_log` | `idx_audit_timestamp` | Chronological audit review |
| `learning_correction` | `idx_learning_correction_created_at` *(v1.1)* | Item-browser / audit ordering, mirrors `learning_item`'s pattern |
| `performance_error` | `idx_perf_error_source` (`source_type`, `source_id`) *(v1.1)* | Joining back to the originating `QuizQuestion`/`WritingEvaluation` |
| `performance_error` | `idx_perf_error_item_created` (`learning_item_id`, `created_at`) *(v1.1)* | Weekly-report weakness-pattern aggregation (PRD Section 19.3) |

### 7.3 FTS5 virtual table

```sql
CREATE VIRTUAL TABLE learning_item_fts USING fts5(
    text,
    definition,
    content='learning_item',
    content_rowid='id'
);

-- kept in sync via triggers (SQLModel does not manage these; created in an Alembic migration):
CREATE TRIGGER learning_item_ai AFTER INSERT ON learning_item BEGIN
    INSERT INTO learning_item_fts(rowid, text, definition) VALUES (new.id, new.text, new.definition);
END;
CREATE TRIGGER learning_item_ad AFTER DELETE ON learning_item BEGIN
    INSERT INTO learning_item_fts(learning_item_fts, rowid, text, definition) VALUES ('delete', old.id, old.text, old.definition);
END;
CREATE TRIGGER learning_item_au AFTER UPDATE ON learning_item BEGIN
    INSERT INTO learning_item_fts(learning_item_fts, rowid, text, definition) VALUES ('delete', old.id, old.text, old.definition);
    INSERT INTO learning_item_fts(rowid, text, definition) VALUES (new.id, new.text, new.definition);
END;
```
This is why SQLModel drops to raw SQLAlchemy Core for this one table (ADR-02) — SQLModel's declarative model layer has no native FTS5 virtual-table support, and hand-written DDL + triggers via Alembic is the standard, correct way to manage this in SQLite regardless of ORM.

*(v1.1 clarification)*: these three triggers are the **only** mechanism that ever writes to `learning_item_fts`. No service-layer code inserts, updates, or deletes rows in the FTS5 table directly — `IngestionService`, `ApprovalService`, and every other caller only ever write to `learning_item`, and the trigger keeps the index consistent within the same transaction, automatically. This rules out the class of bug where an insert path is added later and someone forgets to also update the search index by hand — there is no hand-update path to forget.

### 7.4 Relationships (ER summary)

```
Source 1──N Lesson 1──N Note 1──N ApprovalQueue N──1 LearningItem (0..1, on approval)
ApprovalQueue N──1 LearningCorrection (0..1, on approval)                          [v1.1: split from Correction]
LearningItem 1──N LearningItemTag N──1 Tag
LearningItem 1──N QuizQuestion N──1 QuizSession
LearningItem 1──N PerformanceError (0..N, nullable FK — a PerformanceError may not reference a specific item)   [v1.1: split from Correction]
QuizQuestion 1──N PerformanceError (via source_type=QUIZ, source_id)               [v1.1]
WritingEvaluation 1──N PerformanceError (via source_type=WRITING_MINI, source_id)   [v1.1]
WritingPrompt 1──N WritingSubmission 1──1 WritingEvaluation
WeeklyReport 1──N QuizSession (scope=WEEKLY_REVIEW)
WeeklyReport 1──1 WritingEvaluation (the weekly one; mini evaluations reference week via created_at range, not FK)
```

### 7.5 Denormalization

Per the PRD (Section 12): `ApprovalQueue.source_context` stores a verbatim excerpt (not just a FK) so the approval screen remains meaningful even if source data changes later; `WeeklyReport.mastery_snapshot_json` stores a point-in-time copy so historical reports don't silently drift as `LearningItem.mastery_score` continues to evolve. Both are deliberate, documented denormalizations — not accidental duplication.

---

## 8. Database Schema (SQLModel)

Representative table definitions (not exhaustive of every column already listed in PRD Section 12 — this section focuses on the SQLModel-specific implementation detail: types, indexes, constraints).

```python
# app/db/models/note.py
from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional

class NoteStatus(str, Enum):
    NEW = "NEW"
    PARSING = "PARSING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PROCESSED = "PROCESSED"
    PARSE_FAILED = "PARSE_FAILED"

class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    vault_path: str = Field(index=True, unique=True)
    content_hash: str
    lesson_id: Optional[int] = Field(default=None, foreign_key="lesson.id")
    status: NoteStatus = Field(default=NoteStatus.NEW, index=True)
    changed_since_processed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
```

```python
# app/db/models/learning_item.py
from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional

class ItemType(str, Enum):
    COLLOCATION = "COLLOCATION"
    IDIOM = "IDIOM"
    PHRASAL_VERB = "PHRASAL_VERB"
    GRAMMAR_NOTE = "GRAMMAR_NOTE"
    PERSONAL_EXAMPLE = "PERSONAL_EXAMPLE"

class LearningItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_type: ItemType = Field(index=True)
    text: str
    definition: Optional[str] = None
    example_sentence: Optional[str] = None
    source_note_id: Optional[int] = Field(default=None, foreign_key="note.id")
    source_approval_id: int = Field(foreign_key="approvalqueue.id")

    mastery_score: float = Field(default=0.3)
    review_count: int = Field(default=0)
    correct_count: int = Field(default=0)
    incorrect_count: int = Field(default=0)
    last_reviewed_at: Optional[datetime] = None
    next_review_due: Optional[datetime] = Field(default=None, index=True)
    ease_factor: float = Field(default=2.5)
    interval_days: int = Field(default=0)
    suspended: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    class Config:
        # composite index (item_type, suspended) declared in Alembic migration,
        # since SQLModel's Field(index=True) only supports single-column indexes
        pass
```

```python
# app/db/models/learning_correction.py   [v1.1: new — split from the v1.0 `Correction` entity]
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional

class LearningCorrection(SQLModel, table=True):
    """New knowledge extracted from a note or a writing-feedback suggestion
    (e.g. 'I used to say X, the correct/more natural form is Y'). Approval-gated,
    structurally identical in spirit to LearningItem — see ADR-05."""
    id: Optional[int] = Field(default=None, primary_key=True)
    wrong_form: str
    correct_form: str
    explanation: Optional[str] = None
    example_sentence: Optional[str] = None
    source_note_id: Optional[int] = Field(default=None, foreign_key="note.id")
    source_writing_evaluation_id: Optional[int] = Field(default=None, foreign_key="writingevaluation.id")
    source_approval_id: int = Field(foreign_key="approvalqueue.id")   # required — only ApprovalService inserts this row

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

```python
# app/db/models/performance_error.py   [v1.1: new — split from the v1.0 `Correction` entity]
from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional

class PerformanceErrorSource(str, Enum):
    QUIZ = "QUIZ"
    WRITING_MINI = "WRITING_MINI"
    WRITING_WEEKLY = "WRITING_WEEKLY"   # reserved; not populated in MVP — see Section 6.4 note

class PerformanceError(SQLModel, table=True):
    """A record that a specific mistake happened during a quiz or writing task.
    Written directly by QuizService/WritingService at grading time — no approval
    step, no status/lifecycle. See ADR-05's documented exception."""
    id: Optional[int] = Field(default=None, primary_key=True)
    learning_item_id: Optional[int] = Field(default=None, foreign_key="learningitem.id", index=True)
    wrong_form: str
    correct_form: str
    explanation: Optional[str] = None
    source_type: PerformanceErrorSource
    source_id: int = Field(index=True)   # QuizQuestion.id or WritingEvaluation.id, per source_type

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

```python
# app/db/models/approval.py
from enum import Enum
from datetime import datetime
from typing import Optional, Any
from sqlmodel import SQLModel, Field, JSON, Column

class ApprovalSourceType(str, Enum):
    NOTE_PARSE = "NOTE_PARSE"
    WRITING_FEEDBACK = "WRITING_FEEDBACK"
    QUIZ_FEEDBACK = "QUIZ_FEEDBACK"

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED_APPROVED = "EDITED_APPROVED"
    REJECTED = "REJECTED"

class ApprovalQueue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: ApprovalSourceType
    source_id: int
    item_type: str                      # mirrors ItemType, plus "CORRECTION" — on approval, CORRECTION items commit to LearningCorrection, everything else to LearningItem [v1.1]
    extracted_text: str
    explanation: Optional[str] = None
    example_sentence: Optional[str] = None
    source_context: str
    possible_duplicate_of: Optional[int] = Field(default=None, foreign_key="learningitem.id")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, index=True)
    reviewed_payload: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
```

Remaining tables (`Source`, `Lesson`, `Tag`, `LearningItemTag`, `QuizSession`, `QuizQuestion`, `WritingPrompt`, `WritingSubmission`, `WritingEvaluation`, `WeeklyReport`, `Config`, `AuditLog`) follow the identical pattern established above — enum-typed status/type columns, explicit nullable timestamps per lifecycle event, JSON columns via `sa_column=Column(JSON)` for structured feedback blobs (`feedback_json`, `suggested_items_json`, `mastery_snapshot_json`) — and are fully specified in PRD Section 12; they are not repeated verbatim here to avoid duplicating that document, but every column listed there maps directly to a `Field(...)` following these same conventions. *(v1.1)* Two changes beyond PRD Section 12: `QuizQuestion` and `WritingEvaluation` each gain the four evaluation-metadata fields from ADR-13 (`evaluator_provider`, `evaluator_model`, `prompt_version`, `rubric_version` — nullable, populated only when the row was LLM-graded/evaluated); `Correction` is removed entirely, replaced by `LearningCorrection` and `PerformanceError` above.

### 8.4 Mastery Update Formula (implementation of PRD Section 16.6)

```python
# app/scheduler/mastery.py
from datetime import datetime, timedelta
import math

DECAY_RATE = 0.0077  # tuned so mastery_score=1.0 decays to ~0.5 after ~90 days (config-overridable)
CORRECT_THRESHOLD = 0.7

def decayed_score(item: LearningItem, now: datetime | None = None) -> float:
    """Read-time decay (ADR-04) — never mutates the stored value."""
    now = now or datetime.utcnow()
    if item.last_reviewed_at is None:
        return item.mastery_score
    days = (now - item.last_reviewed_at).days
    return item.mastery_score * math.exp(-DECAY_RATE * days)

def update_mastery(item: LearningItem, score: float, now: datetime | None = None) -> None:
    """Mutates item in place; caller is responsible for committing the session."""
    now = now or datetime.utcnow()
    correct = score >= CORRECT_THRESHOLD
    if correct:
        item.ease_factor = min(item.ease_factor + 0.1, 3.0)
        item.interval_days = max(1, round(item.interval_days * item.ease_factor)) if item.interval_days else 1
        item.mastery_score = min(item.mastery_score + 0.15 * (1 - item.mastery_score), 1.0)
        item.correct_count += 1
    else:
        item.ease_factor = max(item.ease_factor - 0.2, 1.3)
        item.interval_days = 1
        item.mastery_score = max(item.mastery_score - 0.25 * item.mastery_score, 0.0)
        item.incorrect_count += 1
    item.review_count += 1
    item.last_reviewed_at = now
    item.next_review_due = now + timedelta(days=item.interval_days)
```
All constants (`DECAY_RATE`, `CORRECT_THRESHOLD`, the 0.1/0.15/0.2/0.25 adjustment values) are read from `Config` at startup into a small `SchedulerSettings` object rather than hardcoded as module constants in the final implementation — shown as literals here for readability, per PRD Section 16.6's requirement that these remain tunable without a schema change.

---

## 9. Prompt Contracts

Every LLM call in the system goes through `Generator.generate()` or `Evaluator.evaluate()` with a `task` string, a `context` dict, and an `output_schema` Pydantic model. The `OllamaAdapter` passes `output_schema.model_json_schema()` as the `format` parameter (ADR-06), guaranteeing syntactic JSON validity. Semantic validation (below, per task) still runs on every response.

*(v1.1, ADR-12)*: grading/evaluation tasks — 9.3 (`grade_quiz_answer`), 9.4 (`mini_writing_eval`), 9.5 (`weekly_writing_eval`) — are called with deterministic inference settings (`temperature=0`, fixed `seed` where supported), looked up internally by `OllamaAdapter` from `task`. Generation tasks — 9.1, 9.2, 9.6, 9.7 — retain default sampling for variety; this distinction is not repeated in each subsection below.

*(v1.1, ADR-13)*: 9.3, 9.4, and 9.5's resulting rows also carry `evaluator_provider`/`evaluator_model`/`prompt_version`/`rubric_version`, stamped by the calling service, not the model — also not repeated per subsection.

### 9.1 Parser (`task="parse_note"`)

**Input context:**
```json
{
  "note_content": "<raw markdown text>",
  "recent_item_texts": ["<up to 50 recent LearningItem.text values, for the model's own light dedup awareness>"]
}
```

**Output schema (`ParsedNoteOutput`):**
```python
class ParsedItem(BaseModel):
    item_type: Literal["COLLOCATION", "IDIOM", "PHRASAL_VERB", "GRAMMAR_NOTE", "PERSONAL_EXAMPLE", "CORRECTION"]
    text: str
    definition: str | None = None
    example_sentence: str | None = None
    source_excerpt: str          # verbatim span from note_content this was drawn from
    wrong_form: str | None = None    # only for CORRECTION
    correct_form: str | None = None  # only for CORRECTION

class ParsedNoteOutput(BaseModel):
    items: list[ParsedItem]
```

**Validation rules (beyond schema):**
- `source_excerpt` must be a substring of the original `note_content` (verifiable programmatically) — if not, the item is flagged `low_confidence` in the `ApprovalQueue.reviewed_payload` metadata rather than silently trusted, since it indicates the model paraphrased instead of extracting.
- `item_type == CORRECTION` requires both `wrong_form` and `correct_form` non-null; if either is missing, downgrade the item to `PERSONAL_EXAMPLE` rather than reject the whole note.
- Empty `items: []` is valid (a note with no extractable content) and is not treated as failure.

**Failure handling:** One retry with an appended instruction ("Your previous response did not contain a valid `source_excerpt` for item N — it must be a verbatim quote from the note"). Second failure → `Note.status = PARSE_FAILED`, `AuditLog` entry with the raw response for manual inspection.

### 9.2 Quiz Generator (`task="quiz_{mode}"`, one per quiz mode)

**Input context (example: `quiz_fill_blank`):**
```json
{
  "item": {"text": "break the ice", "definition": "...", "example_sentence": "..."},
  "item_type": "IDIOM"
}
```

**Output schema (`QuizQuestionOutput`):**
```python
class QuizQuestionOutput(BaseModel):
    prompt_text: str
    correct_answer: str | None          # null for open-ended modes (rewrite/conversation/mini_essay)
    distractors: list[str] | None = None  # multiple_choice only, exactly 3 required
```

**Validation rules:**
- `multiple_choice`: `distractors` must have exactly 3 entries, none case-insensitively equal to `correct_answer`.
- `fill_blank`: `prompt_text` must contain a `___` blank marker.
- `error_correction`: the generated `prompt_text` (the flawed sentence) must NOT equal `correct_answer` (i.e., the model must have actually introduced an error).

**Failure handling:** One retry with the specific validation failure named in the retry prompt. Second failure → skip that item for this session (log to `AuditLog`), backfill with the next eligible item rather than failing the whole quiz-generation request.

### 9.3 Quiz Answer Grading (`task="grade_quiz_answer"`, LLM fallback path only)

**Input context:**
```json
{"question_prompt": "...", "expected_answer": "...", "learner_answer": "..."}
```

**Output schema (`GradedAnswerOutput`):**
```python
class GradedAnswerOutput(BaseModel):
    score: float          # 0.0-1.0
    feedback: str          # 1-2 sentences
```
**Validation:** `0.0 <= score <= 1.0` (re-clamped defensively even though schema constrains type, since constrained decoding enforces shape, not numeric range — Section 3, ADR-06 trade-off).

### 9.4 Writing Evaluator — Mini (`task="mini_writing_eval"`)

**Output schema (`MiniWritingEvalOutput`):**
```python
class InlineCorrection(BaseModel):
    wrong: str
    correct: str
    explanation: str

class MiniWritingEvalOutput(BaseModel):
    corrections: list[InlineCorrection]
    naturalness_notes: list[str]   # capped at 2 by prompt instruction; enforced by truncation if the model over-produces
    suggested_items: list[ParsedItem] = []
```
**Validation:** `naturalness_notes` truncated to 2 items post-hoc if the model returns more (not treated as failure — prompt instruction is a soft cap, code enforces the hard cap). *(v1.1)* Each `InlineCorrection` in `corrections` becomes one `PerformanceError` row (Section 6.4) — this is the itemized signal `PerformanceError` is built to capture; `suggested_items` remains the separate, approval-gated path for new knowledge (Section 6.2).

### 9.5 Writing Evaluator — Weekly (`task="weekly_writing_eval"`)

**Input context:**
```json
{
  "submission_text": "...",
  "weak_categories": ["naturalness", "collocations"],
  "known_relevant_items": [{"text": "let down", "definition": "..."}]
}
```

**Output schema (`WeeklyWritingEvalOutput`):**
```python
class DimensionScore(BaseModel):
    score: float          # 0-100
    feedback: str

class WeeklyWritingEvalOutput(BaseModel):
    grammar: DimensionScore
    naturalness: DimensionScore
    vocabulary: DimensionScore
    coherence: DimensionScore
    overall: DimensionScore
    suggested_items: list[ParsedItem] = []
```
**Validation:** all five `score` values in `[0, 100]`, re-clamped defensively; `overall.feedback` must be non-empty (a truly empty overall assessment indicates a degenerate response worth retrying).

**Failure handling:** No retry on semantic grounds (an evaluation with unexpectedly low scores is not a failure). Retry only on schema/range violation. Total failure → `WritingEvaluation.status = EVALUATION_FAILED`, submission preserved, learner can retry manually (PRD Section 18.5).

### 9.6 Weekly Report Narrative (`task="weekly_narrative"`)

**Output schema (`WeeklyNarrativeOutput`):**
```python
class WeeklyNarrativeOutput(BaseModel):
    narrative_report: str            # 150-300 words, soft-enforced by prompt
    top_strengths_this_week: list[str]
    top_focus_areas_next_week: list[str]
```
**Validation:** word count checked post-hoc; outside 100-400 words is logged as a quality warning (not a hard failure — a slightly long/short narrative is still usable).

### 9.7 Topic Generation (`task="weekly_topic"`)

**Output schema (`TopicOutput`):**
```python
class TopicOutput(BaseModel):
    topic: str
    prompt_text: str    # the actual instruction shown to the learner
```
**Validation:** `topic` must not fuzzy-match (case-insensitive substring) any of the last 12 topics passed in context — checked in code, not trusted to the model's own avoidance instruction; on match, one retry with the offending topic explicitly excluded.

---

## 10. State Machines

### 10.1 Note

```
      ┌─────┐
      │ NEW │
      └──┬──┘
         │ IngestionService.process_note() starts
         ▼
   ┌───────────┐
   │ PARSING    │
   └─────┬─────┘
         │
   ┌─────┴──────────────────┐
   │ schema-valid response    │ repeated failure (after 1 retry)
   ▼                         ▼
┌──────────────────┐   ┌──────────────┐
│ PENDING_APPROVAL   │   │ PARSE_FAILED  │
└─────────┬─────────┘   └──────────────┘
          │ all ApprovalQueue items for this note reviewed
          ▼
    ┌───────────┐
    │ PROCESSED  │──── file modified later ────▶ (status unchanged, changed_since_processed=true)
    └───────────┘
```

### 10.2 ApprovalQueue item

```
┌─────────┐   approve()        ┌──────────┐
│ PENDING  │────────────────────▶ APPROVED  │──▶ LearningItem/LearningCorrection row created   [renamed v1.1]
└────┬────┘                    └──────────┘
     │ approve_edited(payload)  ┌──────────────────┐
     ├─────────────────────────▶ EDITED_APPROVED     │──▶ LearningItem/LearningCorrection row created with edited values   [renamed v1.1]
     │                          └──────────────────┘
     │ reject()                 ┌──────────┐
     └─────────────────────────▶ REJECTED   │──▶ no LearningItem created; row retained for audit
                                └──────────┘
(all three target states are terminal — no reopening in MVP)
```

*(v1.1)* `PerformanceError` has no state machine of its own — per Section 7.1, it's written once at grading time and never transitions, consistent with it being a factual record rather than reviewable content.

### 10.3 QuizSession

```
┌───────────────┐  first question generated   ┌──────────────┐  all answers graded   ┌────────────┐
│ (created)       │─────────────────────────────▶ IN_PROGRESS   │───────────────────────▶ COMPLETED   │
└───────────────┘                              └──────┬───────┘                       └────────────┘
                                                        │ learner abandons (never submits answers)
                                                        ▼
                                                (session simply never reaches COMPLETED;
                                                 no mastery updates applied for its questions;
                                                 no explicit ABANDONED state needed for MVP)
```

### 10.4 WritingSubmission / WritingEvaluation

```
┌───────────┐   Evaluator.evaluate() called   ┌────────────┐
│ SUBMITTED  │─────────────────────────────────▶ EVALUATING  │
└───────────┘                                  └─────┬──────┘
                                                       │
                              ┌────────────────────────┴────────────────────────┐
                              │ success                                          │ failure (timeout / repeated schema failure)
                              ▼                                                  ▼
                       ┌────────────┐                                    ┌────────────────────┐
                       │ EVALUATED   │                                    │ EVALUATION_FAILED    │──▶ manual retry available
                       └────────────┘                                    └────────────────────┘
```

---

## 11. Error Handling

### 11.1 Expected Failure Modes & Recovery

| Failure | Detection | Recovery Strategy | Retry Policy |
|---|---|---|---|
| Ollama host unreachable / connection refused | `httpx.ConnectError` on adapter call | Surface as a clear error to caller; for parsing, `Note.status = PARSE_FAILED`; for quiz/writing (synchronous, ADR-08), return HTTP 502 with a learner-facing message ("The AI model host is unreachable — check Ollama is running") | 2 retries with exponential backoff (1s, 3s) before surfacing failure |
| Ollama response times out | `httpx.TimeoutException` | Same as above | Timeout set to 120s per call (generous, per ADR-08's acceptance of blocking requests); no retry on timeout itself (retrying a slow host rarely helps) — surfaced immediately |
| Schema-valid but semantically wrong output (e.g., empty `distractors`) | Post-parse validation rules (Section 9, per task) | One retry with the specific violation named in an appended correction instruction | 1 retry, then task-specific fallback (skip item / mark failed) |
| Malformed JSON despite `format` constraint (rare — model/runtime bug) | `pydantic.ValidationError` on `model_validate_json()` | Same retry path as semantic failure | 1 retry, then fail per task |
| SQLite database locked (writer contention) | `sqlite3.OperationalError: database is locked` | WAL mode minimizes this; if it still occurs, SQLAlchemy's connection-level retry with short backoff | 3 retries, 100ms/300ms/900ms backoff |
| SQLite file corruption | `PRAGMA integrity_check` fails (run at FastAPI startup, mirroring the reference document's own pattern) | Show a recovery notice; offer restore from most recent backup (`BackupService.list_backups()` → `restore(path)`) | Manual, learner-initiated restore — no automatic overwrite of a corrupted file without confirmation |
| Obsidian note deleted/moved after being queued for parsing | `FileNotFoundError` on read in `IngestionService` | `Note.status = PARSE_FAILED`, `AuditLog` note; no crash | No retry (file is gone) |
| Vault path misconfigured / inaccessible at startup | `VaultWatcher` fails to start Observer | Log clearly, keep the rest of the API functional (ingestion simply won't happen), surface a persistent warning banner via `GET /dashboard/overview` health field | N/A — requires config fix + restart |
| Concurrent approval of the same `ApprovalQueue` item (double-click) | `ApprovalQueue.status != PENDING` check inside the transaction | Second request returns HTTP 409 Conflict, no duplicate `LearningItem` created | N/A — idempotency check, not a retry scenario |

### 11.2 General Retry Discipline

All LLM-call retries (Section 9's per-task rules) share one implementation: `OllamaAdapter._call_with_retry(request, retries=1)`. This keeps the retry policy centralized rather than duplicated per pipeline — pipelines only specify *what* the correction instruction should say on retry, not *how* retrying works.

---

## 12. Configuration

### 12.1 Environment Variables (`.env`, loaded via `pydantic-settings`)

```
# app/config.py
PRAXIS_DB_PATH=./data/praxis.db
PRAXIS_VAULT_PATH=/path/to/obsidian/vault/EnglishNotes
PRAXIS_BACKUP_DIR=./data/backups
PRAXIS_BACKUP_RETENTION_DAILY=14
PRAXIS_BACKUP_RETENTION_MONTHLY=6

OLLAMA_HOST=http://localhost:11434    # or a remote hosted address
OLLAMA_MODEL=gemma4:31b
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_MAX_RETRIES=1

PRAXIS_LOG_LEVEL=INFO
```

### 12.2 Runtime-Adjustable Config (`Config` table, editable via Settings screen)

Values that are reasonable to tune after observing real usage without a redeploy: `decay_rate`, `correct_threshold`, `mastery_adjust_up`, `mastery_adjust_down`, `category_balance_ratio`, `proficiency_blend_item_weight` / `proficiency_blend_writing_weight` (PRD Section 17.4). These live in the DB `Config` table (not `.env`) specifically because they're the parameters flagged as "revisit after real usage" in PRD Section 23 — making them DB-editable via the Settings screen means tuning them doesn't require a restart or a code change.

### 12.3 Why the split

Infrastructure-level config (paths, model host/name, timeouts) lives in `.env` because it's set once per machine and rarely changes. Behavior-tuning config lives in the DB because it's expected to change based on observed learning data, and the Settings screen is the appropriate place for the learner to adjust it without touching a text file.

---

## 13. Security

Even as a local, single-user, non-networked (beyond the LLM host) application, the following are worth explicit treatment:

### 13.1 Prompt Injection

The learner's own notes and writing submissions are untrusted input from the model's perspective (a note could, in principle, contain text that looks like an instruction — e.g., copy-pasted from somewhere). Mitigations:
- All user content is passed as `context` data within the structured prompt template, never concatenated into the system/instruction portion of the prompt.
- Output is always constrained by `format` (ADR-06) — even if injected text influenced the model's reasoning, the response shape is still enforced.
- The blast radius of a successful injection is bounded by the approval gate (ADR-05): even a maximally manipulated parser response can only ever produce `ApprovalQueue` candidates, never a direct `LearningItem` write. Worst case is a bad suggestion the learner rejects, not a corrupted knowledge base.

### 13.2 Malformed Parser/Evaluator Output

Covered structurally in Section 9 (schema validation) and Section 11 (retry/failure handling) — output is never trusted without `model_validate_json()` succeeding first.

### 13.3 Corrupted Notes

Non-UTF-8 or otherwise unreadable Markdown files are caught at the file-read step in `IngestionService`; the note is marked `PARSE_FAILED` with the decode error logged, rather than crashing the watcher thread (which would silently stop all future ingestion — a single bad file must never take down the watcher).

### 13.4 Database Corruption

Startup `PRAGMA integrity_check` (Section 11.1) plus the daily backup rotation (Section 6.7) together bound the worst case to "at most one day of data re-entry," never total loss.

### 13.5 Backup Recovery

`BackupService.restore(path)` is a deliberately manual, learner-confirmed action (not automatic) — reasoning: an automatic silent restore risks overwriting a merely-briefly-locked database with a stale backup, which is worse than a clear error prompting the learner to choose.

### 13.6 What's explicitly out of scope

No encryption at rest, no OS-level file permission hardening beyond defaults, no network-facing attack surface (the API binds to `localhost` only by default configuration). All explicitly acceptable given the single-device, non-networked deployment model (PRD Section 8) — revisit only if the extensibility path toward multi-device access (Section 15.5) is ever taken.

---

## 14. Performance

### 14.1 Expected Scale

- **Rows:** low thousands of `LearningItem` rows even after multiple years of daily use (roughly 5-10 items/day × ~300 study days/year ≈ 1,500-3,000/year). SQLite handles this scale trivially — no partitioning, no read-replica, no caching layer needed.
- **Concurrent users:** exactly one.
- **Request volume:** dozens of requests per active session, not sustained load.

### 14.2 Performance Assumptions

- Dashboard aggregation queries (`GROUP BY` over `LearningItem`/`QuizQuestion`) run in well under 50ms at this row count on any modern laptop — no caching layer needed for MVP.
- FTS5 `MATCH` queries against a few thousand rows are similarly sub-millisecond.
- The actual latency bottleneck end-to-end is always the LLM call (seconds to ~a minute), never the database — this is why ADR-08 (synchronous endpoints) is an acceptable trade-off: the DB work around the LLM call is noise by comparison.

### 14.3 Caching

None implemented in MVP beyond TanStack Query's default client-side cache (which is about avoiding redundant *requests*, not about server-side computation cost — there is no expensive server-side computation to cache at this scale). If dashboard aggregation ever becomes measurably slow (unlikely, but worth naming the threshold): the first response would be adding targeted indexes before reaching for a caching layer, since the query patterns here are simple aggregations over indexed columns, not the kind of workload caching typically helps with.

---

## 15. Extensibility

Concrete implementation-level extension points, elaborating PRD Section 21:

### 15.1 New LLM Providers

Add a new class implementing `Generator`/`Evaluator` (e.g., `ClaudeAdapter`, `GeminiAdapter`) in `app/llm/`. Change `OLLAMA_MODEL`-equivalent config to select it per-pipeline if desired (e.g., `EVALUATOR_PROVIDER=claude`, `GENERATOR_PROVIDER=ollama` as two independent settings rather than one global model choice) — this two-setting split is a small, deliberate addition beyond the PRD's single `model_name` value, specifically to enable the "frontier model for evaluation only" path called out as a real possibility in the PRD's product philosophy discussion, without requiring a second architectural pass when that day comes.

### 15.2 New Quiz Types

Add a new `Literal` value to the `quiz_mode` enum, a new prompt template in `app/llm/prompts/quiz.py`, and a new grading branch in `app/quizzes/grading.py`. No schema migration needed beyond the enum value itself (SQLite stores enums as `TEXT`, so adding a new allowed value is a non-breaking application-level change).

### 15.3 Speech/Listening Modules

New `item_type` values (`PRONUNCIATION_NOTE`, etc.), a new `AudioEvaluator` protocol alongside the existing `Evaluator` (since audio evaluation has a fundamentally different input shape — bytes, not text), and new frontend feature folders (`features/speaking/`). The `ApprovalService`/`SchedulerModule`/`RetrievalService` core requires zero changes — they already operate generically over `LearningItem` rows regardless of what skill domain produced them.

### 15.4 General Subject Coaching (beyond English)

`Source`/`Lesson`/`LearningItem`/`LearningCorrection`/`PerformanceError` are already domain-generic at the schema level (PRD Section 21.4). The English-specific surface area is entirely in `item_type` enum values and prompt template content — both cheap to extend or parameterize (e.g., a `subject` field added to `Source`, prompt templates parameterized by subject) without touching the ingestion/approval/scheduler core.

### 15.5 Multi-Device Access

The FastAPI/SQLite boundary is the seam (ADR-01). Concretely: swap SQLite for networked Postgres (SQLModel's SQLAlchemy foundation supports this with a connection-string change and minimal query adjustments, since both are ANSI-SQL-compatible for the query patterns used here), add a thin auth layer (single-user token auth is sufficient — still no need for full multi-tenancy), and either expose FastAPI on the local network or deploy it to a small always-on host. The Obsidian vault-watching piece would need its own resolution (likely: the vault stays local and syncs via existing tools like Obsidian Sync/Syncthing, with `VaultWatcher` remaining wherever the vault physically lives) — explicitly flagged as the one part of this extension path that isn't a clean architectural seam today, since it currently assumes co-location with the vault.

---

## 16. Implementation Risks

Ranked by combination of likelihood and blast radius:

| Risk | Why it's high-risk | Architectural mitigation already in place |
|---|---|---|
| **Prompt/schema iteration churn.** Real-world model output quality (especially for `naturalness` judgments and parser extraction accuracy) will very likely require multiple rounds of prompt tuning after real usage begins — this is inherent to LLM-backed features, not a design flaw. | High likelihood, moderate cost per iteration. | Prompt templates are isolated in `app/llm/prompts/`, decoupled from orchestration logic in the service layer — tuning a prompt never requires touching `QuizService`/`WritingService` code. |
| **Watcher-thread + FastAPI lifecycle interaction bugs.** Background-thread-writes-to-shared-SQLite-via-WAL is a well-understood pattern but is exactly the kind of code that's easy to get subtly wrong (session lifecycle, thread-local connections) on first implementation. | Moderate likelihood, high cost if wrong (silent data loss or missed ingestion events). | Isolated to `app/ingestion/watcher.py`; integration tests (Section 17) specifically target this boundary with real file-write simulation, not just mocked calls. *(v1.1)* ADR-11's debounce + hash-compare logic additionally closes the specific sub-risk of duplicate/missed ingestion from atomic-save event patterns, which was previously an unstated assumption rather than a handled case. |
| **Ollama structured-output reliability at the chosen model size.** Section 3/ADR-06's confidence in schema-constrained decoding is based on documented Ollama behavior, but real reliability (especially for deeply nested schemas, per known community-reported limitations) needs validation against the actual model chosen once selected. | Moderate likelihood, moderate cost (mitigated by retry logic, but repeated failures degrade UX). | Retry-with-correction-instruction pattern (Section 11) plus per-task semantic validation (Section 9) are already the second line of defense, not solely relying on `format` constraint. |
| **Blocking synchronous requests (ADR-08) under a genuinely slow model host.** If the chosen hosted model is slower than anticipated, quiz/writing requests could take minutes, which is a poor experience even if technically correct. | Low-moderate likelihood, low cost (documented, accepted trade-off with a known upgrade path). | ADR-08 explicitly names background-job polling as the direct successor pattern if this becomes a real problem — no architectural rework needed, just adding a job table and a polling endpoint. |
| **FTS5 lexical-only duplicate/relevance matching producing noisy results.** Already flagged in the PRD (Section 15.1) as an accepted limitation. | Moderate likelihood of *some* noise, low cost (human approval gate absorbs it). | Approval gate (ADR-05) is the primary mitigation; semantic search is the named upgrade path if needed (Section 15's extensibility notes plus PRD 21.2). |
| **Evaluation scores drifting across sessions for reasons unrelated to real progress.** *(v1.1)* A local model's grading can vary run-to-run, and the model/prompt/rubric themselves will likely change over the project's life (Section 16's top risk, above) — either can make a trend chart misleading if not accounted for. | Moderate likelihood, moderate cost (undermines the "trend visibility" success metric, PRD Section 26, if unaddressed). | ADR-12 (deterministic temperature/seed for grading calls) reduces run-to-run noise; ADR-13 (evaluator/prompt/rubric version stamped on every graded row) means any remaining discontinuity is at least explainable and attributable after the fact, rather than presented as unexplained signal. Neither fully eliminates the risk — only makes it visible and bounded. |

---

## 17. Testing Strategy

### 17.1 Philosophy

Praxis is a solo-maintained personal tool, not a team-maintained product — the testing strategy optimizes for **catching regressions in the parts most likely to silently break** (state transitions, mastery math, schema validation) rather than exhaustive coverage of every UI interaction. The `Generator`/`Evaluator` interface exists partly *because* it makes the single most unpredictable dependency in the system (an LLM) trivially mockable — this is the architectural decision that makes the rest of the system testable at all without a live model host.

### 17.2 Testing Boundaries

| Layer | Test type | What's tested | What's mocked |
|---|---|---|---|
| `app/scheduler/mastery.py` | Unit | Pure functions (`update_mastery`, `decayed_score`) — deterministic input/output, no I/O | Nothing to mock; pure functions |
| `app/quizzes/grading.py` | Unit | Deterministic grading logic (string normalization, MC matching) | LLM fallback path mocked via a stub `Evaluator` |
| `app/llm/schemas.py` validation rules (Section 9) | Unit | Each task's post-parse validation rules against hand-crafted valid/invalid payloads | N/A — testing pure validation functions |
| `app/ingestion/service.py` | Integration | Full parse → validate → duplicate-check → `ApprovalQueue` write, against a temp SQLite DB | `Generator` replaced with a `FakeGenerator` returning fixture `ParsedNoteOutput` payloads (valid, invalid, and edge-case fixtures — empty items, injected `source_excerpt` mismatch, etc.) |
| `app/approvals/service.py` | Integration | Approve/edit-approve/reject transitions, the "only writer of `LearningItem`/`LearningCorrection`" invariant *(v1.1)*, double-approval 409 handling | Nothing — this is pure DB logic |
| `app/quizzes/service.py`, `app/writing/service.py`, `app/reports/service.py` | Integration | Full orchestration flow against a temp DB with a `FakeGenerator`/`FakeEvaluator`, including that incorrect quiz answers and mini-writing corrections produce `PerformanceError` rows directly with no approval step *(v1.1)* | LLM calls entirely mocked; tests assert on the DB state and returned payload shape, not on any real model output quality |
| `app/ingestion/watcher.py` | Integration | Real `watchdog` Observer against a temp directory, simulating actual file writes (including an atomic write-then-rename, a rapid-fire duplicate-event burst, and a same-content re-save), asserting: exactly one `IngestionService.process_note()` call per genuine content change, zero calls for a same-content re-save, and `Note` rows created/updated correctly regardless of which raw event type fired *(v1.1, ADR-11 — this is the test that actually validates the debounce/hash-compare logic, not just the happy path)* | `Generator` mocked as above; this is the one place a *real* filesystem is used rather than a pure in-memory fixture, since the watcher's correctness is specifically about real OS file events (Section 16's named risk) |
| `OllamaAdapter` itself | Integration (optional, opt-in) | A small suite that runs only when `OLLAMA_HOST` is reachable (skipped in CI/offline dev), asserting the adapter correctly round-trips a real schema-constrained call | N/A by design — this is the one suite intentionally *not* mocked, to occasionally validate ADR-06's real-world assumption |
| Frontend feature hooks | Unit (Vitest + React Testing Library) | Hooks correctly call the right endpoint shape and handle loading/error/success states | `api/client.ts` mocked at the fetch layer |
| Frontend components | Component tests | Key interactive components (`ApprovalCard`, `QuestionCard` per quiz type, `WritingEditor`) render correctly given fixture data and fire the right mutation on interaction | All server calls mocked |
| End-to-end | Manual, not automated, for MVP | The full Flow 1-5 sequences (PRD Section 10) walked through by hand against a real (or realistic fixture) Obsidian vault before declaring a phase complete (PRD Section 25's MVP checklist) | N/A — explicitly deferred; an automated E2E suite (Playwright, etc.) is reasonable future work once the UI stabilizes, not before |

### 17.3 The `FakeGenerator`/`FakeEvaluator` Pattern

```python
# tests/fixtures/fake_llm.py
class FakeGenerator:
    def __init__(self, responses: dict[str, BaseModel]):
        self._responses = responses  # keyed by task name

    async def generate(self, task: str, context: dict, output_schema: type[BaseModel]) -> BaseModel:
        return self._responses[task]
```
Injected via FastAPI's dependency override (`app.dependency_overrides[get_generator] = lambda: FakeGenerator({...})`) in integration tests — no test ever makes a real network call to Ollama except the opt-in suite described above.

### 17.4 What Is Explicitly Not Tested at MVP Scope

- LLM output *quality* (naturalness judgment accuracy, parser extraction precision/recall) — this is a product-quality concern validated by the learner's own real usage and spot-checking (PRD Section 22's risk mitigation), not something a unit test can meaningfully assert.
- Load/performance testing — unjustified at single-user scale (Section 14).
- Cross-browser frontend testing — a personal tool used by its own developer on one known browser/OS combination.

---

## 18. Future Improvements

Explicitly distinguishing MVP / Future / Out of Scope, consolidating decisions made throughout this document:

### MVP (this document's scope)
- Everything specified in Sections 1-17 above, matching PRD Sections 24-25's phased roadmap and MVP definition.

### Future Work (not blocked by this architecture; additive when needed)
- Background job queue + polling pattern for LLM calls, if synchronous requests (ADR-08) prove genuinely limiting.
- Semantic/embedding-based retrieval alongside FTS5 (ADR-07's named upgrade path), if lexical matching proves insufficient for writing-evaluation context relevance.
- A second `Generator`/`Evaluator` adapter (frontier API model) for writing evaluation specifically, if open-model naturalness judgment proves unreliable (Section 16's top risk).
- Automated end-to-end test suite once the frontend UI stabilizes past initial iteration.
- Speech/listening modules, general-subject extensibility, multi-device access (Section 15.3-15.5).

### Out of Scope (not a near-term roadmap item; would require revisiting product decisions, not just architecture)
- Multi-user support / authentication beyond single-device trust.
- Cloud-hosted deployment as the primary mode (vs. the learner optionally pointing local backups at their own sync folder).
- Any engagement/gamification mechanic — excluded by product philosophy, not by technical difficulty.
- Certification-equivalent scoring claims (CEFR/IELTS equivalence) — a product-policy exclusion, not a technical one.

---

## Appendix: Key Dependencies

| Package | Purpose | Version Constraint |
|---|---|---|
| `fastapi` | Web framework | `^0.115.0` |
| `uvicorn[standard]` | ASGI server | `^0.32.0` |
| `sqlmodel` | ORM + Pydantic schema unification | `^0.0.22` |
| `alembic` | DB migrations | `^1.13.0` |
| `pydantic-settings` | `.env`-backed configuration | `^2.6.0` |
| `httpx` | Async HTTP client (Ollama adapter calls) | `^0.27.0` |
| `watchdog` | Obsidian vault filesystem observer | `^5.0.0` |
| `python-multipart` | Form/file handling (if ever needed for uploads) | `^0.0.12` |
| `pytest`, `pytest-asyncio` | Backend test runner | latest stable |
| `ruff` | Linting/formatting (single-tool choice, minimal tooling surface for a solo maintainer) | latest stable |
| **Frontend** | | |
| `react`, `react-dom` | UI framework | `^18.3.0` |
| `typescript` | Type safety | `^5.6.0` |
| `vite` | Build tool / dev server | `^5.4.0` |
| `@tanstack/react-query` | Server-state management | `^5.59.0` |
| `react-router-dom` | Client-side routing | `^6.27.0` |
| `tailwindcss` | Styling | `^3.4.0` |
| `recharts` | Dashboard trend/mastery charts | `^2.13.0` |
| `vitest`, `@testing-library/react` | Frontend testing | latest stable |

---

*This document is the implementation-ready technical reference for the Praxis MVP. It is intended to be sufficient, on its own alongside the PRD, to generate a complete implementation task plan without a further design phase. Architecture decisions recorded here (Section 3) are considered final for MVP scope unless real implementation or usage surfaces a concrete reason to revisit — see Section 18 for the pre-identified, non-blocking revision paths.*
