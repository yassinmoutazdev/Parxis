# Product Requirements Document (PRD)

## Praxis — Personal AI English Learning Coach

**Version:** 1.0 (MVP)
**Platform:** Local web application, single device (laptop), single user
**Last Updated:** 2026-07-12
**Status:** Ready for Architecture Design

> "Praxis" is a working title (Greek: the practical application of skill/knowledge) used throughout this document to refer to the system. Rename freely at implementation time — nothing in the architecture depends on the name.

---

## 1. Vision

Most language-learning software is built to maximize engagement with the app itself — streaks, gamified points, infinite flashcard queues. Praxis inverts that model. The learning happens elsewhere: in Cambridge grammar books, in the learner's own notes, in essays the learner writes with their own mind. Praxis's job is to **remember what the learner studied, quietly notice what they're weak at, and manufacture the right practice at the right time** — then get out of the way.

The long-term aim is not a certificate. It is **native-like intuition**: the point at which correct, natural English stops being retrieved consciously and starts being produced automatically. Praxis measures progress toward that state and adapts its practice generation accordingly, without ever becoming the thing the learner is learning *from*.

Praxis is deliberately scoped as a **single-user, local-first system**. It is not a product to be sold; it is infrastructure for one person's multi-year learning project, engineered with the discipline of a real product so it doesn't collapse under its own maintenance burden three months in.

---

## 2. Product Goals

### Primary Goals

1. Eliminate the manual overhead of tracking what has been learned, when it was learned, and how well it has stuck.
2. Automatically generate targeted practice (quizzes and writing prompts) from material the learner has actually studied, rather than generic content.
3. Evaluate writing across multiple independent dimensions (correctness, naturalness, vocabulary, coherence) — not just "right or wrong."
4. Surface a truthful, current picture of the learner's ability, including weaknesses that would otherwise stay invisible (recurring collocation errors, avoided grammar structures, etc.).
5. Keep the learner in full control of what enters their permanent learning record — no silent, unreviewed writes to the knowledge base.
6. Remain cheap to run, simple to maintain by one person, and free of vendor lock-in on the AI model layer.

### Explicit Non-Goals (see also Section 6)

- Praxis is not trying to maximize time-on-app or engagement.
- Praxis is not trying to replace study, note-taking, or essay-writing with AI-generated shortcuts.
- Praxis is not a general-purpose chatbot tutor you converse with to "learn English."

---

## 3. User Persona

### Primary (and only) Persona: The Learner

- **Profile:** A single, technically literate adult (the system's own developer and sole user), current level high B2, actively working toward C2 / native-like fluency.
- **Context:** Studies daily (Mon–Sat) from three Cambridge "In Use" books (Collocations, Idioms, Phrasal Verbs), takes notes in Obsidian, and does a structured review every Sunday.
- **Known strengths:** Grammar fundamentals, reading comprehension, technical vocabulary, idea organization.
- **Known weaknesses:** Natural phrasing, collocations, idiomatic usage, verb sequencing, native-like expression — precisely the dimensions that are hardest to self-assess and hardest for generic tools to grade well.
- **Motivations:** Long-term mastery over short-term test scores. High tolerance for a "boring," backend-heavy tool as long as it is reliable and honest about the learner's actual ability.
- **Anti-goals for this persona:** Does not want gamification, does not want AI to write on their behalf, does not want flashcard-style memorization mechanics, does not want to manage metadata or IDs by hand.

There is no secondary persona in the MVP. Every design decision optimizes for this one user's workflow.

---

## 4. Product Philosophy

These principles are non-negotiable design constraints, not aspirations. Every feature in this PRD is expected to be checked against them.

1. **AI organizes and evaluates; it does not teach.** Content originates from real books and the learner's own writing. The AI never generates the primary learning material — only practice, evaluation, and retrieval on top of material the learner produced or studied.
2. **Nothing enters the permanent learning record without human approval.** Parsed notes, AI-suggested vocabulary, and writing-feedback-derived items all pass through a single, consistent approval step before they affect scheduling, mastery scores, or quizzes.
3. **The system reflects current reality, not an idealized schedule.** If three lessons were studied instead of six, the weekly review is built from three. If a weakness fades, its score fades — but its history is never deleted.
4. **No visible flashcard/SRS mechanics.** Spaced-repetition-style scheduling exists purely as an internal ranking signal for which items are eligible for the next quiz. The learner never sees due dates, streaks, or review queues as such — only practice sessions and progress trends.
5. **Model-agnostic by construction.** Every LLM call goes through a `Generator`/`Evaluator` interface. The MVP's default implementation calls a single hosted open-weight model via Ollama, but swapping in a frontier API model for a specific pipeline (e.g., writing evaluation) must be a new adapter class, never an architectural change.
6. **Simplicity over premature scale.** Single user, single device, local-first. No multi-tenancy, no cloud sync, no auth system, no horizontal scaling — until a real need forces it.

---

## 5. Scope

### In Scope (MVP)

- Obsidian vault watching, LLM-based parsing of freeform notes, and an approval workflow for extracted items.
- A structured learning database (SQLite) covering collocations, idioms, phrasal verbs, grammar notes, personal examples, and corrections.
- Quiz generation across 7 modes (recall, fill-in-the-blank, multiple choice, error correction, rewrite naturally, conversation, mini essay) plus a random mixed mode.
- Two writing evaluation tiers: lightweight mini-writing-task feedback, and a deep weekly writing assessment across 5 scoring dimensions.
- An internal (invisible) spaced-repetition-style scheduler that governs quiz item eligibility and mastery decay.
- A weekly review pipeline (adaptive to actual study volume) producing a combined narrative report.
- A local web dashboard: proficiency overview, mastery breakdown, writing/quiz trend charts, approval inbox, item browser, weekly report archive.
- A model-agnostic `Generator`/`Evaluator` abstraction with a default Ollama-backed implementation.
- Local automatic backups of the learning database.

### Out of Scope (MVP)

- Speaking and listening skills (require entirely different evaluation pipelines: ASR, pronunciation scoring, audio UI).
- Multi-device access, mobile apps, cloud sync, remote access.
- Multi-user support, authentication, authorization.
- Vector/semantic search (SQLite FTS5 is used instead; revisit only if demonstrably insufficient).
- Cloud backup / off-machine redundancy built into the app (user may point local backups at an existing sync folder, but Praxis does not implement cloud upload).
- General-subject coaching beyond English (explicitly a future-extensibility target, not MVP work).
- Editing/re-processing of previously approved or previously parsed notes ("write-once" ingestion model).

---

## 6. Non-Goals

Stated explicitly so they are never accidentally reintroduced during implementation:

- **Not a chatbot.** There is no open-ended "chat with the AI about English" surface in the MVP. All AI interaction is task-scoped (parse, generate quiz, evaluate writing, produce report).
- **Not a content library.** Praxis does not host or replace the Cambridge books; it only structures what the learner extracts from them.
- **Not a grading authority.** Scores are estimates to guide practice, not certifications. Praxis never claims equivalence to IELTS/CEFR/TOEFL scoring.
- **Not engagement-optimized.** No streaks, badges, leaderboards (there is only one user), or notification pressure beyond what's functionally necessary.
- **Not fully autonomous.** The system must never silently mutate the learner's permanent knowledge base.

---

## 7. Functional Requirements

### 7.1 Obsidian Ingestion Module

**FR-1.1: Vault Watching**
- The system watches a configured Obsidian vault directory (or subfolder) for file create/modify events.
- Only `.md` files are considered.
- A file is considered "new" the first time it is observed; the system computes and stores a content hash at ingestion time.

**FR-1.2: Note Parsing (LLM-based)**
- On detecting a new or modified-but-unprocessed note, the system sends the raw Markdown content to the configured `Generator` with a parsing-specific prompt.
- The parser extracts zero or more candidate items, each classified as one of: `collocation`, `idiom`, `phrasal_verb`, `grammar_note`, `personal_example`, `correction`.
- Output must conform to a fixed JSON schema (see Section 15.2). Malformed output triggers one automatic retry with an error-correction prompt; a second failure marks the note `PARSE_FAILED` and logs it for manual review — it does not silently drop content.
- The parser additionally performs duplicate/near-duplicate detection against existing `LearningItems` (via FTS5 text search) and attaches a `possible_duplicate_of` reference where confidence is high.

**FR-1.3: Write-Once Ingestion**
- Once a note has been successfully parsed (regardless of approval outcome for its items), it is marked `PROCESSED` and is not automatically re-parsed.
- If a processed note's file is modified afterward, the system detects the content-hash change and surfaces a **non-blocking notification** ("This note changed since it was processed") in the dashboard. No automatic re-parsing or re-scheduling occurs.

**FR-1.4: Approval Screen**
- All parser output lands in a generic `ApprovalQueue`, never directly in `LearningItems`.
- Each queued item is presented with: extracted text, item type, definition/explanation, source note excerpt, and (if applicable) the suggested duplicate.
- The learner may **Approve** (as-is), **Edit & Approve** (modify any field before committing), or **Reject** each item individually, or apply Approve/Reject in bulk to a note's full batch.
- Approved items are written to `LearningItems` with `mastery_score` initialized per Section 17.3 and become eligible for future quiz selection.

### 7.2 Learning Database & Knowledge Model

**FR-2.1:** The system maintains one canonical, structured record per approved learning item (collocation, idiom, phrasal verb, grammar note, personal example) with full source traceability back to the originating note and/or writing evaluation.

**FR-2.2:** Corrections (from writing evaluation or quizzes) are tracked as first-class entities distinct from new-vocabulary items, and are linked to the `LearningItem` they relate to when applicable.

**FR-2.3:** Items support tagging (e.g., `book:collocations-in-use`, `lesson:12`) for retrieval filtering.

### 7.3 Quiz Generation

**FR-3.1:** The system supports 7 quiz types plus a `random` mode that mixes types within a session (see Section 16 for full pipeline).

**FR-3.2:** Quiz items are selected from `LearningItems` that are (a) approved, and (b) currently "due" per the internal scheduler (Section 17), with a fallback to weighted-random selection from all approved items if fewer than the requested count are due.

**FR-3.3:** Objectively-gradable quiz types (recall, fill-in-the-blank, multiple choice, error correction) are graded deterministically where possible, falling back to LLM grading only for free-text recall answers.

**FR-3.4:** Subjectively-gradable quiz types (rewrite naturally, conversation, mini essay) are graded by the configured `Evaluator` using a lightweight rubric (see Section 16.5) — deliberately less exhaustive than the full weekly writing rubric.

**FR-3.5:** Every quiz answer updates the mastery score and review scheduling of its associated `LearningItem`(s) (Section 17).

### 7.4 Writing Evaluation

**FR-4.1: Mini Writing Tasks** — short, frequent, lightweight feedback (grammar/correctness + 1–2 naturalness notes), used as one of the quiz modes and standalone practice.

**FR-4.2: Weekly Writing Assessment** — a deeper evaluation on a randomly generated topic (independent of that week's studied material, with repetition-avoidance against prompt history), scored across 5 independent dimensions: Grammar, Naturalness, Vocabulary, Coherence, Overall.

**FR-4.3:** Both tiers may surface "better alternative" suggestions (collocations, idioms, phrasal verbs, more natural phrasings). Suggestions route through the same `ApprovalQueue` as parsed notes (FR-1.4) before becoming `LearningItems`.

**FR-4.4:** All writing submissions and their evaluations are stored permanently and linked into the weekly report.

### 7.5 Weekly Review Pipeline

**FR-5.1:** A "Start Weekly Review" action (manually triggered by the learner, not time-forced) assembles: all `LearningItems` approved during the current week, a quiz drawn only from that material, one weekly writing assessment, and a combined narrative report.

**FR-5.2:** The pipeline adapts to actual study volume — if only 3 of 6 possible lessons were studied, the review uses those 3 lessons' material only. No requirement is silently inflated or padded.

**FR-5.3:** The report combines quiz performance, mini-writing performance accumulated that week, and the weekly writing assessment into one stored `WeeklyReport` record with both structured metrics and an LLM-generated narrative summary.

### 7.6 Dashboard

**FR-6.1:** Overview page showing an estimated overall proficiency indicator, recent trend, and a snapshot of the current week's activity.

**FR-6.2:** Mastery breakdown by category (collocations, idioms, phrasal verbs, grammar) with per-item drill-down.

**FR-6.3:** Historical trend charts for quiz performance and writing scores (all 5 dimensions) over time.

**FR-6.4:** Approval inbox surfaced prominently whenever pending items exist.

**FR-6.5:** Searchable/filterable item browser across the full learning database.

**FR-6.6:** Weekly report archive, browsable by week.

### 7.7 System Operations

**FR-7.1:** Automatic local backups of the SQLite database on a defined trigger policy (Section 21.3), with rotation to bound disk usage.

**FR-7.2:** All configuration (model provider/name, backup retention, scheduler parameters) lives in a single config file / environment variables — no hardcoded values in application logic.

---

## 8. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Dashboard pages load in <1s from local SQLite on typical laptop hardware. Note parsing completes within a few seconds to ~1 minute depending on hosted model latency (acceptable — asynchronous, not blocking the learner's workflow). |
| **Reliability** | No data loss on process crash mid-write (use DB transactions for every multi-step write, especially approval commits and quiz/writing evaluation persistence). |
| **Data Integrity** | Every `LearningItem`, `QuizQuestion`, and `WritingEvaluation` is immutable once created except for the mutable `mastery_score`/scheduling fields on `LearningItems`; corrections and history are additive, never destructive. |
| **Portability** | The entire application state (DB + config) must be fully recoverable from the backup folder alone. |
| **Maintainability** | Single-developer-maintainable: minimal dependency surface, no infrastructure beyond a Python process and SQLite file. |
| **Model Independence** | No application logic anywhere references a specific model name/provider directly; all LLM calls go through the `Generator`/`Evaluator` interface. |
| **Observability** | All LLM calls (prompt, raw response, parsed result, success/failure) are logged locally for debugging parsing/evaluation quality over time. |
| **Security/Privacy** | Local-only; no requirement for encryption at rest in MVP (single-user, single-machine, non-networked). Explicitly revisit if scope ever expands beyond one device. |

---

## 9. User Stories

### Ingestion & Knowledge Base

- **US-01:** As the learner, I want my Obsidian notes parsed automatically after I save them, so I never have to manually enter vocabulary or grammar into a separate system.
- **US-02:** As the learner, I want to review and approve everything the parser extracts before it becomes part of my permanent knowledge base, so I stay in control of my own learning record.
- **US-03:** As the learner, I want duplicate or near-duplicate items flagged during approval, so my database doesn't fill up with redundant entries over time.
- **US-04:** As the learner, I want to see when a previously processed note has since changed, so I'm aware it wasn't re-parsed, without the system trying to silently reconcile it.

### Practice & Quizzing

- **US-05:** As the learner, I want quizzes generated from material I've actually studied, so my practice reinforces real gaps instead of testing random trivia.
- **US-06:** As the learner, I want multiple quiz formats (not just flashcard recall), so my practice actually resembles production, not memorization.
- **US-07:** As the learner, I want a "random mixed" quiz mode, so a single session can exercise multiple skills at once.
- **US-08:** As the learner, I want quiz item selection to be invisible/automatic — I never want to see "due dates" or manage a review queue myself.

### Writing

- **US-09:** As the learner, I want quick, lightweight feedback on short mini-writing tasks, so I can practice frequently without waiting for a deep evaluation every time.
- **US-10:** As the learner, I want a deep weekly writing assessment on a topic unrelated to what I studied, so it measures my actual overall ability rather than short-term memorization.
- **US-11:** As the learner, I want writing feedback broken into separate scores (grammar, naturalness, vocabulary, coherence, overall), so I understand *which* dimension of my English needs work.
- **US-12:** As the learner, I want genuinely useful phrasing suggestions from writing feedback to be offered as candidates for my learning database, so good corrections aren't lost after I read them once.

### Weekly Review

- **US-13:** As the learner, I want my Sunday review to reflect what I actually studied that week, not an idealized six-lesson plan, so the system never punishes me for a lighter week.
- **US-14:** As the learner, I want one combined weekly report (quiz + mini-writing + weekly essay), so I get a single coherent picture of my week rather than three disconnected scores.

### Progress & Dashboard

- **US-15:** As the learner, I want to see my estimated overall proficiency and its trend over time, so I can tell whether I'm actually improving.
- **US-16:** As the learner, I want a breakdown of mastery by category (collocations, idioms, phrasal verbs, grammar), so I know which area is lagging.
- **US-17:** As the learner, I want old, unpracticed weaknesses to fade from my "current" score over time (while remaining in history), so my dashboard reflects who I am now, not a permanent tally of every mistake I've ever made.
- **US-18:** As the learner, I want to browse and search my full learning history, so I can look up "did I already learn this idiom" at any time.

### System Trust

- **US-19:** As the learner, I want automatic local backups of my learning database, so years of progress data can't be lost to a single disk failure.
- **US-20:** As the learner, I want the AI model used for parsing/quizzing/evaluation to be swappable via configuration, so I'm never locked into one provider.

---

## 10. User Flows

### Flow 1: Daily Study & Note Ingestion

1. Learner studies one lesson from a Cambridge book.
2. Learner writes a freeform Markdown note in Obsidian summarizing what was learned, using no required structure or metadata.
3. Learner saves the file.
4. Praxis's file watcher detects the save within seconds and creates a `Note` record (status `NEW`).
5. Praxis sends the note content to the LLM parser (status → `PARSING`).
6. Parser returns structured candidate items; Praxis validates against the JSON schema.
   - **On success:** items are written to `ApprovalQueue` (note status → `PENDING_APPROVAL`).
   - **On repeated schema failure:** note status → `PARSE_FAILED`; surfaced in dashboard for manual attention; learner's Markdown file is untouched either way.
7. Dashboard shows a badge: "N items awaiting approval."
8. Learner opens the approval screen at a convenient time (not necessarily immediately), reviews each item, and Approves / Edits+Approves / Rejects.
9. Approved items become `LearningItems`, entering the scheduling pool; note status → `PROCESSED`.

### Flow 2: Ad-hoc Quiz Session

1. Learner opens Praxis and selects "Start Quiz."
2. Learner picks a quiz type (or Random) and a target length (e.g., 10 items).
3. Praxis's scheduler selects eligible `LearningItems` (Section 17), weighted toward weaker/overdue items, with category balance.
4. Praxis generates quiz questions via the `Generator` for the selected type(s).
5. Learner answers each question in the UI.
6. Praxis grades each answer (deterministic where possible, LLM-based otherwise) and shows immediate feedback per question.
7. On session completion, Praxis updates `mastery_score` and scheduling fields for every item touched, and stores the `QuizSession` + `QuizQuestions` record.
8. Learner sees a session summary (score, items reinforced, notable mistakes).

### Flow 3: Mini Writing Task

1. Learner selects "Quick Writing Practice" (can happen any day, independent of the weekly cycle).
2. Praxis generates or reuses a lightweight prompt.
3. Learner writes a short response in the UI.
4. Praxis submits the text to the `Evaluator` with the mini-task rubric (Section 18.2).
5. Feedback (correctness notes + 1–2 naturalness notes) is returned and displayed immediately.
6. Any "better alternative" suggestions are added to the `ApprovalQueue`.
7. The submission and evaluation are stored and linked to the current week for later inclusion in the weekly report.

### Flow 4: Sunday Weekly Review

1. Learner selects "Start Weekly Review."
2. Praxis queries all `LearningItems` approved with `created_at` in the current week window.
   - If zero items exist (no study occurred), Praxis still allows the writing assessment to proceed but skips the material-specific quiz, and notes this explicitly in the report rather than fabricating content.
3. Praxis generates a quiz drawn only from this week's material (mixed types).
4. Learner completes the quiz (graded per Flow 2 mechanics).
5. Praxis generates a weekly writing topic, checking against `WritingPrompts` history to avoid repetition, and presents it.
6. Learner writes the weekly essay.
7. Praxis runs the full weekly writing rubric (Section 18.3) via the `Evaluator`.
8. Praxis assembles: this week's quiz results + this week's accumulated mini-writing results + the weekly essay evaluation, and generates a narrative summary via the `Generator`.
9. The combined `WeeklyReport` is stored and immediately viewable; it also appears in the report archive.

### Flow 5: Reviewing Approval Inbox

1. Learner opens "Approvals" from the dashboard.
2. Items are grouped by source (note batch / writing-feedback batch) and sorted oldest-first.
3. For each item: learner sees extracted text, type, explanation, source excerpt, and duplicate warning if any.
4. Learner acts per item (Approve / Edit / Reject) or uses batch actions on an entire group.
5. Actions commit immediately (per item), so partial review sessions are safe to abandon and resume later.

---

## 11. System Architecture

### 11.1 Component Overview

```
┌─────────────────────┐
│   Obsidian Vault      │   (Markdown files, learner-owned, untouched by Praxis)
└──────────┬───────────┘
           │ filesystem events
           ▼
┌─────────────────────┐
│  Vault Watcher         │   (watchdog-based file observer)
└──────────┬───────────┘
           │ new/changed note
           ▼
┌─────────────────────────────────────────────────────────┐
│                     Praxis Backend (FastAPI)              │
│                                                             │
│  ┌───────────────┐   ┌──────────────────┐                 │
│  │ Ingestion       │──▶│ Approval Queue    │                 │
│  │ Service         │   │ Service           │                 │
│  └───────┬───────┘   └────────┬─────────┘                 │
│          │                     │ approved items              │
│          ▼                     ▼                             │
│  ┌────────────────────────────────────────┐                │
│  │        Learning Database (SQLite + FTS5) │                │
│  └───────────┬───────────────┬────────────┘                │
│              │               │                                │
│    ┌─────────▼──────┐ ┌──────▼─────────┐                    │
│    │ Scheduler        │ │ Retrieval        │                    │
│    │ (mastery/decay)  │ │ Service (SQL/FTS)│                    │
│    └─────────┬──────┘ └──────┬─────────┘                    │
│              │               │                                │
│    ┌─────────▼───────────────▼─────────┐                    │
│    │   Quiz / Writing / Report Pipelines  │                    │
│    └─────────────────┬───────────────────┘                    │
│                       │                                        │
│              ┌────────▼─────────┐                              │
│              │ Generator/Evaluator│  (abstract interface)      │
│              │ Interface          │                              │
│              └────────┬─────────┘                              │
│                       │ default adapter                        │
│              ┌────────▼─────────┐                              │
│              │ Ollama Adapter     │──▶ Hosted open-weight model  │
│              └───────────────────┘     (e.g., gemma4:31b)       │
│                                                                  │
│              ┌───────────────────┐                              │
│              │ Backup Service      │──▶ local rotating snapshots │
│              └───────────────────┘                              │
└──────────────────────────┬──────────────────────────────────┘
                            │ REST/JSON API
                            ▼
                 ┌─────────────────────┐
                 │  Frontend SPA          │
                 │  (dashboard, quiz UI,  │
                 │   approval UI, writing │
                 │   editor)               │
                 └─────────────────────┘
```

### 11.2 Component Responsibilities

| Component | Responsibility |
|---|---|
| **Vault Watcher** | Observes the Obsidian vault folder; emits ingestion events on file create/modify. No parsing logic here. |
| **Ingestion Service** | Reads note content, computes content hash, calls `Generator` for parsing, validates schema, writes to `ApprovalQueue`, manages `Note` state machine. |
| **Approval Queue Service** | CRUD over pending items; on approval, commits to `LearningItems`/`Corrections` in a single transaction; on rejection, marks item discarded (retained for audit, not deleted). |
| **Learning Database** | SQLite file, single source of truth. FTS5 virtual table over item text for duplicate detection and text search. |
| **Scheduler** | Computes review eligibility and updates mastery scores after every quiz/writing interaction (Section 17). Pure functions over DB rows — no background jobs required. |
| **Retrieval Service** | Provides scoped, structured queries for each pipeline's context needs (Section 15). |
| **Quiz / Writing / Report Pipelines** | Orchestrate retrieval → prompt construction → `Generator`/`Evaluator` call → validation → persistence for their respective domains. |
| **Generator/Evaluator Interface** | Abstract contract (`generate(task, context) -> structured_output`, `evaluate(task, content, context) -> structured_output`). Decouples all pipelines from any specific model provider. |
| **Ollama Adapter** | Default MVP implementation; calls Ollama's REST API against a configured model string; handles retries and JSON-schema-enforcing prompt wrapping. |
| **Backup Service** | Event-triggered (not cron-based) snapshotting of the SQLite file with rotation (Section 21.3). |
| **Frontend SPA** | All learner-facing UI; communicates with backend exclusively via REST/JSON. |

### 11.3 Why Event-Driven Instead of a Scheduler Library

Nearly every action in this system is naturally triggered by something the learner does (save a note, start a quiz, submit writing) or by application lifecycle events (startup). The only genuinely time-based need is backups, and that can be satisfied by a **startup check** ("has a backup been taken today? if not, take one now") plus a **post-write hook** (backup after any approval-queue commit batch), with no calendar-based dependency at all. **Recommendation: do not add APScheduler (or any scheduler library) to the MVP.** If a genuine wall-clock-driven need emerges later (e.g., a nightly maintenance job unrelated to any event), introduce a scheduler at that point — not preemptively.

### 11.4 Frontend Architecture Recommendation

The learner explicitly wants long-term room for an interactive dashboard, quiz interfaces, an approval workflow, a writing editor, and eventually a conversational surface — while staying technology-agnostic at the PRD stage rather than optimizing purely for initial simplicity.

**Recommendation: a decoupled Single Page Application, React + TypeScript + Vite, communicating with the FastAPI backend purely over a REST/JSON API.**

Rationale:
- **Clean separation of concerns.** The backend has zero knowledge of rendering; the frontend has zero knowledge of persistence or LLM orchestration. This makes it possible to redesign or even fully replace the UI later (e.g., a native app) without touching backend logic — directly serving the "grow into a richer app later" requirement.
- **Ecosystem maturity for the specific UI surfaces required.** Interactive charts (mastery trends, score history), a rich text/writing editor, drag-free approval workflows, and eventually a conversational chat UI are all well-served by mature, actively maintained React libraries (Recharts/Visx for charts, TipTap or a plain `<textarea>`-based editor for writing, standard component patterns for approval queues and chat threads).
- **TypeScript** enforces a typed contract against the backend's Pydantic models, catching integration bugs at build time rather than at runtime — valuable for a solo maintainer who won't have a QA team catching regressions.
- **Vite** keeps the build tooling minimal and fast; this is not "enterprise React," it's the smallest reasonable footprint that still gives full SPA capability.

Explicitly rejected alternatives and why:
- **Server-rendered Jinja2 + HTMX** (the earlier recommendation) — reconsidered per the learner's feedback. It minimizes initial build tooling, but a conversational UI and a rich interactive writing/quiz experience push against HTMX's grain; committing to it now would mean a likely rewrite later rather than incremental growth.
- **SvelteKit** — a reasonable, slightly lighter-weight alternative with a smaller bundle size and less boilerplate than React; noted here as a legitimate substitution if the learner prefers Svelte's ergonomics, but React is recommended as the safer long-term default given library breadth for charts, editors, and chat-style UIs specifically.

State management within the frontend: **TanStack Query** for all server-state (fetching quiz sessions, approval queue, dashboard data) rather than a global client-state library — the backend/database is the actual source of truth, so the frontend should treat almost everything as server state with caching/invalidation, not duplicate it into client state.

---

## 12. Database Design

SQLite, single file, WAL mode enabled for crash safety during concurrent read/write. FTS5 virtual table mirrors item text for duplicate detection and search.

### Entity: Source

```
Source
├── id (INTEGER, primary key)
├── title (TEXT) — e.g. "English Collocations in Use"
├── author (TEXT, nullable)
├── source_type (ENUM: BOOK | OTHER)
└── created_at (TIMESTAMP)
```

### Entity: Lesson

```
Lesson
├── id (INTEGER, primary key)
├── source_id (FK → Source.id, nullable)
├── title (TEXT) — e.g. "Unit 12: Business Collocations"
├── order_index (INTEGER, nullable)
└── created_at (TIMESTAMP)
```

### Entity: Note

```
Note
├── id (INTEGER, primary key)
├── vault_path (TEXT) — relative path within the Obsidian vault
├── content_hash (TEXT) — hash at time of last successful parse
├── lesson_id (FK → Lesson.id, nullable) — inferred or unset
├── status (ENUM: NEW | PARSING | PENDING_APPROVAL | PROCESSED | PARSE_FAILED)
├── changed_since_processed (BOOLEAN, default false)
├── created_at (TIMESTAMP)
└── processed_at (TIMESTAMP, nullable)
```

### Entity: ApprovalQueue

```
ApprovalQueue
├── id (INTEGER, primary key)
├── source_type (ENUM: NOTE_PARSE | WRITING_FEEDBACK | QUIZ_FEEDBACK)
├── source_id (INTEGER) — Note.id or WritingEvaluation.id or QuizQuestion.id
├── item_type (ENUM: COLLOCATION | IDIOM | PHRASAL_VERB | GRAMMAR_NOTE | PERSONAL_EXAMPLE | CORRECTION)
├── extracted_text (TEXT)
├── explanation (TEXT, nullable)
├── example_sentence (TEXT, nullable)
├── source_context (TEXT) — verbatim excerpt the item was drawn from
├── possible_duplicate_of (FK → LearningItem.id, nullable)
├── status (ENUM: PENDING | APPROVED | EDITED_APPROVED | REJECTED)
├── reviewed_payload (JSON, nullable) — final values if edited before approval
├── created_at (TIMESTAMP)
└── reviewed_at (TIMESTAMP, nullable)
```

### Entity: LearningItem

```
LearningItem
├── id (INTEGER, primary key)
├── item_type (ENUM: COLLOCATION | IDIOM | PHRASAL_VERB | GRAMMAR_NOTE | PERSONAL_EXAMPLE)
├── text (TEXT) — canonical form, e.g. "break the ice"
├── definition (TEXT, nullable)
├── example_sentence (TEXT, nullable)
├── source_note_id (FK → Note.id, nullable)
├── source_approval_id (FK → ApprovalQueue.id)
├── mastery_score (REAL, 0.0–1.0, default 0.3)
├── review_count (INTEGER, default 0)
├── correct_count (INTEGER, default 0)
├── incorrect_count (INTEGER, default 0)
├── last_reviewed_at (TIMESTAMP, nullable)
├── next_review_due (TIMESTAMP, nullable)
├── ease_factor (REAL, default 2.5) — SM-2-style parameter
├── interval_days (INTEGER, default 0)
├── suspended (BOOLEAN, default false) — manual opt-out, not deletion
└── created_at (TIMESTAMP)
```

### Entity: Correction

```
Correction
├── id (INTEGER, primary key)
├── learning_item_id (FK → LearningItem.id, nullable)
├── wrong_form (TEXT)
├── correct_form (TEXT)
├── explanation (TEXT, nullable)
├── source_type (ENUM: WRITING | QUIZ)
├── source_id (INTEGER) — WritingEvaluation.id or QuizQuestion.id
└── created_at (TIMESTAMP)
```

### Entity: Tag / LearningItemTag

```
Tag
├── id (INTEGER, primary key)
└── name (TEXT, unique) — e.g. "book:idioms-in-use", "lesson:7"

LearningItemTag
├── learning_item_id (FK → LearningItem.id)
└── tag_id (FK → Tag.id)
```

### Entity: QuizSession / QuizQuestion

```
QuizSession
├── id (INTEGER, primary key)
├── quiz_scope (ENUM: AD_HOC | WEEKLY_REVIEW)
├── quiz_mode (ENUM: RECALL | FILL_BLANK | MULTIPLE_CHOICE | ERROR_CORRECTION |
│               REWRITE_NATURALLY | CONVERSATION | MINI_ESSAY | RANDOM)
├── started_at (TIMESTAMP)
├── completed_at (TIMESTAMP, nullable)
└── week_id (FK → WeeklyReport.id, nullable) — set only for WEEKLY_REVIEW scope

QuizQuestion
├── id (INTEGER, primary key)
├── quiz_session_id (FK → QuizSession.id)
├── learning_item_id (FK → LearningItem.id, nullable) — nullable for free-form types
├── question_type (ENUM, mirrors QuizSession.quiz_mode values minus RANDOM)
├── prompt (TEXT)
├── correct_answer (TEXT, nullable) — null for open-ended types graded by rubric
├── user_answer (TEXT, nullable)
├── is_correct (BOOLEAN, nullable) — null for scored (non-binary) types
├── score (REAL, nullable) — 0.0–1.0, for rubric-graded types
├── feedback (TEXT, nullable)
├── graded_by (ENUM: DETERMINISTIC | LLM)
└── created_at (TIMESTAMP)
```

### Entity: WritingPrompt / WritingSubmission / WritingEvaluation

```
WritingPrompt
├── id (INTEGER, primary key)
├── prompt_type (ENUM: MINI | WEEKLY)
├── topic (TEXT)
├── used_at (TIMESTAMP)
└── week_id (FK → WeeklyReport.id, nullable)

WritingSubmission
├── id (INTEGER, primary key)
├── prompt_id (FK → WritingPrompt.id)
├── submission_type (ENUM: MINI | WEEKLY)
├── submitted_text (TEXT)
├── word_count (INTEGER)
└── created_at (TIMESTAMP)

WritingEvaluation
├── id (INTEGER, primary key)
├── submission_id (FK → WritingSubmission.id)
├── grammar_score (REAL, nullable) — 0–100; null for MINI (correctness notes only, no numeric score)
├── naturalness_score (REAL, nullable)
├── vocabulary_score (REAL, nullable)
├── coherence_score (REAL, nullable)
├── overall_score (REAL, nullable)
├── feedback_json (JSON) — structured per-dimension notes
├── suggested_items_json (JSON) — candidate items sent to ApprovalQueue
├── evaluator_model (TEXT) — which Generator/Evaluator adapter+model produced this
└── created_at (TIMESTAMP)
```

### Entity: WeeklyReport

```
WeeklyReport
├── id (INTEGER, primary key)
├── week_start (DATE)
├── week_end (DATE)
├── items_studied_count (INTEGER)
├── quiz_summary_json (JSON)
├── mini_writing_summary_json (JSON)
├── weekly_writing_evaluation_id (FK → WritingEvaluation.id, nullable)
├── mastery_snapshot_json (JSON) — category-level mastery at time of report
├── narrative_report (TEXT) — LLM-generated summary
└── created_at (TIMESTAMP)
```

### Entity: Config / AuditLog

```
Config  (key-value)
├── key (TEXT, primary key)
└── value (TEXT)

Example keys:
- model_provider ("ollama")
- model_name ("gemma4:31b")
- backup_retention_daily (14)
- backup_retention_monthly (6)
- vault_path

AuditLog
├── id (INTEGER, primary key)
├── timestamp (TIMESTAMP)
├── event_type (ENUM: PARSE_FAILED | BACKUP_TAKEN | BACKUP_FAILED | CONFIG_CHANGE | APPROVAL_ACTION)
├── description (TEXT)
└── metadata (JSON, nullable)
```

### Relationships Summary

- One `Note` → many `ApprovalQueue` items (1:N)
- One `ApprovalQueue` item → at most one `LearningItem` (1:0..1, on approval)
- One `LearningItem` → many `Correction`, many `QuizQuestion`, many `LearningItemTag` (1:N each)
- One `WeeklyReport` → one `WritingEvaluation` (weekly) + many `QuizSession` (1:N) + many mini `WritingEvaluation`s via week association

### Denormalization Strategy

- `ApprovalQueue.source_context` stores a verbatim excerpt rather than only a foreign key, so the approval screen remains meaningful even if the source note is later altered.
- `WeeklyReport.mastery_snapshot_json` stores a point-in-time copy of category mastery, so historical reports remain accurate even as `LearningItem.mastery_score` continues to change going forward.

---

## 13. Data Flow

**Ingestion path:**
`Obsidian file save → Vault Watcher event → Ingestion Service → Generator.parse() → schema validation → ApprovalQueue rows → (learner action) → LearningItem/Correction rows → Scheduler initializes mastery fields`

**Quiz path:**
`Quiz request (mode, size) → Scheduler.select_eligible_items() → Retrieval Service assembles item context → Generator.generate(quiz_task) → schema validation → QuizQuestion rows (prompt only) → learner answers → grading (deterministic or Evaluator.evaluate()) → QuizQuestion updated with result → Scheduler.update_mastery() per item → QuizSession marked completed`

**Writing path (mini or weekly):**
`Writing prompt request → Retrieval Service (recent prompts, for repetition avoidance) → Generator.generate(prompt_task) → WritingPrompt row → learner submits text → WritingSubmission row → Evaluator.evaluate(writing_task, text, context) → WritingEvaluation row → suggested items → ApprovalQueue rows`

**Weekly report path:**
`Trigger "Start Weekly Review" → Retrieval Service gathers week-scoped LearningItems, QuizSessions, WritingEvaluations → weekly quiz + weekly writing flows execute (see above) → aggregation → Generator.generate(report_task) → WeeklyReport row`

**Backup path:**
`Startup check OR post-approval-commit hook → Backup Service copies DB file with WAL checkpoint → rotation prunes old snapshots → AuditLog entry`

---

## 14. State Management

### Note lifecycle

```
NEW → PARSING → PENDING_APPROVAL → PROCESSED
             └──────────────────→ PARSE_FAILED (after retry exhausted)
```
`PROCESSED` notes may additionally flip `changed_since_processed = true` on later file modification, without changing `status`.

### ApprovalQueue item lifecycle

```
PENDING → APPROVED           (commits to LearningItem/Correction)
       → EDITED_APPROVED     (commits edited values to LearningItem/Correction)
       → REJECTED            (retained for audit; never enters LearningItems)
```
All transitions are terminal — no re-opening a reviewed item in the MVP (a rejected suggestion can reappear naturally if the same expression is encountered again later, at which point duplicate detection will reference the original rejected entry's context if still relevant).

### QuizSession lifecycle

```
(created) → IN_PROGRESS → COMPLETED
```
Sessions are created with all questions pre-generated (not generated one-at-a-time as the learner progresses), so a session can be safely abandoned mid-way without partial-generation inconsistency; an abandoned session simply never reaches `COMPLETED` and does not affect mastery scores for its unanswered questions.

### WritingSubmission / WritingEvaluation lifecycle

```
SUBMITTED → EVALUATING → EVALUATED
                       → EVALUATION_FAILED (surfaced to learner, retry available; submission text is never lost)
```

### LearningItem mastery state

Not a discrete state machine — a continuous `mastery_score` updated after every interaction (Section 17). `suspended` is the only discrete flag, and it is manual/opt-in only (not used by MVP automation), reserved for the learner to pull an item out of rotation without deleting it.

---

## 15. Retrieval Strategy

### 15.1 Decision: SQLite + FTS5, no vector search

All retrieval needs identified for this system are structured and filterable by known dimensions (date, item type, review-due status, week association) rather than requiring semantic/embedding-based similarity:

| Pipeline | Retrieval need | Query shape |
|---|---|---|
| Note parsing (duplicate check) | "Does an item with similar text already exist?" | FTS5 `MATCH` query against `LearningItem.text` + explanation, ranked by BM25, top-3 candidates surfaced to the learner (not auto-merged) |
| Quiz generation | "N eligible items, weighted by due-ness and weakness" | SQL filter on `suspended = false AND (next_review_due <= now OR review_count = 0)`, ordered by a computed weakness score |
| Weekly review | "Everything approved this week" | SQL filter on `LearningItem.created_at BETWEEN week_start AND week_end` |
| Writing evaluation context | "My known weak items relevant to what I just wrote" | FTS5 `MATCH` of submission text tokens against `LearningItem.text`/`definition`, to surface items the learner already knows so feedback can reference them by name — see caveat below |
| Dashboard | Aggregate stats | Standard SQL `GROUP BY`/aggregate queries |

**Caveat on writing evaluation context:** FTS5 token matching is lexical, not semantic — it will not connect "I felt disappointed" to a learned idiom like "let down" unless there's token overlap. This is an accepted MVP limitation. If, after real use, this measurably degrades writing feedback quality (the Evaluator can't reference already-known relevant expressions), **embedding-based semantic retrieval is the first and only recommended upgrade path** — added as an additive retrieval mode, not a replacement of FTS5. This is intentionally deferred, not dismissed.

### 15.2 Context Assembly Principle

Every pipeline receives a purpose-built, minimal context object — never the full database. Each `Generator`/`Evaluator` call is constructed as:

```
{
  "task": "<parse_note | generate_quiz | evaluate_writing | generate_report | ...>",
  "context": { ...retrieved, scoped data only... },
  "output_schema": { ...JSON schema the response must conform to... }
}
```

The Ollama adapter is responsible for prompt-wrapping this into the target model's expected chat format and enforcing schema conformance (via prompt instruction + validation + retry, since Ollama-hosted models cannot be assumed to support native structured-output constraints reliably).

---

## 16. Quiz Generation Pipeline

### 16.1 Eligibility & Selection

1. Query all `LearningItem` rows where `suspended = false`.
2. Partition into **due** (`next_review_due <= now OR review_count = 0`) and **not-due**.
3. Compute a `weakness_score = 1 - mastery_score` for each due item.
4. Sample the requested quiz size from the due pool, weighted by `weakness_score`, with a **category balance constraint**: no more than ~60% of a session drawn from a single `item_type`, to avoid a session becoming e.g. all-phrasal-verbs by chance.
5. If the due pool is smaller than the requested size (common early on), backfill from the not-due pool using the same weighting, oldest-`last_reviewed_at`-first.
6. For `WEEKLY_REVIEW` scope, skip steps 1–5 entirely and instead select only from items with `created_at` in the current week window.

### 16.2 Question Type Assignment

- If a specific mode was requested, all questions use that mode.
- If `RANDOM` was requested, each question is independently assigned one of the 7 concrete modes, still respecting the category-balance constraint from 16.1.

### 16.3 Prompt Construction (per type)

Each quiz mode has a dedicated prompt template that receives: the target `LearningItem`(s) (text, definition, example), and — for error-correction and rewrite-naturally types — a synthetically constructed "flawed" sentence the model is asked to generate first, which then becomes the question. The `output_schema` requires: `prompt_text`, `correct_answer` (where applicable), and for multiple-choice, `distractors` (plausible but incorrect options, explicitly instructed not to be trivially eliminable).

### 16.4 Deterministic Grading (Recall, Fill-in-blank, MC, Error Correction)

- Exact/normalized string match against `correct_answer` (case-insensitive, whitespace-normalized) for fill-in-blank and MC.
- For error correction, the learner's corrected sentence is compared against the model-provided `correct_answer` using normalized match; if it doesn't match exactly but the learner's answer is plausible, fall through to LLM grading (see 16.5) rather than marking it flatly wrong — free-text answers rarely match a single canonical string.
- For recall (learner must produce the target expression from a definition/prompt with no options), deterministic match is attempted first; on mismatch, fall through to LLM grading.

### 16.5 LLM-Based Grading (Rewrite Naturally, Conversation, Mini Essay, and deterministic fallbacks)

A lightweight rubric — deliberately lighter than the full weekly writing rubric (Section 18.3) — scores a single `score` (0.0–1.0) plus one or two sentences of `feedback`. This keeps quiz-embedded writing tasks fast and low-friction, distinct from the deep weekly assessment.

### 16.6 Mastery Update

After each answered question:
```
if correct (score >= 0.7 threshold for scored types):
    ease_factor = min(ease_factor + 0.1, 3.0)
    interval_days = max(1, round(interval_days * ease_factor))
    mastery_score = min(mastery_score + 0.15 * (1 - mastery_score), 1.0)
else:
    ease_factor = max(ease_factor - 0.2, 1.3)
    interval_days = 1
    mastery_score = max(mastery_score - 0.25 * mastery_score, 0.0)
review_count += 1
last_reviewed_at = now
next_review_due = now + interval_days
```
This is a simplified SM-2 variant, not a strict implementation — appropriate here because the product goal is "influence quiz selection," not precise long-term retention optimization. Parameters (0.1, 0.15, 0.2, 0.25, thresholds) are configuration values, not hardcoded, so they can be tuned after real-world use without a schema change.

---

## 17. Progress Tracking & Mastery Decay Logic

### 17.1 Design Goal

The dashboard must reflect **current** ability, not a lifetime cumulative tally. An item mastered a year ago and never revisited should not still register as "strong" if the learner would plausibly get it wrong today; conversely, a single recent mistake should not permanently brand an otherwise well-known item as "weak" if it's an outlier.

### 17.2 Read-Time Decay (not write-time / not cron-based)

`mastery_score` as stored is the value **as of `last_reviewed_at`**. Whenever mastery is *read* for display or for quiz weighting, a decay function is applied on the fly:

```
days_since_review = (now - last_reviewed_at).days
decayed_score = mastery_score * exp(-DECAY_RATE * days_since_review)
```

`DECAY_RATE` is a configuration constant (suggested default: tuned so a fully-mastered item (1.0) decays to ~0.5 after roughly 90 days of no exposure — deliberately slow, since the goal is intuition-building, not cramming). This means:
- No background job is needed to "age" scores — decay is computed lazily, exactly once per read, from stored timestamps.
- Full history (`review_count`, `correct_count`, `incorrect_count`, every `QuizQuestion` row) is retained forever regardless of decay; decay only affects the *current-estimate* view, never the historical record.

### 17.3 New Item Initialization

New `LearningItem`s start at `mastery_score = 0.3` (deliberately below neutral — freshly learned material is assumed fragile until reinforced at least once), `review_count = 0`, which also makes them immediately eligible ("due") for the next quiz regardless of decay math.

### 17.4 Category & Overall Proficiency Aggregation

- **Category mastery** = weighted average of decayed `mastery_score` across all non-suspended `LearningItem`s in that category, weighted by `review_count` (so a single lucky guess on a brand-new item doesn't swing the category average as much as a well-exercised item).
- **Overall estimated proficiency** = a weighted blend of (a) category mastery averages, and (b) the rolling average of the last N weekly-writing `overall_score` values, since writing performance is the more holistic signal of production ability versus item-level recall. Suggested default blend: 40% item mastery / 60% recent writing performance — configurable, and explicitly labeled on the dashboard as an *estimate*, never presented as a certified level.

---

## 18. Writing Evaluation Pipeline

### 18.1 Shared Evaluation Contract

Both mini and weekly evaluations call `Evaluator.evaluate(task, submitted_text, context)`. Context always includes: the learner's known weak categories (top-N lowest-mastery categories), and — where FTS5 surfaces a lexical match (Section 15.1) — a short list of already-known relevant expressions the model may reference by name in feedback ("you already know the idiom 'let down' — consider using it here instead of...").

### 18.2 Mini Writing Task Rubric

- **Correctness check:** grammar/spelling/syntax errors identified inline, each with a brief explanation.
- **Naturalness notes:** 1–2 specific observations maximum (deliberately capped, to keep this "lightweight" as specified) — not a full multi-dimensional score.
- **Output schema:** `{ corrections: [{wrong, correct, explanation}], naturalness_notes: [string], suggested_items: [...] }`
- No numeric scores are stored for mini tasks (`WritingEvaluation` numeric fields remain null) — mini tasks feed the weekly report as qualitative signal + correction counts, not as a graded metric in their own right.

### 18.3 Weekly Writing Assessment Rubric

Five independent scores, each 0–100, each with accompanying qualitative feedback:

1. **Grammar** — correctness of syntax, tense, agreement, punctuation.
2. **Naturalness** — would an educated native speaker phrase it this way; flags stilted, overly literal, or non-idiomatic constructions specifically (this is the learner's stated core weakness and gets the most detailed feedback of the five).
3. **Vocabulary** — range, precision, and appropriateness of word choice; explicitly rewards attempted use of recently-learned collocations/idioms/phrasal verbs.
4. **Coherence** — logical flow, paragraph structure, argument/idea organization (a stated existing strength — tracked to confirm it stays strong, not to over-focus practice here).
5. **Overall** — a holistic score that is **not** a simple average of the other four (the `Evaluator` is instructed to weigh naturalness and grammar more heavily, consistent with the product's C2/native-intuition goal, rather than let strong coherence mask weak naturalness).

Additionally: a `suggested_items` list of concrete better-alternative phrasings, each routed to `ApprovalQueue` with `source_type = WRITING_FEEDBACK`.

### 18.4 Topic Generation & Repetition Avoidance

The weekly topic generator queries the last N (suggested: 12) `WritingPrompt` rows of type `WEEKLY` and instructs the `Generator` to avoid overlapping subject matter, providing those prior topics as negative examples in the prompt context.

### 18.5 Failure Handling

If the `Evaluator` call fails or returns schema-invalid output, the `WritingSubmission` is preserved (never lost) with `WritingEvaluation` status `EVALUATION_FAILED`; the learner can manually retry evaluation from the dashboard without re-submitting the text.

---

## 19. Weekly Review Pipeline

(Full step sequence already specified in Flow 4, Section 10; this section covers pipeline-internal mechanics not covered there.)

### 19.1 Week Boundary Definition

A "week" is defined as Monday 00:00 through Sunday 23:59, learner's local system time. The review is intended to run on Sunday but is **not time-gated** — the trigger is the learner's manual action, and the pipeline always operates on "the most recently completed or currently in-progress week" relative to when it's invoked, so an early or late review still binds to the correct week's data.

### 19.2 Adaptive Content Volume

The pipeline explicitly queries actual data rather than assuming a fixed lesson count (FR-5.2). If `items_studied_count = 0` for the week, the quiz step is skipped entirely and the narrative report states this plainly rather than generating a hollow quiz from unrelated old material.

### 19.3 Report Generation

The `Generator` receives: quiz summary stats (score %, weak items surfaced), mini-writing summary (correction counts, recurring error patterns across the week's mini submissions), and the full weekly writing evaluation (all 5 scores + key feedback points), and produces a narrative summary in the schema:
```
{
  "narrative_report": "<free text, 150-300 words>",
  "top_strengths_this_week": [string, ...],
  "top_focus_areas_next_week": [string, ...]
}
```
This narrative is stored verbatim in `WeeklyReport.narrative_report`; the structured metrics it was built from remain independently queryable for charting (Section 20).

---

## 20. Dashboard Design

### 20.1 Screen Hierarchy

1. **Overview (Home):** Estimated overall proficiency (with trend arrow/sparkline), this week's activity snapshot, pending-approvals badge if nonzero.
2. **Mastery Breakdown:** Category-level bars/scores (collocations, idioms, phrasal verbs, grammar), drill-down to item list per category.
3. **Progress Trends:** Line charts — writing scores (5 series) over time; quiz accuracy over time; items-learned-per-week bar chart.
4. **Approval Inbox:** Grouped pending items (Section 10, Flow 5).
5. **Item Browser:** Full-text searchable/filterable table of all `LearningItem`s (filter by type, tag, mastery range).
6. **Weekly Report Archive:** List of past `WeeklyReport`s, each expandable to full detail.
7. **Practice:** Entry points for ad-hoc quiz and mini writing task (Flows 2–3).
8. **Settings:** Model provider/name, vault path, backup retention — thin wrapper over `Config` table.

### 20.2 Interaction Principles

- No streaks, points, or gamified elements anywhere in the UI (per Product Philosophy #4).
- Approval actions must be completable in a single click for the common case (Approve-as-is), with edit as a secondary, expandable action — friction here directly discourages the "everything gets reviewed" behavior the philosophy depends on.
- Charts always show both the raw historical line and, where decay applies (mastery), a visibly distinct "current estimate" indicator, so the learner can tell the two apart at a glance.

### 20.3 Visual Design Principles

- Clean, low-density, text-forward layout appropriate for a personal tool used by one technically literate adult — no need for the large-touch-target/high-contrast mobile-first patterns relevant to a different kind of product.
- Score displays use consistent color semantics across the app: a single mastery/score gradient (not stoplight red/yellow/green, which reads as "pass/fail" and is a poor fit for a continuous, decaying metric).
- Writing evaluation feedback is displayed as inline annotations against the submitted text where possible (wrong/correct spans), rather than only as a detached list — directly supporting comprehension of *why* a score is what it is.

---

## 21. Future Extensibility

Explicitly designed to be viable later without an MVP rewrite:

1. **Frontier-model evaluator swap.** The `Generator`/`Evaluator` interface is the seam. Adding a Claude/Gemini adapter for writing evaluation specifically (while keeping Ollama for parsing/quizzing) is a new adapter class plus a per-pipeline config value — no pipeline logic changes.
2. **Semantic retrieval upgrade.** If FTS5 proves insufficient for writing-evaluation context relevance (Section 15.1 caveat), an embedding-based retrieval mode can be added additively alongside FTS5 without restructuring the schema (a vector index would sit beside, not replace, existing tables).
3. **Speaking/listening modules.** Out of scope for MVP by design, but the `LearningItem`/`ApprovalQueue`/`Scheduler` core is skill-agnostic; a pronunciation- or listening-comprehension pipeline could plug into the same knowledge base and scheduler with new `item_type` values and new evaluation pipelines, without touching the ingestion or mastery-decay core.
4. **General long-term coaching beyond English.** The learner's stated long-term vision. The current schema is intentionally not English-specific at the structural level (`Source`/`Lesson`/`LearningItem`/`Correction` are generic educational primitives) — subject-specificity currently lives only in prompt templates and `item_type` enum values, both of which are the cheapest possible things to extend later.
5. **Multi-device access.** Explicitly deferred, but the FastAPI/SQLite split already implies a natural seam: introducing a lightweight auth layer and switching SQLite to a networked Postgres instance (or exposing FastAPI over a local network) would not require redesigning the domain model.

---

## 22. Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Open-weight model (Gemma 4 or similar) underperforms on subtle naturalness judgment** — the learner's core weakness is exactly the hardest thing for any model to grade well, and open models may be less reliable here than frontier APIs. | Weekly writing scores (naturalness dimension especially) could be noisy or occasionally wrong, undermining trust in the system's core value proposition. | The `Evaluator` abstraction (Section 11.2, Risk mitigation built into architecture) makes this a config change, not a redesign, if quality proves inadequate after real use. Recommend the learner periodically spot-check naturalness feedback against their own judgment during the first 4-6 weeks specifically. |
| **LLM parser misclassifies or fabricates items from ambiguous freeform notes.** | Low-quality or hallucinated entries reach the approval screen, wasting the learner's review time or (if approved without scrutiny) polluting the knowledge base. | Approval-gate is mandatory and universal (Product Philosophy #2) — this is the primary mitigation. Schema validation + retry catches structurally malformed (not semantically wrong) output. |
| **Ollama-hosted model latency or unavailability** (e.g., host machine asleep, model swapped, network hiccup if hosted remotely). | Parsing, quiz generation, or writing evaluation calls fail or hang. | All `Generator`/`Evaluator` calls have bounded timeouts + limited retries; failures degrade gracefully to a stored "failed" state (Note.PARSE_FAILED, WritingEvaluation.EVALUATION_FAILED) rather than losing learner input or blocking the UI indefinitely. |
| **Duplicate detection false negatives/positives** (FTS5 is lexical, not semantic — "break the ice" vs. "breaking the ice" vs. a synonym idiom may not match). | Knowledge base could accumulate near-duplicates, or conversely flag unrelated items as duplicates. | Learner has final say at approval time regardless (mitigated by design); acceptable MVP-level noise given the human-in-the-loop gate. |
| **Weekly review skipped for multiple consecutive weeks.** | Weekly report data becomes sparse/misleading; "current" mastery decay could make everything look artificially weak if no quizzing occurs at all. | Decay rate is deliberately slow (Section 17.2) and configurable; dashboard should visibly indicate "no recent activity" rather than presenting decayed scores as if they were fresh negative signal. |
| **Single point of failure: one SQLite file, one laptop.** | Total data loss on disk failure without backup. | Local rotating backups (FR-7.1) are mandatory MVP scope, not a future nice-to-have; learner is responsible for pointing the backup folder at an existing personal sync solution if off-machine redundancy is desired. |
| **Solo-maintainer scope creep.** | The richly detailed feature set here could balloon in implementation time for one developer. | MVP Definition (Section 24) exists specifically to sequence this correctly; roadmap phases are ordered to defer anything not required for the core weekly loop to function end-to-end first. |

---

## 23. Open Questions

These remain genuinely open — they don't block starting implementation of the MVP roadmap (Section 25), but should be resolved before the corresponding phase begins:

1. **Exact decay-rate and SM-2 parameter tuning** (Sections 16.6, 17.2) are given sensible defaults in this document but are fundamentally empirical — they should be revisited after a few weeks of real usage data rather than treated as final.
2. **Overall-proficiency blend weighting** (40/60 item-mastery/writing-performance suggested in 17.4) is a starting guess, not a validated formula — worth revisiting once real writing-score history exists.
3. **Exact Ollama hosting arrangement** — "hosted" was specified, but *where* (a rented GPU box, a home server, a cloud Ollama-compatible provider) is not yet decided; this affects latency assumptions and whether "unavailability" (Section 22 risk) is a realistic concern worth extra defensive engineering.
4. **CEFR-style labeling** — whether the dashboard should ever surface a rough CEFR-equivalent label (e.g., "estimated: high B2") alongside the raw proficiency score, given the explicit non-goal of claiming certification equivalence (Section 6). Leaning toward yes-with-heavy-caveats, but not decided.
5. **Retention/cleanup policy for rejected `ApprovalQueue` items and `PARSE_FAILED` notes** — currently "retain forever" by default (consistent with Product Philosophy #3), but no explicit cap is defined; revisit if this becomes a real storage or UI-clutter concern at scale (unlikely at single-user text-data volumes, but worth a stated policy eventually).

---

## 24. Development Roadmap

### Phase 0 — Foundations (no learner-facing value yet)
- FastAPI project scaffold, SQLite schema + migrations, `Config` table, `Generator`/`Evaluator` interface + Ollama adapter (unit-testable against a mocked schema-conformant response).
- Vault Watcher + Ingestion Service skeleton (parsing prompt, schema validation, retry logic) — testable against sample notes without a frontend.

### Phase 1 — Core Ingestion Loop
- Approval Queue Service + minimal frontend approval screen.
- Duplicate detection via FTS5.
- End-to-end: save a real Obsidian note → see it appear for approval → approve → confirm it lands correctly in `LearningItem`.

### Phase 2 — Quiz Loop
- Scheduler (eligibility selection, mastery update logic, Section 16–17).
- Quiz generation for the 4 deterministic-gradable types first (recall, fill-blank, MC, error correction) — defer the 3 LLM-graded types to reduce early complexity.
- Minimal quiz-taking UI.

### Phase 3 — Writing Evaluation
- Mini writing task pipeline (lighter rubric) end-to-end.
- Weekly writing assessment pipeline (full 5-dimension rubric), including topic repetition-avoidance.
- Suggested-items → ApprovalQueue integration.

### Phase 4 — Weekly Review Assembly
- Full weekly pipeline orchestration (adaptive volume handling, Section 19).
- Narrative report generation.
- Weekly Report Archive UI.

### Phase 5 — Remaining Quiz Modes & Dashboard Depth
- Rewrite-naturally, conversation, mini-essay quiz modes (LLM-graded).
- Mastery Breakdown, Progress Trends charts, Item Browser.

### Phase 6 — Operational Hardening
- Backup Service (event-triggered snapshots + rotation).
- AuditLog coverage across failure paths.
- Settings screen for model/backup configuration.

Each phase should be independently usable end-to-end by the learner even if later phases haven't started — Phase 1 alone already delivers real value (structured, searchable knowledge base from notes), and Phase 2 alone already delivers quiz practice, so the roadmap does not require full completion before the tool becomes genuinely useful daily.

---

## 25. MVP Definition

**The MVP is complete when the full Monday–Sunday learner workflow described in the Vision and Section 10 (Flows 1–5) can run end-to-end without manual database intervention:**

- [ ] A note saved in Obsidian is automatically parsed and appears in the approval inbox within seconds.
- [ ] Approving an item makes it immediately eligible for future quizzes.
- [ ] An ad-hoc quiz can be generated and taken across at least the 4 deterministic-gradable modes plus Random.
- [ ] A mini writing task can be submitted and receive lightweight feedback, including at least one suggested-item round-trip through approval.
- [ ] "Start Weekly Review" correctly reflects however many lessons were actually studied that week (including the zero-lessons edge case, Section 19.2).
- [ ] The weekly review produces one combined report containing quiz results, mini-writing summary, and a full 5-dimension weekly writing assessment.
- [ ] The dashboard shows an overall proficiency estimate, category mastery breakdown, and at least one historical trend chart with real data after 2+ weeks of use.
- [ ] Mastery scores visibly decay over time for unpracticed items when read, without any scheduled background job.
- [ ] A local backup snapshot exists after normal use and can be manually restored (tested at least once before declaring MVP done).
- [ ] Swapping `model_name` in config changes which model handles every pipeline, with no code changes required.

Explicitly **not** required for MVP completion (deferred per Section 24 phasing, tracked but not blocking): the 3 LLM-graded quiz modes beyond Random's fallback behavior, full Item Browser search/filter polish, Settings UI beyond raw config editing.

---

## 26. Success Metrics

Since this is a single-user personal system, "success" is defined behaviorally and qualitatively rather than via engagement/growth metrics (which would be meaningless at n=1):

| Metric | Target / Signal |
|---|---|
| **Workflow adherence** | The learner actually completes the Mon–Sat study + Sunday review cycle using Praxis, without reverting to manual tracking, for a sustained multi-week period. |
| **Approval friction** | Approval sessions take under ~2 minutes for a typical daily note's worth of extracted items (a proxy for parser quality — high friction signals the parser is extracting noise). |
| **Data integrity** | Zero unrecoverable data loss events across the system's lifetime (verified by successful backup restores when tested). |
| **Trend visibility** | After 8+ weeks of use, the Progress Trends charts show a directionally sensible pattern (e.g., naturalness score trending upward, or at minimum, not randomly noisy in a way that suggests evaluator unreliability). |
| **Self-reported trust** | The learner subjectively agrees, on reviewing weekly reports, that the feedback matches their own sense of their mistakes and progress — the qualitative bar that matters most for a system whose entire purpose is to be a trustworthy mirror of one person's ability. |
| **Maintenance burden** | The system requires no more than occasional (not weekly) manual intervention (e.g., handling a `PARSE_FAILED` note, restarting a stalled Ollama call) to keep running. |

---

**End of PRD v1.0**

This document is intended to be sufficiently detailed for implementation to begin at Phase 0 (Section 24) without further clarification. Open Questions (Section 23) are flagged explicitly as deferred, not unresolved blockers.
