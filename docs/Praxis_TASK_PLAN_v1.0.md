# Task Plan

## Praxis — Personal AI English Learning Coach — MVP

**For:** Solo Developer (executing via Claude Code)
**Source:** `ARCHITECTURE.md` v1.1 · `PRD.md` v1.0
**Format:** Epic → Feature → Tasks
**Total Epics:** 11
**Total Tasks:** 130
**Last Updated:** 2026-07-13
**Status:** Draft — ready to execute from Epic 1

---

## How to Read This Document

**Epic** — A major architectural milestone. One epic = one implementation chat
session. All tasks in an epic are completed before the next epic begins.

**Feature** — A coherent group of tasks within an epic. One feature produces
a testable, working slice of the epic's functionality.

**Task** — A single atomic unit of work. One task = one prompt to Claude Code.
Tasks are written as imperatives. Each task references the source document
section it implements and specifies its exact output.

**Task format:**
```
- [ ] T[Epic].[Feature].[N] — [Imperative description]
      Ref: [PRD section / ARCHITECTURE section]
      Output: [File path(s) or observable behavior]
```

**Task status:**
- `[ ]` Not started
- `[~]` In progress
- `[x]` Done

**Documentation note:** This project has no separate `DOCUMENTATION_STANDARDS.md`.
Every task that creates a new file implicitly requires a module-level docstring
and a docstring on every public class/function, consistent with the style
already used throughout `ARCHITECTURE.md`'s own code samples (Sections 8, 9).
This is not restated in every task below.

---

## Scope Summary

| Epic | Title | Features | Tasks |
|---|---|---|---|
| E1 | Foundation & Core Infrastructure | 6 | 22 |
| E2 | LLM Infrastructure & Prompt Contracts | 4 | 15 |
| E3 | Vault Watcher & Ingestion Pipeline | 3 | 10 |
| E4 | Approval Workflow | 4 | 10 |
| E5 | Scheduler & Retrieval | 3 | 9 |
| E6 | Quiz Engine | 5 | 12 |
| E7 | Writing Evaluation | 5 | 12 |
| E8 | Weekly Reports | 4 | 7 |
| E9 | Dashboard | 4 | 12 |
| E10 | Backup & Settings | 4 | 10 |
| E11 | Polish, Edge Cases & QA Hardening | 4 | 11 |
| **Total** | | **46** | **130** |

---

## Epic Order & Dependencies

```
E1 (Foundation) → all other epics depend on this

E2 (LLM Infrastructure)
    ↓
E3 (Vault Watcher & Ingestion)
    ↓
E4 (Approval Workflow)
    ↓
E5 (Scheduler & Retrieval)                    E10 (Backup & Settings)
    ↓                                          ↑ hooks into E4's ApprovalService,
E6 (Quiz Engine)                                only needs E1 + E4 to start —
    ↓                                          runs in parallel with E5–E9
E7 (Writing Evaluation)                                 │
    ↓                                                    │
E8 (Weekly Reports)  ←── needs both E6 and E7             │
    ↓                                                    │
E9 (Dashboard)  ←── aggregates E5/E6/E7/E8 data           │
    ↓                                                    │
    └──────────────────────┬───────────────────────────┘
                            ▼
                  E11 (Polish + QA Hardening)
```

> **Critical path:** E1 → E2 → E3 → E4 → E5 → E6 → E7 → E8 → E9 → E11
>
> **Parallel branch:** E10 can start as soon as E4 is complete (it needs
> `ApprovalService` to exist so its post-approval-commit backup hook has
> something to attach to — Architecture Section 6.7) and does not need to
> wait for E5–E9. Merge E10 before starting E11.
>
> **Ordering rule:** No epic starts until every epic it depends on above is
> fully complete and its own tests pass. Within each epic: models/schema →
> service logic → API router → frontend → tests, in that order, never reversed.

---

---

# EPIC 1 — Foundation & Core Infrastructure

> Every other epic depends on this. Produces no user-facing feature, but
> everything else is built on top of it.

**What "done" means for this epic:**
- Backend starts with `uvicorn app.main:app` without errors, `/health` returns 200 and includes a successful `PRAGMA integrity_check` result
- All 15 SQLModel tables exist in the SQLite file after running Alembic migrations, including the `learning_item_fts` virtual table and its three sync triggers
- `Generator`/`Evaluator` Protocols exist and a `FakeGenerator`/`FakeEvaluator` can be injected via FastAPI dependency override in a test
- Frontend starts with `npm run dev`, renders a shell with all six route stubs (Dashboard/Approvals/Quizzes/Writing/Reports/Settings) navigable via React Router
- `ruff check` and `tsc --noEmit` both pass with zero warnings on the scaffolded project

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 12 (Database Design) · Section 8 (NFRs)
docs/ARCHITECTURE.md   ← Section 2 (Principles) · Section 3 (ADR-01, ADR-02, ADR-06) ·
                          Section 4 (Component/Project Structure) · Section 7 (Data Architecture) ·
                          Section 8 (Database Schema) · Appendix (Key Dependencies)
```

---

## Feature 1.1 — Backend Project Setup

- [ ] T1.1.1 — Initialize the backend Python project: `pyproject.toml` with all
      dependencies pinned per the Appendix version constraints; create the full
      `backend/app/` directory structure (empty `__init__.py` files in every
      package) exactly as laid out in Architecture Section 4.3
      Ref: ARCHITECTURE Appendix (Key Dependencies) · Section 4.3 (Backend Project Structure)
      Output: `backend/pyproject.toml` · full `backend/app/` tree · `backend/tests/` tree

- [ ] T1.1.2 — Implement application configuration: `pydantic-settings` `Settings`
      class covering every `.env` variable listed in Architecture Section 12.1;
      create `.env.example` with all defaults filled in
      Ref: ARCHITECTURE Section 12.1 (Environment Variables)
      Output: `backend/app/config.py` · `backend/.env.example`

- [ ] T1.1.3 — Implement the FastAPI app skeleton: `main.py` with an (initially
      empty) `lifespan` context manager stub, permissive local-only CORS for the
      Vite dev server origin, and a `GET /health` endpoint that runs
      `PRAGMA integrity_check` against the configured DB and reports the result
      Ref: ARCHITECTURE Section 11.1 (SQLite file corruption) · Section 13.4 (Database Corruption)
      Output: `backend/app/main.py` — `uvicorn app.main:app` starts; `GET /health` returns 200

---

## Feature 1.2 — Database Models (Core Entities)

- [ ] T1.2.1 — Implement `Source` and `Lesson` SQLModel tables
      Ref: ARCHITECTURE Section 7 (ER summary) · PRD Section 12 (Entity: Source, Lesson)
      Output: `backend/app/db/models/source.py`

- [ ] T1.2.2 — Implement the `Note` SQLModel table with `NoteStatus` enum and
      the unique index on `vault_path`
      Ref: ARCHITECTURE Section 8 (`Note` definition) · Section 7.2 (`idx_note_vault_path`, `idx_note_status`)
      Output: `backend/app/db/models/note.py`

- [ ] T1.2.3 — Implement the `ApprovalQueue` SQLModel table with
      `ApprovalSourceType`/`ApprovalStatus` enums and the `reviewed_payload` JSON column
      Ref: ARCHITECTURE Section 8 (`ApprovalQueue` definition, v1.1 `item_type` note)
      Output: `backend/app/db/models/approval.py`

- [ ] T1.2.4 — Implement `LearningItem` with `ItemType` enum, all mastery/scheduling
      fields, and `Tag`/`LearningItemTag` join table
      Ref: ARCHITECTURE Section 8 (`LearningItem` definition) · Section 7.2 (indexes)
      Output: `backend/app/db/models/learning_item.py`

- [ ] T1.2.5 — Implement `LearningCorrection` and `PerformanceError` as two
      separate SQLModel tables (v1.1 split — do not recreate the old v1.0
      `Correction` entity); `PerformanceError` must have no status/lifecycle field
      Ref: ARCHITECTURE Section 8 (`LearningCorrection`, `PerformanceError` definitions, ADR-05)
      Output: `backend/app/db/models/learning_correction.py` · `backend/app/db/models/performance_error.py`

- [ ] T1.2.6 — Implement `QuizSession` and `QuizQuestion`, including the four
      v1.1 evaluation-metadata columns on `QuizQuestion`
      (`evaluator_provider`, `evaluator_model`, `prompt_version`, `rubric_version`, all nullable)
      Ref: ARCHITECTURE Section 8 (v1.1 note on `QuizQuestion`) · Section 7.1 (ADR-13 evaluation metadata) · PRD Section 12
      Output: `backend/app/db/models/quiz.py`

- [ ] T1.2.7 — Implement `WritingPrompt`, `WritingSubmission`, and
      `WritingEvaluation`, including the same four v1.1 evaluation-metadata columns
      on `WritingEvaluation`
      Ref: ARCHITECTURE Section 8 (v1.1 note) · PRD Section 12
      Output: `backend/app/db/models/writing.py`

- [ ] T1.2.8 — Implement `WeeklyReport`, `Config` (key-value), and `AuditLog`
      Ref: PRD Section 12 (Entity: WeeklyReport, Config, AuditLog)
      Output: `backend/app/db/models/report.py` · `backend/app/db/models/system.py`

---

## Feature 1.3 — Migrations, Engine & Indexes

- [ ] T1.3.1 — Set up Alembic (`alembic init`, configure `env.py` to import all
      SQLModel metadata) and generate the initial migration creating all 15 tables
      from Feature 1.2
      Ref: ARCHITECTURE Section 3 (ADR-02) · Section 4.3 (`migrations/`)
      Output: `backend/alembic.ini` · `backend/app/db/migrations/` · migration applies cleanly to a fresh SQLite file

- [ ] T1.3.2 — Write a hand-authored Alembic migration creating the
      `learning_item_fts` FTS5 virtual table and its three sync triggers
      (`learning_item_ai`, `learning_item_ad`, `learning_item_au`) exactly as
      specified; this must be the only mechanism that ever writes to the FTS5 table
      Ref: ARCHITECTURE Section 7.3 (FTS5 virtual table + triggers, v1.1 clarification)
      Output: new file in `backend/app/db/migrations/versions/` — inserting/updating/deleting a `LearningItem` row is reflected in `learning_item_fts` with no application code touching it

- [ ] T1.3.3 — Write a migration adding the composite indexes not expressible
      via SQLModel's single-column `Field(index=True)`: `(item_type, suspended)`
      on `learning_item`, `(source_type, source_id)` on `performance_error`,
      `(learning_item_id, created_at)` on `performance_error`
      Ref: ARCHITECTURE Section 7.2 (Indexes table)
      Output: new file in `backend/app/db/migrations/versions/`

- [ ] T1.3.4 — Implement `engine.py`: SQLModel engine construction pointed at
      `Settings.db_path`, connection-level `PRAGMA journal_mode=WAL` and
      `PRAGMA foreign_keys=ON`, and a `get_session()` FastAPI dependency
      Ref: ARCHITECTURE Section 3 (ADR-01, WAL mode) · Section 7.1 (foreign key enforcement)
      Output: `backend/app/db/engine.py`

---

## Feature 1.4 — LLM Abstraction Skeleton & Test Fixtures

- [ ] T1.4.1 — Define the `Generator` and `Evaluator` `Protocol` classes exactly
      as specified (no concrete implementation yet — that's Epic 2)
      Ref: ARCHITECTURE Section 3 (ADR-06 code block)
      Output: `backend/app/llm/interface.py`

- [ ] T1.4.2 — Implement `FakeGenerator`/`FakeEvaluator` test fixtures that
      return pre-registered responses keyed by `task` name
      Ref: ARCHITECTURE Section 17.3 (`FakeGenerator`/`FakeEvaluator` Pattern)
      Output: `backend/tests/fixtures/fake_llm.py`

- [ ] T1.4.3 — Set up pytest scaffolding: a `conftest.py` fixture providing a
      temp-file SQLite `Session` per test (not in-memory, since WAL-mode behavior
      matters — Section 3 ADR-01), and a documented pattern for overriding
      `get_generator`/`get_evaluator` FastAPI dependencies with the fakes from T1.4.2
      Ref: ARCHITECTURE Section 17.1 (Testing Philosophy) · Section 17.3
      Output: `backend/tests/conftest.py` — a trivial smoke test using the temp DB fixture passes

---

## Feature 1.5 — Frontend Project Setup & Shell

- [ ] T1.5.1 — Initialize the frontend project: Vite + React + TypeScript
      template, Tailwind CSS configured, `react-router-dom` and
      `@tanstack/react-query` installed
      Ref: ARCHITECTURE Section 3 (ADR-09) · Appendix (Key Dependencies — Frontend)
      Output: `frontend/package.json` · `frontend/tailwind.config.ts` · `frontend/vite.config.ts`

- [ ] T1.5.2 — Implement `api/client.ts`: a thin `fetch` wrapper (base URL from
      an env var, JSON parsing, normalized error shape) and a starter
      `api/types.ts` file with TypeScript interfaces mirroring the backend's
      core Pydantic/SQLModel schemas produced so far (`Note`, `ApprovalQueue`, `LearningItem`)
      Ref: ARCHITECTURE Section 4.4 (Frontend Project Structure — `api/`) · Section 5 (Component Interaction)
      Output: `frontend/src/api/client.ts` · `frontend/src/api/types.ts`

- [ ] T1.5.3 — Implement `App.tsx` with `react-router-dom` routes for all six
      feature pages (initially rendering placeholder text) and wrap the app in
      a `QueryClientProvider`
      Ref: ARCHITECTURE Section 4.4 (feature folder list) · Section 3 (ADR-09)
      Output: `frontend/src/App.tsx` · `frontend/src/main.tsx` — app renders and all six routes navigate correctly

- [ ] T1.5.4 — Implement shared components: `Button`, `Card`, `ScoreBadge`,
      `LoadingSpinner`, `EmptyState`, styled with Tailwind utility classes
      Ref: ARCHITECTURE Section 4.4 (`shared/components/`) · Section 20.3 of PRD (visual design principles — single mastery gradient, not stoplight colors)
      Output: `frontend/src/shared/components/{Button,Card,ScoreBadge,LoadingSpinner,EmptyState}.tsx`

---

## Feature 1.6 — CI Hygiene

- [ ] T1.6.1 — Configure `ruff` (backend) and ESLint + `tsc --noEmit` (frontend)
      with strict-but-reasonable rulesets; add `npm run test` wiring for Vitest;
      confirm both linters and the test runner execute cleanly on the scaffolded
      (near-empty) project
      Ref: ARCHITECTURE Appendix (Key Dependencies — `ruff`, `vitest`)
      Output: `backend/pyproject.toml` (ruff config section) · `frontend/.eslintrc` · `frontend/vitest.config.ts` — zero warnings, zero failing tests

---

---

# EPIC 2 — LLM Infrastructure & Prompt Contracts

> Every downstream pipeline (ingestion, quiz, writing, reports) calls through
> this layer. Building it in isolation, fully mocked, means every later epic
> can be developed without a live Ollama host running.

**What "done" means for this epic:**
- `OllamaAdapter` implements both `Generator` and `Evaluator`, calling `/api/chat`
  with a `format` parameter built from the target Pydantic schema
- Grading/evaluation tasks are provably called with `temperature=0` and a fixed
  seed; generation tasks are provably called with default sampling
- Every one of the 7 prompt-contract tasks from Architecture Section 9 has an
  output schema, a prompt template with a version constant, and a semantic
  validation function with passing unit tests for both valid and invalid fixtures
- The opt-in real-Ollama integration test exists and correctly skips itself when
  `OLLAMA_HOST` is unreachable

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 16 (Quiz Generation Pipeline) · Section 18 (Writing Evaluation Pipeline) ·
                          Section 19 (Weekly Review Pipeline)
docs/ARCHITECTURE.md   ← Section 3 (ADR-06, ADR-12, ADR-13) · Section 9 (Prompt Contracts, full) ·
                          Section 11 (Error Handling) · Section 17.2 (Testing Boundaries — OllamaAdapter row)
```

---

## Feature 2.1 — Output Schemas

- [ ] T2.1.1 — Implement `ParsedItem` and `ParsedNoteOutput` Pydantic models
      Ref: ARCHITECTURE Section 9.1 (Parser — Output schema)
      Output: `backend/app/llm/schemas.py` (start file; subsequent tasks append)

- [ ] T2.1.2 — Implement `QuizQuestionOutput` and `GradedAnswerOutput`
      Ref: ARCHITECTURE Section 9.2 (Quiz Generator) · Section 9.3 (Quiz Answer Grading)
      Output: `backend/app/llm/schemas.py` (append)

- [ ] T2.1.3 — Implement `InlineCorrection`, `MiniWritingEvalOutput`,
      `DimensionScore`, `WeeklyWritingEvalOutput`
      Ref: ARCHITECTURE Section 9.4 (Writing Evaluator — Mini) · Section 9.5 (Writing Evaluator — Weekly)
      Output: `backend/app/llm/schemas.py` (append)

- [ ] T2.1.4 — Implement `WeeklyNarrativeOutput` and `TopicOutput`
      Ref: ARCHITECTURE Section 9.6 (Weekly Report Narrative) · Section 9.7 (Topic Generation)
      Output: `backend/app/llm/schemas.py` (append)

---

## Feature 2.2 — Ollama Adapter

- [ ] T2.2.1 — Implement `OllamaAdapter.generate()`/`.evaluate()`: `httpx.AsyncClient`
      POST to `{OLLAMA_HOST}/api/chat` with `format=output_schema.model_json_schema()`,
      parsing the response via `output_schema.model_validate_json()`; connection
      and timeout error handling per the Error Handling table (2 retries,
      1s/3s backoff for connection errors; no retry on timeout, 120s timeout)
      Ref: ARCHITECTURE Section 3 (ADR-06) · Section 11.1 (Ollama host unreachable / timeout rows)
      Output: `backend/app/llm/ollama_adapter.py`

- [ ] T2.2.2 — Implement `_call_with_retry()`: the single shared retry
      implementation for schema/semantic-validation failures (one retry with an
      appended correction instruction, per Section 9's per-task rules), used by
      every task type
      Ref: ARCHITECTURE Section 11.2 (General Retry Discipline)
      Output: `backend/app/llm/ollama_adapter.py` (extend)

- [ ] T2.2.3 — Implement `inference_settings.py`: a lookup table mapping
      `grade_quiz_answer`, `mini_writing_eval`, `weekly_writing_eval` to
      `temperature=0` + fixed seed (where supported), and all other task names
      to default sampling; wire `OllamaAdapter` to consult it per call
      Ref: ARCHITECTURE Section 3 (ADR-12) · Section 9 (v1.1 inference-settings note)
      Output: `backend/app/llm/inference_settings.py`

- [ ] T2.2.4 — Implement a provenance-stamping helper used by calling services
      (not the adapter itself) to populate `evaluator_provider`, `evaluator_model`
      (from active `Config`), `prompt_version`, `rubric_version` (from the
      constant co-located with the template actually used) on graded/evaluated rows
      Ref: ARCHITECTURE Section 3 (ADR-13) · Section 7.1 (v1.1 Evaluation metadata)
      Output: `backend/app/llm/provenance.py`

---

## Feature 2.3 — Prompt Templates

- [ ] T2.3.1 — Write the `parse_note` prompt template and `PARSE_NOTE_PROMPT_VERSION`
      constant, co-located in the same file
      Ref: ARCHITECTURE Section 9.1 (Parser) · Section 3 (ADR-13 — co-location discipline)
      Output: `backend/app/llm/prompts/parser.py`

- [ ] T2.3.2 — Write the 7 `quiz_{mode}` prompt templates (recall, fill_blank,
      multiple_choice, error_correction, rewrite_naturally, conversation,
      mini_essay) with per-mode version constants
      Ref: ARCHITECTURE Section 9.2 (Quiz Generator) · PRD Section 16.3 (Prompt Construction per type)
      Output: `backend/app/llm/prompts/quiz.py`

- [ ] T2.3.3 — Write the `mini_writing_eval` and `weekly_writing_eval` prompt
      templates with version constants (`prompt_version`) and a separately
      versioned rubric text block (`rubric_version`) per ADR-13's independent versioning
      Ref: ARCHITECTURE Section 9.4 · Section 9.5 · Section 3 (ADR-13)
      Output: `backend/app/llm/prompts/writing_eval.py`

- [ ] T2.3.4 — Write the `weekly_narrative` and `weekly_topic` prompt templates
      with version constants
      Ref: ARCHITECTURE Section 9.6 · Section 9.7
      Output: `backend/app/llm/prompts/weekly_report.py`

---

## Feature 2.4 — Validation Rules & Tests

- [ ] T2.4.1 — Implement the semantic validation function for each task per
      Architecture Section 9's per-task rules: `source_excerpt` substring check
      and CORRECTION-field downgrade (parser); MC distractor count/uniqueness,
      fill_blank marker presence, error_correction inequality (quiz); score
      clamping to `[0,1]` (grading); `naturalness_notes` truncation to 2 (mini
      writing); score clamping to `[0,100]` + non-empty overall feedback (weekly
      writing); word-count warning (narrative); fuzzy-match-against-history
      retry trigger (topic)
      Ref: ARCHITECTURE Section 9 (Validation rules, all subsections)
      Output: `backend/app/llm/validation.py`

- [ ] T2.4.2 — Write unit tests for every validation function in T2.4.1 against
      hand-crafted valid and invalid fixture payloads (one valid + at least one
      invalid case per rule)
      Ref: ARCHITECTURE Section 17.2 (Testing Boundaries — schema validation row)
      Output: `backend/tests/unit/test_llm_validation.py` — all cases passing

- [ ] T2.4.3 — Write the opt-in `OllamaAdapter` integration test: skips via
      `pytest.mark.skipif` when `OLLAMA_HOST` is unreachable, otherwise asserts
      a real schema-constrained call round-trips correctly for at least the
      `parse_note` task
      Ref: ARCHITECTURE Section 17.2 (`OllamaAdapter` itself row)
      Output: `backend/tests/integration/test_ollama_adapter_live.py`

---

---

# EPIC 3 — Vault Watcher & Ingestion Pipeline

> Implements PRD Flow 1 end-to-end on the backend side. This is the epic with
> the highest-ranked implementation risk (Architecture Section 16, watcher-thread
> concurrency), so it gets dedicated, isolated testing before Approval or Quiz
> code depends on its output.

**What "done" means for this epic:**
- Saving a real file into a watched temp directory results in exactly one
  `IngestionService.process_note()` call, verified with a real `watchdog` Observer
- An atomic save (write-temp-then-rename), a rapid-fire duplicate-event burst,
  and a same-content re-save each produce the correct behavior per ADR-11
  (one call, one call, zero calls, respectively)
- A successfully parsed note produces `ApprovalQueue` rows with correct
  `possible_duplicate_of` values when a near-duplicate exists
- A note that fails parsing twice lands in `PARSE_FAILED` with an `AuditLog` entry

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 10 (Flow 1) · Section 7.1 (FR-1.1–FR-1.4)
docs/ARCHITECTURE.md   ← Section 3 (ADR-11) · Section 6.1 (Sequence: Save Note → Parser → Approval) ·
                          Section 10.1 (Note state machine) · Section 11 (Error Handling)
```

---

## Feature 3.1 — Vault Watcher

- [ ] T3.1.1 — Implement `VaultWatcher._raw_event_handler()`: subscribes to
      `on_created`, `on_modified`, `on_moved` via `watchdog`, and implements the
      debounce logic (default 2s, configurable) that coalesces multiple raw
      events for the same `vault_path` into a single downstream call
      Ref: ARCHITECTURE Section 3 (ADR-11) · Section 6.1 (sequence diagram, debounce step)
      Output: `backend/app/ingestion/watcher.py`

- [ ] T3.1.2 — Implement `VaultWatcher.handle_event(path)`: computes
      `content_hash`, compares against the existing `Note.content_hash` (no-op
      on match), upserts the `Note` row, and calls `IngestionService.process_note()`
      Ref: ARCHITECTURE Section 3 (ADR-11, hash-compare) · Section 6.1 (sequence diagram)
      Output: `backend/app/ingestion/watcher.py` (extend)

- [ ] T3.1.3 — Wire `VaultWatcher` into the FastAPI `lifespan` context manager
      from Feature 1.1 as a background thread; handle the vault-path-misconfigured
      case by logging clearly and leaving the rest of the API functional
      Ref: ARCHITECTURE Section 3 (ADR-03) · Section 11.1 (vault path misconfigured row)
      Output: `backend/app/main.py` (extend `lifespan`)

---

## Feature 3.2 — Ingestion Service

- [ ] T3.2.1 — Implement `IngestionService.process_note()`: read file content,
      set `Note.status = PARSING`, call `Generator.generate(task="parse_note", ...)`,
      handle schema/semantic validation failure with the retry-then-`PARSE_FAILED`
      path (Note update + `AuditLog` entry on second failure)
      Ref: ARCHITECTURE Section 6.1 (sequence diagram) · Section 9.1 (Failure handling)
      Output: `backend/app/ingestion/service.py`

- [ ] T3.2.2 — Implement `duplicate_detection.find_similar(text)`: FTS5 `MATCH`
      query against `learning_item_fts` with BM25 ranking, returning top candidates
      Ref: ARCHITECTURE Section 3 (ADR-07) · Section 6.1 (sequence diagram, duplicate lookup step)
      Output: `backend/app/ingestion/duplicate_detection.py`

- [ ] T3.2.3 — Implement `ApprovalQueue` row creation from a validated
      `ParsedNoteOutput`: one row per candidate item, `possible_duplicate_of`
      populated from T3.2.2, `Note.status` transitioned to `PENDING_APPROVAL`
      Ref: ARCHITECTURE Section 6.1 (sequence diagram, final steps) · Section 10.1 (Note state machine)
      Output: `backend/app/ingestion/service.py` (extend)

- [ ] T3.2.4 — Implement `changed_since_processed` detection: when a hash-changed
      event arrives for a `Note` already in `PROCESSED` status, set the flag and
      do **not** re-parse (write-once ingestion model)
      Ref: PRD Section 7.1 (FR-1.3 Write-Once Ingestion) · ARCHITECTURE Section 10.1 (Note state machine)
      Output: `backend/app/ingestion/service.py` (extend)

---

## Feature 3.3 — Tests

- [ ] T3.3.1 — Write the real-filesystem integration test: a real `watchdog`
      Observer against a temp directory, simulating (a) an atomic write-then-rename
      save, (b) a rapid-fire duplicate-event burst from one save, (c) a
      same-content re-save; assert exactly one `process_note()` call for (a) and
      (b) each, and zero for (c)
      Ref: ARCHITECTURE Section 17.2 (`app/ingestion/watcher.py` row, v1.1 detail)
      Output: `backend/tests/integration/test_vault_watcher.py`

- [ ] T3.3.2 — Write integration tests for `IngestionService.process_note()`
      happy path and `PARSE_FAILED` path, using `FakeGenerator` fixtures
      (valid response, and a response that fails validation twice)
      Ref: ARCHITECTURE Section 17.2 (`app/ingestion/service.py` row)
      Output: `backend/tests/integration/test_ingestion_service.py`

- [ ] T3.3.3 — Write unit tests for `duplicate_detection.find_similar()` against
      a small seeded set of `LearningItem` rows (exact match, near match, no match)
      Ref: ARCHITECTURE Section 17.2 (unit test row, adjacent to duplicate detection)
      Output: `backend/tests/unit/test_duplicate_detection.py`

---

---

# EPIC 4 — Approval Workflow

> Implements the structural trust gate (ADR-05) that every other pipeline
> depends on. `LearningItem`/`LearningCorrection` cannot exist in the system
> until this epic is complete.

**What "done" means for this epic:**
- `ApprovalService.approve()`/`approve_edited()`/`reject()` are the only code
  paths in the entire codebase that insert `LearningItem`/`LearningCorrection` rows
  (verified by a grep-able module-boundary check, not just a test)
  — this codifies PRD's "nothing enters the permanent learning record without
  human approval" as a structural rule, not just an implemented feature
- Double-approving the same item returns HTTP 409 with no duplicate row created
- The Approvals page in the frontend lists pending items grouped by source,
  supports single-click approve, edit-then-approve, reject, and batch actions

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 9 (Product Philosophy #2) · Section 10 (Flow 5) · Section 7.1 (FR-1.4)
docs/ARCHITECTURE.md   ← Section 3 (ADR-05) · Section 6.2 (Sequence: Approval Action) ·
                          Section 10.2 (ApprovalQueue state machine) · Section 11.1 (double-approval row)
```

---

## Feature 4.1 — Approval Service

- [ ] T4.1.1 — Implement `ApprovalService.approve()` and `.approve_edited()`:
      wrapped in a single transaction that fetches the `ApprovalQueue` row,
      inserts a `LearningItem` or `LearningCorrection` depending on `item_type`
      (with `mastery_score=0.3` initialization per Section 17.3 of the PRD for
      `LearningItem`), updates `ApprovalQueue.status`, and commits
      Ref: ARCHITECTURE Section 3 (ADR-05) · Section 6.2 (sequence diagram) · PRD Section 17.3 (New Item Initialization)
      Output: `backend/app/approvals/service.py`

- [ ] T4.1.2 — Implement `ApprovalService.reject()`: terminal status transition,
      no `LearningItem`/`LearningCorrection` row created, row retained for audit
      Ref: ARCHITECTURE Section 10.2 (ApprovalQueue state machine)
      Output: `backend/app/approvals/service.py` (extend)

- [ ] T4.1.3 — Implement the double-approval guard: check
      `ApprovalQueue.status == PENDING` inside the same transaction before
      writing; return a distinguishable error the router can map to HTTP 409
      Ref: ARCHITECTURE Section 11.1 (Concurrent approval row)
      Output: `backend/app/approvals/service.py` (extend)

---

## Feature 4.2 — Approval API

- [ ] T4.2.1 — Implement the `/approvals` router: `GET /approvals` (list pending,
      grouped by `source_type`+`source_id`), `POST /approvals/{id}/approve`,
      `POST /approvals/{id}/approve-edited`, `POST /approvals/{id}/reject`, and
      batch variants accepting a list of IDs
      Ref: ARCHITECTURE Section 6.2 (sequence diagram) · PRD Section 10 (Flow 5)
      Output: `backend/app/approvals/router.py`

- [ ] T4.2.2 — Implement `GET /approvals/pending-count`: the lightweight polling
      target referenced by ADR-08 for the frontend's normal refresh cadence
      Ref: ARCHITECTURE Section 3 (ADR-08 — note-parsing polling note)
      Output: `backend/app/approvals/router.py` (extend)

---

## Feature 4.3 — Frontend Approvals

- [ ] T4.3.1 — Implement `usePendingApprovals()`, `useApproveItem()`,
      `useRejectItem()` hooks using TanStack Query; approving/rejecting
      invalidates `["approvals","pending"]` and `["items"]` query keys
      Ref: ARCHITECTURE Section 6.2 (sequence diagram, frontend invalidation step) · Section 3 (ADR-09)
      Output: `frontend/src/features/approvals/hooks/`

- [ ] T4.3.2 — Implement `ApprovalCard`: displays extracted text, item type,
      explanation, source excerpt, and a duplicate warning banner when
      `possible_duplicate_of` is present; single-click Approve, expandable Edit form, Reject
      Ref: PRD Section 20.2 (Interaction Principles — single-click approve)
      Output: `frontend/src/features/approvals/components/ApprovalCard.tsx`

- [ ] T4.3.3 — Implement `ApprovalsPage`: groups pending items by source batch,
      oldest-first, with batch Approve/Reject controls per group
      Ref: PRD Section 10 (Flow 5, full sequence)
      Output: `frontend/src/features/approvals/ApprovalsPage.tsx`

---

## Feature 4.4 — Tests

- [ ] T4.4.1 — Write integration tests: approve/edit-approve/reject transitions
      each produce the correct row state; verify the only-writer invariant by
      asserting no other tested module path can insert a `LearningItem`; verify
      double-approval returns 409 with no duplicate row
      Ref: ARCHITECTURE Section 17.2 (`app/approvals/service.py` row)
      Output: `backend/tests/integration/test_approval_service.py`

- [ ] T4.4.2 — Write frontend hook tests for `usePendingApprovals`/`useApproveItem`
      with the fetch layer mocked
      Ref: ARCHITECTURE Section 17.2 (Frontend feature hooks row)
      Output: `frontend/src/features/approvals/hooks/__tests__/`

---

---

# EPIC 5 — Scheduler & Retrieval

> Pure-logic and read-path infrastructure needed by every remaining
> learner-facing pipeline (Quiz, Writing, Reports, Dashboard).

**What "done" means for this epic:**
- `decayed_score()` and `update_mastery()` are pure, side-effect-free (beyond
  mutating the passed-in object) and covered by unit tests for normal, boundary
  (0.0/1.0 clamping), and multi-day-decay cases
- `select_eligible_items()` correctly partitions due/not-due, weights by
  weakness, respects the ~60% category-balance constraint, and backfills from
  the not-due pool when the due pool is too small
- Week-scoped retrieval queries return the correct adaptive volume, including
  the zero-items-studied edge case

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 17 (Progress Tracking & Mastery Decay Logic) · Section 16.1 (Eligibility & Selection) ·
                          Section 19.2 (Adaptive Content Volume)
docs/ARCHITECTURE.md   ← Section 3 (ADR-04) · Section 8.4 (Mastery Update Formula) ·
                          Section 4.2 (RetrievalService responsibilities) · Section 12.2 (Runtime-Adjustable Config)
```

---

## Feature 5.1 — Mastery/Decay Engine

- [ ] T5.1.1 — Implement `decayed_score()` and `update_mastery()` exactly per
      the formula in Architecture Section 8.4, as pure functions taking a
      `LearningItem` and mutating it in place (caller commits)
      Ref: ARCHITECTURE Section 8.4 (Mastery Update Formula) · PRD Section 16.6 · Section 17.2
      Output: `backend/app/scheduler/mastery.py`

- [ ] T5.1.2 — Implement `SchedulerSettings`: loads `decay_rate`,
      `correct_threshold`, and the four mastery-adjustment constants from the
      `Config` table at call time (not hardcoded), falling back to the documented
      defaults if unset
      Ref: ARCHITECTURE Section 12.2 (Runtime-Adjustable Config) · Section 8.4 (constants-must-be-tunable note)
      Output: `backend/app/scheduler/mastery.py` (extend)

- [ ] T5.1.3 — Write unit tests: correct-answer update path, incorrect-answer
      update path, mastery clamping at 0.0 and 1.0, `decayed_score()` at 0 days /
      90 days / very-long-elapsed inputs
      Ref: ARCHITECTURE Section 17.2 (`app/scheduler/mastery.py` row)
      Output: `backend/tests/unit/test_mastery.py`

---

## Feature 5.2 — Retrieval Service

- [ ] T5.2.1 — Implement `RetrievalService.select_eligible_items()`: due/not-due
      partition, weakness-weighted sampling (`weakness_score = 1 - mastery_score`),
      ~60% category-balance constraint, backfill from not-due pool
      Ref: PRD Section 16.1 (Eligibility & Selection, full algorithm)
      Output: `backend/app/retrieval/service.py`

- [ ] T5.2.2 — Implement week-scoped query methods:
      `items_created_between(week_start, week_end)`,
      `quiz_summary_for_week()`, `mini_writing_summary_for_week()`,
      `weekly_writing_eval_for_week()`
      Ref: ARCHITECTURE Section 6.5 (Weekly Report Assembly sequence) · PRD Section 19.1–19.2
      Output: `backend/app/retrieval/service.py` (extend)

- [ ] T5.2.3 — Implement `RetrievalService.item_context()` (single-item context
      for quiz prompt construction) and `writing_context()` (FTS5-based
      `known_relevant_items` lookup for writing evaluation, per the accepted
      lexical-only limitation)
      Ref: ARCHITECTURE Section 15.1 of PRD (Retrieval Strategy, caveat) · Section 9.5 of ARCHITECTURE (writing eval input context)
      Output: `backend/app/retrieval/service.py` (extend)

- [ ] T5.2.4 — Implement `RetrievalService.performance_error_patterns()`: an
      aggregation query over `PerformanceError` rows for weekly-report
      weakness-pattern surfacing
      Ref: ARCHITECTURE Section 7.2 (`idx_perf_error_item_created` index rationale) · PRD Section 19.3
      Output: `backend/app/retrieval/service.py` (extend)

---

## Feature 5.3 — Tests

- [ ] T5.3.1 — Write integration tests for `select_eligible_items()`: seed a
      mixed due/not-due, mixed-category `LearningItem` set and assert the
      category-balance and backfill rules hold
      Ref: ARCHITECTURE Section 17.2 (integration test pattern, adapted for scheduler/retrieval)
      Output: `backend/tests/integration/test_retrieval_scheduler.py`

- [ ] T5.3.2 — Write integration tests for week-scoped queries, including the
      zero-items-studied case returning an empty (not error) result
      Ref: PRD Section 19.2 (Adaptive Content Volume)
      Output: `backend/tests/integration/test_retrieval_scheduler.py` (extend)

---

---

# EPIC 6 — Quiz Engine

> Implements PRD Flow 2 end-to-end. First learner-facing feature with real value.

**What "done" means for this epic:**
- A quiz session can be started for any of the 7 modes plus RANDOM, generating
  schema-valid questions via `Generator`, with category balance respected in RANDOM mode
- Deterministic grading correctly handles fill-blank/MC/error-correction/recall;
  ambiguous free-text answers fall through to LLM grading with deterministic
  inference settings (ADR-12)
- Every incorrect/low-score answer produces a `PerformanceError` row directly
  (no approval step, per the ADR-05 exception) and updates the associated
  `LearningItem`'s mastery via `SchedulerModule.update_mastery()`
- The frontend Quiz page supports starting a session, answering each of the 7
  question types with an appropriate UI, and viewing a session summary

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 16 (Quiz Generation Pipeline, full) · Section 10 (Flow 2)
docs/ARCHITECTURE.md   ← Section 3 (ADR-05 PerformanceError exception, ADR-08, ADR-12) ·
                          Section 6.3 (Sequence: Ad-hoc Quiz Generation & Grading) · Section 10.3 (QuizSession state machine)
```

---

## Feature 6.1 — Quiz Generation

- [ ] T6.1.1 — Implement `QuizService.start_session()`: call
      `SchedulerModule.select_eligible_items()`, create `QuizSession`
      (`status=IN_PROGRESS`), and for each selected item construct the
      per-mode prompt context via `RetrievalService.item_context()` and call
      `Generator.generate(task=f"quiz_{mode}", ...)`, persisting `QuizQuestion` rows
      Ref: ARCHITECTURE Section 6.3 (sequence diagram, session-start portion)
      Output: `backend/app/quizzes/service.py`

- [ ] T6.1.2 — Implement RANDOM mode: independently assign one of the 7 concrete
      modes per question while still respecting the category-balance constraint
      Ref: PRD Section 16.2 (Question Type Assignment)
      Output: `backend/app/quizzes/service.py` (extend)

- [ ] T6.1.3 — Implement the per-item retry/backfill path on quiz-question
      validation failure: one retry with the named violation, then skip and
      backfill with the next eligible item rather than failing the whole request
      Ref: ARCHITECTURE Section 9.2 (Failure handling)
      Output: `backend/app/quizzes/service.py` (extend)

---

## Feature 6.2 — Grading

- [ ] T6.2.1 — Implement `grading.grade_deterministic()`: normalized
      case/whitespace-insensitive matching for fill-blank/MC, with fallback
      trigger for error-correction/recall when the match is ambiguous
      Ref: PRD Section 16.4 (Deterministic Grading)
      Output: `backend/app/quizzes/grading.py`

- [ ] T6.2.2 — Implement the LLM-fallback grading path: call
      `Evaluator.evaluate(task="grade_quiz_answer", ...)` with deterministic
      inference settings (via Feature 2.2's `inference_settings`), defensively
      re-clamp the returned score to `[0,1]`
      Ref: ARCHITECTURE Section 9.3 (Quiz Answer Grading) · Section 3 (ADR-12)
      Output: `backend/app/quizzes/grading.py` (extend)

- [ ] T6.2.3 — Implement `QuizService.grade_session()`: orchestrates grading
      per answer, stamps `graded_by`/provenance fields (via Feature 2.2's
      provenance helper, only when `graded_by=LLM`), inserts a `PerformanceError`
      row for each incorrect/low-score answer (direct write, no approval step —
      this is the ADR-05 exception), calls `SchedulerModule.update_mastery()`,
      and marks `QuizSession.completed_at`
      Ref: ARCHITECTURE Section 6.3 (sequence diagram, grading portion) · Section 3 (ADR-05 exception)
      Output: `backend/app/quizzes/service.py` (extend)

---

## Feature 6.3 — Quiz API

- [ ] T6.3.1 — Implement the `/quizzes` router: `POST /quizzes` (start session,
      synchronous per ADR-08), `POST /quizzes/{session_id}/answers` (grade),
      `GET /quizzes/{session_id}` (summary)
      Ref: ARCHITECTURE Section 3 (ADR-08) · Section 6.3 (sequence diagram)
      Output: `backend/app/quizzes/router.py`

---

## Feature 6.4 — Frontend Quiz UI

- [ ] T6.4.1 — Implement `useStartQuiz()` and `useSubmitAnswer()` hooks
      Ref: ARCHITECTURE Section 4.4 (`features/quizzes/hooks/`)
      Output: `frontend/src/features/quizzes/hooks/`

- [ ] T6.4.2 — Implement `QuizModeSelector` and a `QuestionCard` component with
      distinct rendering per quiz type (fill-blank input, MC radio group,
      error-correction textarea, rewrite/conversation/mini-essay free-text,
      recall input)
      Ref: PRD Section 9 (Quiz types, D. Quiz Generation) · Section 16 (7 modes + Random)
      Output: `frontend/src/features/quizzes/components/{QuizModeSelector,QuestionCard}.tsx`

- [ ] T6.4.3 — Implement `SessionSummary` component and `QuizPage` orchestration
      (mode selection → answering → summary), local answer state held until submit
      Ref: PRD Section 10 (Flow 2, full sequence)
      Output: `frontend/src/features/quizzes/components/SessionSummary.tsx` · `frontend/src/features/quizzes/QuizPage.tsx`

---

## Feature 6.5 — Tests

- [ ] T6.5.1 — Write unit tests for `grade_deterministic()` covering every quiz
      type's normalization/edge cases (case sensitivity, whitespace, near-miss
      free-text answers triggering fallback)
      Ref: ARCHITECTURE Section 17.2 (`app/quizzes/grading.py` row)
      Output: `backend/tests/unit/test_quiz_grading.py`

- [ ] T6.5.2 — Write integration tests for the full start→answer→grade flow
      using `FakeGenerator`/`FakeEvaluator`, asserting: `PerformanceError` rows
      are created for incorrect answers with no approval step involved, and
      `LearningItem.mastery_score`/`next_review_due` update correctly
      Ref: ARCHITECTURE Section 17.2 (`app/quizzes/service.py` row, v1.1 detail)
      Output: `backend/tests/integration/test_quiz_service.py`

---

---

# EPIC 7 — Writing Evaluation

> Implements PRD Flow 3 (mini) and the writing half of Flow 4 (weekly) end-to-end.

**What "done" means for this epic:**
- A mini writing submission receives correctness/naturalness feedback with no
  numeric scores stored, and each `InlineCorrection` produces a `PerformanceError`
  row directly (no approval step)
- A weekly writing submission receives all 5 dimension scores plus provenance
  metadata, and a repetition-avoiding topic is generated correctly
- `suggested_items` from either flow route to `ApprovalQueue` with
  `source_type=WRITING_FEEDBACK` — these, unlike corrections, DO require approval
- `EVALUATION_FAILED` preserves the submission text and supports a manual retry

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 18 (Writing Evaluation Pipeline, full) · Section 10 (Flow 3, Flow 4 writing portion)
docs/ARCHITECTURE.md   ← Section 3 (ADR-05 exception, ADR-12, ADR-13) · Section 6.4 (Sequence: Weekly Writing Assessment) ·
                          Section 9.4–9.5 (Prompt Contracts) · Section 10.4 (WritingEvaluation state machine)
```

---

## Feature 7.1 — Mini Writing Flow

- [ ] T7.1.1 — Implement `WritingService` prompt handling for mini tasks and
      `WritingSubmission` storage (`submission_type=MINI`)
      Ref: PRD Section 10 (Flow 3, steps 1-3)
      Output: `backend/app/writing/service.py`

- [ ] T7.1.2 — Implement the `mini_writing_eval` `Evaluator` call and its result
      handling: each `InlineCorrection` in the response becomes a `PerformanceError`
      row (`source_type=WRITING_MINI`), written directly with no approval step
      Ref: ARCHITECTURE Section 9.4 (v1.1 note — InlineCorrection → PerformanceError) · Section 3 (ADR-05 exception)
      Output: `backend/app/writing/service.py` (extend)

- [ ] T7.1.3 — Implement `suggested_items` routing to `ApprovalQueue`
      (`source_type=WRITING_FEEDBACK`) — this path IS approval-gated, distinct
      from the `PerformanceError` path in T7.1.2
      Ref: ARCHITECTURE Section 3 (ADR-05, the new-knowledge category) · PRD Section 11 (E. Writing Evaluation)
      Output: `backend/app/writing/service.py` (extend)

---

## Feature 7.2 — Weekly Writing Flow

- [ ] T7.2.1 — Implement `WritingService.generate_weekly_prompt()`: fetch last
      12 `WEEKLY` prompts via `RetrievalService`, call `Generator.generate(task="weekly_topic", ...)`,
      apply the fuzzy-match retry rule from Section 9.7, persist `WritingPrompt`
      Ref: ARCHITECTURE Section 6.4 (sequence diagram, prompt-generation portion) · Section 9.7
      Output: `backend/app/writing/service.py` (extend)

- [ ] T7.2.2 — Implement the `weekly_writing_eval` `Evaluator` call: pass
      `weak_categories` and `known_relevant_items` context, persist all 5
      `DimensionScore`s plus provenance metadata (via Feature 2.2's helper) on `WritingEvaluation`
      Ref: ARCHITECTURE Section 9.5 · Section 6.4 (sequence diagram) · Section 3 (ADR-13)
      Output: `backend/app/writing/service.py` (extend)

- [ ] T7.2.3 — Implement `EVALUATION_FAILED` handling: preserve the
      `WritingSubmission` on `Evaluator` failure, expose a manual retry path that
      re-runs evaluation against the already-stored text without requiring resubmission
      Ref: ARCHITECTURE Section 10.4 (WritingEvaluation state machine) · Section 9.5 (Failure handling) · PRD Section 18.5
      Output: `backend/app/writing/service.py` (extend)

---

## Feature 7.3 — Writing API

- [ ] T7.3.1 — Implement the `/writing` router: mini-task submit/evaluate
      endpoint, weekly prompt-generation endpoint, weekly submit/evaluate
      endpoint, and a retry-evaluation endpoint for the `EVALUATION_FAILED` case
      Ref: ARCHITECTURE Section 6.4 (sequence diagram) · Section 3 (ADR-08, synchronous)
      Output: `backend/app/writing/router.py`

---

## Feature 7.4 — Frontend Writing UI

- [ ] T7.4.1 — Implement `useMiniTask()` and `useWeeklyAssessment()` hooks
      Ref: ARCHITECTURE Section 4.4 (`features/writing/hooks/`)
      Output: `frontend/src/features/writing/hooks/`

- [ ] T7.4.2 — Implement `WritingEditor` component (plain textarea-based, per
      ARCHITECTURE Section 3 ADR-09's noted minimal-editor option)
      Ref: ARCHITECTURE Section 3 (ADR-09) · PRD Section 20.3 (inline annotation principle)
      Output: `frontend/src/features/writing/components/WritingEditor.tsx`

- [ ] T7.4.3 — Implement `EvaluationFeedback` component: inline wrong/correct
      span annotations for mini-task corrections, and per-dimension score
      display (5 scores + feedback) for weekly assessments
      Ref: PRD Section 20.3 (Visual Design Principles — inline annotations)
      Output: `frontend/src/features/writing/components/EvaluationFeedback.tsx`

---

## Feature 7.5 — Tests

- [ ] T7.5.1 — Write integration tests for the mini flow (submission →
      evaluation → `PerformanceError` rows + `ApprovalQueue` suggested-item rows
      both created correctly) and the weekly flow (5 scores + provenance metadata
      persisted correctly) using `FakeEvaluator`
      Ref: ARCHITECTURE Section 17.2 (`app/writing/service.py` row)
      Output: `backend/tests/integration/test_writing_service.py`

- [ ] T7.5.2 — Write an integration test for the `EVALUATION_FAILED` path:
      simulate an `Evaluator` failure, assert the submission is preserved, then
      assert a manual retry succeeds using a corrected `FakeEvaluator` response
      Ref: ARCHITECTURE Section 10.4 (state machine) · PRD Section 18.5
      Output: `backend/tests/integration/test_writing_service.py` (extend)

---

---

# EPIC 8 — Weekly Reports

> Implements the writing-quiz-report assembly half of PRD Flow 4, tying
> together E5 (retrieval), E6 (quiz), and E7 (writing).

**What "done" means for this epic:**
- "Start Weekly Review" correctly uses only the current week's actual data,
  including the zero-lessons-studied edge case producing a report that states
  this plainly rather than fabricating quiz content
- The assembled `WeeklyReport` contains quiz summary, mini-writing summary,
  the weekly writing evaluation, a point-in-time `mastery_snapshot_json`, and
  an LLM-generated narrative
- The Reports page can trigger a full weekly review (quiz → writing → finalize)
  and browse the report archive

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 19 (Weekly Review Pipeline) · Section 10 (Flow 4, full)
docs/ARCHITECTURE.md   ← Section 6.5 (Sequence: Weekly Report Assembly) · Section 9.6 (Prompt Contract: Narrative)
```

---

## Feature 8.1 — Report Assembly

- [ ] T8.1.1 — Implement `ReportService.assemble()`: compute the Monday–Sunday
      week boundary (Section 19.1), gather week-scoped items/quiz/writing data
      via `RetrievalService` (Epic 5), and handle the zero-items-studied case by
      skipping the quiz step and noting it explicitly rather than fabricating content
      Ref: PRD Section 19.1 (Week Boundary Definition) · Section 19.2 (Adaptive Content Volume)
      Output: `backend/app/reports/service.py`

- [ ] T8.1.2 — Implement the `weekly_narrative` `Generator` call and
      `WeeklyReport` persistence, including the point-in-time
      `mastery_snapshot_json` copy (via `DashboardService`'s category-mastery
      aggregation, built as a small standalone function reused later by Epic 9)
      Ref: ARCHITECTURE Section 6.5 (sequence diagram) · PRD Section 12 (denormalization: `mastery_snapshot_json`)
      Output: `backend/app/reports/service.py` (extend)

---

## Feature 8.2 — Weekly Review API

- [ ] T8.2.1 — Implement the `/reports` router: weekly-quiz trigger (delegates
      to `QuizService` with `quiz_scope=WEEKLY_REVIEW`), weekly writing-prompt/submit
      endpoints (delegate to Epic 7's writing router logic), `POST /reports/weekly/finalize`,
      and archive list/detail endpoints
      Ref: ARCHITECTURE Section 6.5 (sequence diagram) · Section 6.3 (weekly-scope quiz note)
      Output: `backend/app/reports/router.py`

---

## Feature 8.3 — Frontend Reports UI

- [ ] T8.3.1 — Implement `useStartWeeklyReview()` and `useWeeklyReports()` hooks
      Ref: ARCHITECTURE Section 4.4 (`features/reports/hooks/`)
      Output: `frontend/src/features/reports/hooks/`

- [ ] T8.3.2 — Implement `ReportSummaryCard` and `ReportsPage`: orchestrates
      the full weekly-review flow (quiz step → writing step → finalize) as a
      guided sequence, plus a browsable archive of past reports
      Ref: PRD Section 10 (Flow 4, full sequence)
      Output: `frontend/src/features/reports/components/ReportSummaryCard.tsx` · `frontend/src/features/reports/ReportsPage.tsx`

---

## Feature 8.4 — Tests

- [ ] T8.4.1 — Write integration tests for the full weekly-review flow,
      including a variant where only 3 of a possible 6 lessons were studied and
      a variant with zero lessons studied — assert the report correctly reflects
      actual volume in both cases
      Ref: PRD Section 19.2 (Adaptive Content Volume) · ARCHITECTURE Section 6.5
      Output: `backend/tests/integration/test_report_service.py`

- [ ] T8.4.2 — Write an integration test asserting report archive ordering
      (`idx_report_week_start`) and that `mastery_snapshot_json` correctly
      freezes at report-creation time even as `LearningItem.mastery_score`
      continues to change afterward
      Ref: ARCHITECTURE Section 7.5 (Denormalization)
      Output: `backend/tests/integration/test_report_service.py` (extend)

---

---

# EPIC 9 — Dashboard

> Read-only aggregation over everything built in Epics 1–8. No epic after
> this one needs Dashboard code, so it can be the last learner-facing feature
> before hardening.

**What "done" means for this epic:**
- Overview, mastery-breakdown, and trend queries each resolve independently and
  correctly against seeded fixture data (matching PRD's success metric of
  directionally sensible trends)
- Category mastery aggregation is weighted by `review_count`, and decay
  (Epic 5) is applied at read time, never stored
- The Item Browser supports FTS5-backed text search plus type/tag/mastery-range filters
- The Dashboard page renders progressively — each of its three parallel queries
  populates its own section independently, per Section 6.6

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 20 (Dashboard Design) · Section 17.4 (Category & Overall Proficiency Aggregation)
docs/ARCHITECTURE.md   ← Section 6.6 (Sequence: Dashboard Refresh) · Section 14 (Performance)
```

---

## Feature 9.1 — Dashboard Aggregation Service

- [ ] T9.1.1 — Implement `DashboardService.overview()`: the proficiency blend
      formula from PRD Section 17.4 (configurable item-mastery/writing-performance
      weighting, default 40/60), pending-approvals count, and a `health` field
      reflecting `VaultWatcher` startup status (Epic 3, Feature 3.1)
      Ref: PRD Section 17.4 (Overall Proficiency Aggregation) · ARCHITECTURE Section 11.1 (vault path misconfigured row)
      Output: `backend/app/dashboard/service.py`

- [ ] T9.1.2 — Implement `DashboardService.mastery_by_category()`: decayed
      per-category `mastery_score` aggregation (via Epic 5's `decayed_score()`),
      weighted by `review_count` per PRD's stated rationale
      Ref: PRD Section 17.4 (Category mastery formula)
      Output: `backend/app/dashboard/service.py` (extend)

- [ ] T9.1.3 — Implement `DashboardService.trend_series()`: quiz-accuracy history,
      writing 5-dimension score history, and items-learned-per-week series, each
      queryable over a configurable date range
      Ref: PRD Section 20.1 (Screen Hierarchy — Progress Trends)
      Output: `backend/app/dashboard/service.py` (extend)

---

## Feature 9.2 — Dashboard API

- [ ] T9.2.1 — Implement the `/dashboard` router: `GET /dashboard/overview`,
      `GET /dashboard/mastery-breakdown`, `GET /dashboard/trends?range=...`
      Ref: ARCHITECTURE Section 6.6 (sequence diagram — 3 parallel queries)
      Output: `backend/app/dashboard/router.py`

- [ ] T9.2.2 — Implement the Item Browser endpoint: FTS5-backed text search
      combined with `item_type`/tag/mastery-range filters
      Ref: PRD Section 20.1 (Item Browser) · ARCHITECTURE Section 3 (ADR-07)
      Output: `backend/app/dashboard/router.py` (extend)

---

## Feature 9.3 — Frontend Dashboard UI

- [ ] T9.3.1 — Implement `useOverview()`, `useMasteryBreakdown()`, `useTrends()`
      hooks — each independently fetched, not combined into one "load everything" call
      Ref: ARCHITECTURE Section 6.6 (sequence diagram, "no single blocking call" note)
      Output: `frontend/src/features/dashboard/hooks/`

- [ ] T9.3.2 — Implement `ProficiencyCard` and `MasteryBreakdownChart`
      (Recharts) using the single mastery/score color gradient, not stoplight colors
      Ref: PRD Section 20.3 (Visual Design Principles) · ARCHITECTURE Appendix (recharts dependency)
      Output: `frontend/src/features/dashboard/components/{ProficiencyCard,MasteryBreakdownChart}.tsx`

- [ ] T9.3.3 — Implement `TrendChart` (multi-series Recharts component covering
      quiz accuracy and all 5 writing dimensions over time), visually
      distinguishing the raw historical line from the decayed "current estimate" indicator
      Ref: PRD Section 20.2 (Interaction Principles — decay visibility)
      Output: `frontend/src/features/dashboard/components/TrendChart.tsx`

- [ ] T9.3.4 — Implement the Item Browser page: search input + type/tag/mastery
      filters against T9.2.2
      Ref: PRD Section 20.1 (Item Browser)
      Output: `frontend/src/features/dashboard/components/ItemBrowser.tsx`

- [ ] T9.3.5 — Implement `DashboardPage`: composes the three independent hooks
      from T9.3.1 so each section renders as soon as its own query resolves,
      with the pending-approvals badge from `overview` shown prominently
      Ref: ARCHITECTURE Section 6.6 (progressive-rendering pattern) · PRD Section 20.1 (Overview screen)
      Output: `frontend/src/features/dashboard/DashboardPage.tsx`

---

## Feature 9.4 — Tests

- [ ] T9.4.1 — Write integration tests for `overview()`, `mastery_by_category()`,
      and `trend_series()` against seeded fixture data with known expected aggregates
      Ref: ARCHITECTURE Section 17.2 (integration testing pattern, applied to dashboard)
      Output: `backend/tests/integration/test_dashboard_service.py`

- [ ] T9.4.2 — Write frontend component tests confirming `MasteryBreakdownChart`
      and `TrendChart` render correctly given fixture data
      Ref: ARCHITECTURE Section 17.2 (Frontend components row)
      Output: `frontend/src/features/dashboard/components/__tests__/`

---

---

# EPIC 10 — Backup & Settings

> Cross-cutting concern that can run in parallel with Epics 5–9 once Epic 4
> (`ApprovalService`) exists, since the post-approval-commit backup hook
> attaches there.

**What "done" means for this epic:**
- `perform_backup()` uses SQLite's online backup API and produces a restorable snapshot
- Backups are triggered both on FastAPI startup (if none taken today) and after
  every `ApprovalService.approve()`/`approve_edited()` commit, idempotently
- Rotation correctly retains 14 daily + 6 monthly snapshots and prunes the rest
- The Settings page exposes runtime-adjustable scheduler config (Epic 5's
  `SchedulerSettings` values) and a backup list with a learner-confirmed restore action

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 21 (Backups) · Section 15 (Constraints)
docs/ARCHITECTURE.md   ← Section 3 (ADR-10) · Section 6.7 (Sequence: Backup) ·
                          Section 12 (Configuration, full) · Section 13.4–13.5 (Security: DB corruption, backup recovery)
```

---

## Feature 10.1 — Backup Service

- [ ] T10.1.1 — Implement `BackupService.perform_backup()`: use
      `sqlite3.Connection.backup()` (the online backup API, not a raw file copy)
      to write a timestamped snapshot into the configured backup directory
      Ref: ARCHITECTURE Section 3 (ADR-10)
      Output: `backend/app/backup/service.py`

- [ ] T10.1.2 — Implement `rotate()`: retain the last 14 daily + 6 monthly
      snapshots (both counts read from `Config`, per PRD Section 21), delete the rest
      Ref: ARCHITECTURE Section 6.7 (sequence diagram, rotate step) · PRD Section 21 (Backups)
      Output: `backend/app/backup/service.py` (extend)

- [ ] T10.1.3 — Implement `check_and_backup_if_needed()`: idempotent, cheap
      no-op if already backed up today; wire it into the FastAPI `lifespan`
      startup (Epic 1/3) and as a post-commit hook at the end of
      `ApprovalService.approve()`/`approve_edited()` (Epic 4)
      Ref: ARCHITECTURE Section 6.7 (Trigger A / Trigger B) · Section 3 (ADR-03)
      Output: `backend/app/backup/service.py` (extend) · `backend/app/main.py` (wire startup) · `backend/app/approvals/service.py` (wire post-commit hook)

- [ ] T10.1.4 — Implement `BackupService.list_backups()` and `.restore(path)`:
      restore is a deliberately manual, learner-confirmed action, never automatic
      Ref: ARCHITECTURE Section 13.5 (Backup Recovery)
      Output: `backend/app/backup/service.py` (extend)

---

## Feature 10.2 — Configuration & Settings

- [ ] T10.2.1 — Implement a `Config` table CRUD service covering every
      runtime-adjustable parameter listed in Architecture Section 12.2
      (`decay_rate`, `correct_threshold`, mastery-adjust values,
      `category_balance_ratio`, proficiency blend weights, backup retention counts)
      Ref: ARCHITECTURE Section 12.2 (Runtime-Adjustable Config)
      Output: `backend/app/settings/service.py`

- [ ] T10.2.2 — Implement the `/settings` router: `GET`/`PUT` config values,
      `GET /settings/backups` (list), `POST /settings/backups/{name}/restore`
      Ref: ARCHITECTURE Section 12.3 (Why the split)
      Output: `backend/app/settings/router.py`

- [ ] T10.2.3 — Implement `SettingsPage`: a config-editing form for the runtime
      values from T10.2.1, and a backup list with a restore action gated behind
      a confirmation dialog (using the `shared/components` confirmation pattern
      established in the shared component set)
      Ref: PRD Section 20.1 (Settings screen) · ARCHITECTURE Section 13.5 (manual, confirmed restore)
      Output: `frontend/src/features/settings/SettingsPage.tsx` · `frontend/src/features/settings/hooks/`

---

## Feature 10.3 — Startup Integrity Check

- [ ] T10.3.1 — Extend the `/health` endpoint / startup sequence from Feature
      1.1 with the full corrupted-DB recovery path: on `PRAGMA integrity_check`
      failure, surface a persistent recovery notice (not an automatic overwrite)
      offering restore from the most recent backup via T10.1.4
      Ref: ARCHITECTURE Section 11.1 (SQLite file corruption row) · Section 13.4 (Database Corruption)
      Output: `backend/app/main.py` (extend) — recovery notice reachable from `/dashboard/overview`'s health field (Epic 9, T9.1.1)

---

## Feature 10.4 — Tests

- [ ] T10.4.1 — Write integration tests for a full backup → rotate → restore
      round-trip against a temp DB, including verifying rotation correctly
      prunes beyond the retention window
      Ref: ARCHITECTURE Section 3 (ADR-10) · Section 6.7
      Output: `backend/tests/integration/test_backup_service.py`

- [ ] T10.4.2 — Write an integration test that deliberately corrupts a fixture
      DB file and asserts the startup integrity check correctly surfaces the
      recovery notice rather than crashing or silently continuing
      Ref: ARCHITECTURE Section 13.4 (Database Corruption)
      Output: `backend/tests/integration/test_startup_integrity.py`

---

---

# EPIC 11 — Polish, Edge Cases & QA Hardening

> Always last. Do not start until Epics 1–10 (including the parallel E10
> branch) are complete and individually smoke-tested.

**What "done" means for this epic:**
- Every item in PRD Section 25's MVP Definition checklist is verified against
  the running application
- Every failure mode in Architecture Section 11.1 not already covered by an
  epic-specific test has an explicit handler and a passing test
- All 5 PRD Flows (Section 10) have been walked through manually against a
  real Obsidian vault and a real (or realistic fixture) Ollama-hosted model
- `ruff check` and `tsc --noEmit`/`eslint` pass with zero warnings across the
  entire codebase

**Files to attach to this epic's chat:**
```
docs/PRD.md            ← Section 25 (MVP Definition) · Section 10 (Flows 1-5, full)
docs/ARCHITECTURE.md   ← Section 11 (Error Handling, full) · Section 16 (Implementation Risks) ·
                          Section 17.4 (What Is Explicitly Not Tested — confirms manual E2E is by design, not a gap)
```

---

## Feature 11.1 — Error Handling Completeness Pass

- [ ] T11.1.1 — Audit Architecture Section 11.1's full failure-mode table
      against the implemented codebase; implement or verify any handler not
      already covered by an epic-specific task (in particular: the HTTP 502
      messaging for Ollama-unreachable on synchronous quiz/writing endpoints,
      and the SQLite-locked retry/backoff wrapper around session commits)
      Ref: ARCHITECTURE Section 11.1 (full table) · Section 11.2 (General Retry Discipline)
      Output: gaps closed in the relevant `backend/app/*/service.py` files; one test added per closed gap

---

## Feature 11.2 — MVP Checklist Verification

- [ ] T11.2.1 — Walk every checkbox in PRD Section 25 (MVP Definition) against
      the running application one by one; for any unmet item, file it as a
      concrete follow-up task and fix it before closing this epic
      Ref: PRD Section 25 (MVP Definition, full checklist)
      Output: a completed checklist with every item verified true against the running app

---

## Feature 11.3 — Manual End-to-End Smoke Tests

> All tasks in this feature are manual — they cannot be automated, consistent
> with Architecture Section 17.4's explicit scoping decision.

- [ ] T11.3.1 — Manually walk PRD Flow 1 (Daily Study & Note Ingestion) end to
      end against a real Obsidian vault: save a note, confirm it appears in the
      approval inbox, approve it, confirm it's schedulable in a quiz
      Ref: PRD Section 10 (Flow 1)
      Output: all steps confirmed working on the real vault

- [ ] T11.3.2 — Manually walk PRD Flow 2 (Ad-hoc Quiz Session) across all 7
      quiz modes plus Random
      Ref: PRD Section 10 (Flow 2)
      Output: all 8 mode variants confirmed working

- [ ] T11.3.3 — Manually walk PRD Flow 3 (Mini Writing Task) including
      confirming a suggested item reaches the approval inbox
      Ref: PRD Section 10 (Flow 3)
      Output: confirmed working, including the approval round-trip

- [ ] T11.3.4 — Manually walk PRD Flow 4 (Sunday Weekly Review) twice: once
      with a normal week's material, once simulating a zero-lessons-studied week
      Ref: PRD Section 10 (Flow 4) · Section 19.2 (Adaptive Content Volume)
      Output: both variants confirmed producing correct, non-fabricated reports

- [ ] T11.3.5 — Manually walk PRD Flow 5 (Reviewing Approval Inbox) including
      abandoning a partial review session and resuming it later
      Ref: PRD Section 10 (Flow 5)
      Output: confirmed safe to abandon/resume, per-item commit behavior verified

- [ ] T11.3.6 — Manually test backup restore: take a backup, make further
      changes, restore from the earlier backup, confirm the DB reverts correctly
      Ref: PRD Section 25 (MVP checklist — backup restore item)
      Output: restore confirmed correct on a real backup file

- [ ] T11.3.7 — Manually test the model-swap requirement: change `OLLAMA_MODEL`
      in config, restart, confirm every pipeline (parsing, quiz, writing,
      report) picks up the new model with zero code changes
      Ref: PRD Section 25 (MVP checklist — model-swap item) · ARCHITECTURE Section 3 (ADR-06)
      Output: confirmed across all four pipelines

---

## Feature 11.4 — Final Hygiene

- [ ] T11.4.1 — Run a full lint pass (`ruff check` backend, `eslint`+`tsc --noEmit`
      frontend) across the entire codebase; fix every warning
      Ref: ARCHITECTURE Appendix (Key Dependencies — `ruff`)
      Output: zero warnings on both toolchains

- [ ] T11.4.2 — Confirm every module and public class/function across the
      codebase has a docstring consistent with the discipline established
      throughout Epics 1–10 (per this document's Documentation note)
      Ref: this document's "How to Read This Document" (Documentation note)
      Output: spot-checked across every `backend/app/*/service.py` and every non-trivial frontend hook/component

---

## Canonical File Locations

| What | Where |
|---|---|
| This file | `docs/TASK_PLAN.md` |
| Product requirements | `docs/PRD.md` |
| Architecture reference | `docs/ARCHITECTURE.md` |
| Backend source | `backend/app/` |
| Backend tests | `backend/tests/` |
| Frontend source | `frontend/src/` |

---

*This task plan is derived directly from `ARCHITECTURE.md` v1.1 and `PRD.md`
v1.0. Both are treated as frozen for the duration of MVP implementation — if
executing a task surfaces a genuine contradiction between this plan and either
source document, stop and reconcile the documents before continuing, rather
than silently improvising a resolution. An undocumented deviation is not a
shortcut — it is a surprise for the next epic.*
