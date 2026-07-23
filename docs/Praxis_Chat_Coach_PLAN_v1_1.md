# Praxis — Chat Coach Implementation Plan v1.1

## Patch Notes (none → v1.1)

This is the first version of this document. It did not exist before this rewrite: the
previous file that carried this name contained only a product-vision brief (Role /
Context / Product Vision / Tasks), not an implementation plan. No section of this
document — including every "§" reference below — existed anywhere in the repository
prior to this version. It has been authored from scratch, grounded in the current
codebase (`Praxis_Architecture_v1_1.md`, `backend/app/`, `frontend/src/`) and in the
chat-first product vision supplied separately.

Document authority: this plan is subordinate to `Praxis_Architecture_v1_1.md` per
`CLAUDE.md` §2. It does not change any ADR, backend architecture principle, database
engine, LLM adapter, or service-layer boundary defined there. It adds one new backend
domain (`app/chat/`) and restructures the frontend shell. Where this plan is silent,
`Praxis_Architecture_v1_1.md` governs.

---

## 1. Executive Summary

Praxis is being extended with a **Chat Coach**: a conversational surface that becomes
the primary way users interact with the application. Quizzes, writing sessions, and
weekly assessments — which today are standalone pages the user must navigate to — become
tools the coach can invoke inline, mid-conversation, the way ChatGPT or Claude Desktop
invoke a tool without leaving the chat.

This plan covers three epics:

- **Epic 12** — Chat data model, migration, CRUD service, and the first four endpoints.
  No LLM code. Pure persistence layer.
- **Epic 13** — The coach's LLM integration: prompt contract, structured output schemas,
  action routing (quiz / writing / plain reply), and the remaining endpoints.
- **Epic 14** — The frontend rebuild: a two-column app shell (collapsible sidebar +
  content pane), `ChatPage` as the landing route, inline plugin widgets for quiz and
  writing, and removal of the old standalone quiz/writing pages and routes.

The backend architecture (SQLite, FastAPI, SQLModel, synchronous per-request LLM calls,
`Generator`/`Evaluator` protocol over Ollama) is unchanged. This plan only adds new
modules that follow those existing patterns.

---

## 2. Product Scope: Chat-First

### 2.1 What "chat-first" means concretely

- The application's root route (`/`) renders `ChatPage`, not `DashboardPage`. Opening
  Praxis for the first time (or any time, with no active thread) lands the user in a
  ready-to-type new-chat composer — never a dashboard, never a page the user must
  click through to start talking to the coach.
- Dashboard, Reports, Settings, and Approvals remain, but they are **secondary,
  standalone pages** reached only via explicit sidebar navigation. None of them may
  become a required step before chatting.
- Quiz sessions, writing sessions, and weekly assessments are **not** independent pages
  the user navigates to. They are **actions the coach can trigger**, rendered as inline
  widgets inside the chat transcript. The user completes them without leaving the chat
  route.

### 2.2 What does NOT change

- Backend architecture, ADRs, database engine, domain model for notes / learning items /
  approvals / quizzes / writing / reports (`Praxis_Architecture_v1_1.md` §3–§11) are
  unchanged. This plan is additive.
- Existing quiz/writing **grading logic** (`QuizService`, `WritingService`, the
  `Generator`/`Evaluator` protocol, prompt contracts in `app/llm/prompts/`) is reused
  as-is. The Chat Coach calls into these services; it does not reimplement them.
- Approval workflow (ADR-05) is untouched.

---

## 3. Data Model & Persistence

New domain: `backend/app/chat/`, following the same package shape as
`backend/app/quizzes/` and `backend/app/writing/` (`__init__.py`, `router.py`,
`service.py`). New SQLModel tables live in `backend/app/db/models/chat.py`, following the
conventions in `app/db/models/quiz.py` (typed enums, `created_at`/`updated_at`, integer
PKs, cross-cutting conventions in Architecture §7.1).

### 3.1 New tables

**`ChatThread`**

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | autoincrement |
| `title` | `str \| None` | nullable until first assistant reply names it (§4.2) |
| `created_at` | `datetime` | |
| `updated_at` | `datetime` | bumped on every new message |
| `last_message_preview` | `str \| None` | first ~120 chars of the latest message, denormalized for sidebar/history list rendering without a join |

**`ChatMessage`**

| Column | Type | Notes |
|---|---|---|
| `id` | `int` PK | |
| `thread_id` | `int` FK → `ChatThread.id`, indexed | |
| `role` | `enum ChatRole` | `USER`, `ASSISTANT`, `SYSTEM` |
| `content` | `str` | plain text (markdown-safe); never contains embedded widget state |
| `action_type` | `enum ChatActionType \| None` | `NONE` (default), `QUIZ`, `WRITING`. Set when this assistant message triggered an inline plugin. |
| `action_ref_id` | `int \| None` | FK-by-convention (not a DB FK, since it points to different tables depending on `action_type`) to `QuizSession.id` or `WritingSubmission.id` |
| `created_at` | `datetime` | indexed for ordering |

`ChatActionType` and `ChatRole` are plain `str` enums in `app/db/models/chat.py`,
mirroring `QuizMode`/`QuizScope` style in `app/db/models/quiz.py`.

No new table is needed to represent "quiz-in-progress" or "writing-in-progress" state —
that state already lives in `QuizSession`/`WritingSubmission` (existing tables). A
`ChatMessage` with `action_type != NONE` is a pointer into that existing state, not a
duplicate of it. This keeps the chat domain a thin coordination layer, consistent with
Architecture ADR-01 (SQLite as sole datastore, no duplicated state) and ADR-02
(SQLModel).

### 3.2 Migration

One Alembic migration, `backend/app/db/migrations/versions/<rev>_add_chat_tables.py`,
creating `chat_thread` and `chat_message` only. It must:

- apply cleanly on top of head (`alembic upgrade head`)
- reverse cleanly (`alembic downgrade -1`)
- not touch any existing table (no column additions to `quiz_session` or
  `writing_submission` — the coordination is done by ID reference from `chat_message`,
  not by adding a `thread_id` to the target tables, so existing quiz/writing code paths
  used outside chat remain untouched)

### 3.3 Service — CRUD layer (Epic 12 scope)

`ChatService` in `backend/app/chat/service.py`, static/class methods, matching the style
of `QuizService`:

- `create_thread() -> ChatThread` — creates an empty thread, `title=None`.
- `list_threads(limit: int = 50, offset: int = 0) -> list[ChatThread]` — ordered by
  `updated_at` desc, for the sidebar "Chat History" list.
- `get_thread(thread_id: int) -> ChatThread` — raises `ValueError` if not found (matches
  existing `QuizService.get_session_with_questions` not-found convention → router maps
  to 404).
- `list_messages(thread_id: int) -> list[ChatMessage]` — ordered by `created_at` asc.
- `append_message(thread_id: int, role: ChatRole, content: str, action_type: ChatActionType = ChatActionType.NONE, action_ref_id: int | None = None) -> ChatMessage`
  — also updates `ChatThread.updated_at` and `last_message_preview`.
- `delete_thread(thread_id: int) -> None` — cascades to messages.

These six methods are the **only** service methods in scope for Epic 12. Everything
LLM-related (below) is Epic 13.

### 3.4 API — first four endpoints (Epic 12 scope)

Router: `backend/app/chat/router.py`, `APIRouter(prefix="/api/chat", tags=["chat"])`,
registered in `main.py` alongside the other routers (after `approvals_router`,
alphabetically consistent with the existing block).

1. `POST /api/chat/threads` → creates a thread, returns `ChatThreadResponse`.
2. `GET /api/chat/threads` → returns `list[ChatThreadResponse]` (id, title,
   `last_message_preview`, `updated_at`) for the sidebar history list.
3. `GET /api/chat/threads/{thread_id}` → returns `ChatThreadDetailResponse` (thread +
   `list[ChatMessageResponse]`), 404 if missing.
4. `DELETE /api/chat/threads/{thread_id}` → deletes, 204 on success, 404 if missing.

No `POST /api/chat/threads/{thread_id}/messages` endpoint yet — that endpoint is where
the LLM lives, and is explicitly Epic 13 scope (§4.3). Epic 12 ships a fully working,
tested persistence layer with an empty inbox: threads can be created, listed, and
fetched, but nothing populates them with assistant replies yet.

---

## 4. Backend — Coach LLM Integration & Action Routing (Epic 13 scope)

### 4.1 Task type, prompt contract, schemas

**Task type.** Add `COACH_CHAT = "coach_chat"` to `TaskType` in `app/llm/interface.py`,
added to `GENERATION_TASKS` (it is a generation task: the coach produces new content, not
a grade).

**Prompt.** New file `app/llm/prompts/coach.py`, following the shape of
`app/llm/prompts/quiz.py`. The prompt receives:

- the last N messages of the thread (N = 20, truncate oldest first; matches a
  conversational-context window without unbounded growth — if this needs to be larger
  for real usage, that is a follow-up decision, not something to invent in this epic)
- a compact summary of the learner's current state usable for grounding suggestions:
  most recent weekly report narrative (if any) and count of items due for review
  (reusing existing `LearningItem` mastery-decay read path, Architecture §2 ADR-04) —
  read-only, no new computation.

**Output schema** — `CoachReply` in `app/llm/schemas.py`:

```python
class CoachAction(BaseModel):
    """A structured intent to launch a plugin, or none."""

    action: Literal["NONE", "START_QUIZ", "START_WRITING"]
    quiz_mode: QuizMode | None = None       # required if action == START_QUIZ
    quiz_size: int | None = None            # required if action == START_QUIZ, default 10 applied in service if absent
    writing_topic: str | None = None        # required if action == START_WRITING


class CoachReply(BaseModel):
    """Output schema for the coach_chat task."""

    reply_text: str = Field(description="the assistant's conversational reply, always present")
    action: CoachAction
    suggested_thread_title: str | None = Field(
        default=None,
        description="only populated on the first assistant reply in a thread; 3-6 words",
    )
```

The model always returns `reply_text` even when it also returns an action — e.g. "Let's
do a quick fill-in-the-blank round on phrasal verbs" alongside
`action.action = "START_QUIZ"`. The frontend renders `reply_text` as a normal chat
bubble, then renders the inline widget beneath it if `action.action != "NONE"`.

### 4.2 Service methods (remaining, on top of §3.3)

All in `ChatService` unless noted:

- `generate_reply(thread_id: int) -> ChatMessage` — the core orchestration method:
  1. Loads thread history via `list_messages`.
  2. Calls `Generator.generate(task=TaskType.COACH_CHAT, context=..., output_schema=CoachReply)`.
  3. Persists the assistant's `reply_text` as a `ChatMessage` via `append_message`.
  4. If `suggested_thread_title` is present and `ChatThread.title` is still `None`, sets
     it.
  5. If `action.action == "START_QUIZ"`, calls `start_quiz_action` (below); if
     `"START_WRITING"`, calls `start_writing_action`; if `"NONE"`, does nothing further.
  6. Returns the persisted assistant `ChatMessage` (with `action_type`/`action_ref_id`
     populated if a plugin was launched).
- `start_quiz_action(thread_id: int, mode: QuizMode, size: int) -> ChatMessage` — calls
  the **existing, unmodified** `QuizService.start_session` (no new quiz logic), then
  appends a `ChatMessage` with `role=ASSISTANT`, `action_type=QUIZ`,
  `action_ref_id=session.id`. Content is a short deterministic string (e.g. "Quiz
  started.") — the actual questions render from the widget's own fetch of
  `GET /api/quizzes/{session_id}`, not from chat message content, avoiding duplicated
  state.
- `start_writing_action(thread_id: int, topic: str) -> ChatMessage` — same pattern,
  calling the existing `WritingService` entry point, `action_type=WRITING`.
- `on_quiz_graded(thread_id: int, session_id: int) -> ChatMessage` — called after the
  user submits quiz answers (triggered from the router endpoint in §4.3, not from inside
  `QuizService`, to avoid coupling the quiz domain to chat). Fetches the graded session
  summary, calls the LLM once more with a short "the user just finished this quiz,
  continue the conversation naturally" context, persists the follow-up assistant
  message. This is what makes the conversation "continue naturally after completion"
  per the product vision — it is not automatic; it requires this explicit call.
- `on_writing_graded(thread_id: int, submission_id: int) -> ChatMessage` — same pattern
  for writing.

**Explicit non-goal for this epic:** the coach does not autonomously decide to grade or
re-invoke itself on a timer. Every LLM call in this service happens synchronously inside
a request/response cycle, consistent with ADR-08 (no background job queue for
user-triggered LLM calls). "Automatic triggering from conversation" (per the plugin
philosophy) means the coach's *own reply* can contain an action — not that a background
process pokes the thread.

### 4.3 API — remaining endpoints

5. `POST /api/chat/threads/{thread_id}/messages` — body: `{ content: str }`. Appends the
   user message (`role=USER`), then calls `generate_reply`. Returns both the persisted
   user message and the assistant's reply as `ChatMessageResponse[]` (length 2). This is
   the single endpoint the composer calls on submit.
6. `POST /api/chat/threads/{thread_id}/quiz/{session_id}/complete` — called by the
   frontend the moment the inline quiz widget receives its graded summary from the
   existing `POST /api/quizzes/{session_id}/answers` call. Triggers `on_quiz_graded`.
   Returns the new assistant `ChatMessageResponse`.
7. `POST /api/chat/threads/{thread_id}/writing/{submission_id}/complete` — same pattern
   for writing, triggers `on_writing_graded`.

Note the deliberate separation: the frontend still calls the **existing** quiz/writing
grading endpoints directly (no change to `app/quizzes/router.py` or
`app/writing/router.py`), then separately notifies chat that grading finished. This
keeps quiz/writing domains ignorant of chat's existence, preserving the existing service
layer boundary (CLAUDE.md §5 — API contract changes for quiz/writing are out of scope
for this plan entirely).

### 4.4 Error handling

Follows the existing pattern in `app/quizzes/router.py`: `ValueError` → 404,
unexpected exceptions → logged + 500 with a generic detail message. If the LLM call in
`generate_reply` fails after the adapter's internal retries (Architecture §11 governs
retry policy — unchanged), the endpoint returns 500 and the frontend shows a retry
affordance on that message (§5.3.4) rather than a partially-persisted state; the user
message itself is still persisted so the user does not lose their input.

---

## 5. Frontend — Chat-First App Shell (Epic 14 scope)

### 5.1 Routing

`frontend/src/App.tsx` is restructured:

- `/` → `ChatPage` (new thread composer, no `thread_id`)
- `/chat/:threadId` → `ChatPage` (existing thread, loads history)
- `/dashboard` → `DashboardPage` (moved off `/`)
- `/approvals` → `ApprovalsPage` (unchanged)
- `/reports` → `ReportsPage` (unchanged)
- `/settings` → `SettingsPage` (unchanged)
- `/quizzes`, `/writing` routes and `QuizPage.tsx`, `WritingPage.tsx` files are
  **deleted**. This plan explicitly authorizes their removal — the functionality is not
  lost, it moves inline (§5.4). Do not keep them "just in case" or leave dead routes.

### 5.2 App shell layout

Two-column layout, replacing the current single top-nav bar (`App.tsx` today):

- **Left column — sidebar.** Fixed-width when expanded (~260px), collapses to an
  icon-only rail (~64px) via a toggle. State persists across navigation (React state at
  the `App` level, not per-page) but does not need to persist across browser sessions
  in this epic — that is a nice-to-have, not required.
- **Right column — content pane.** Renders the routed page. On `ChatPage`, this pane
  itself has no additional chrome (no page title bar, no breadcrumb) — the composer and
  transcript fill it, matching Claude Desktop's chat pane, not a dashboard content area.

Sidebar link order (top to bottom), matching the product vision's priority list exactly:

1. **New Chat** — button, not a nav link to a page; always navigates to `/` and clears
   any active thread state in `ChatPage`.
2. **Dashboard**
3. **Reports**
4. **Search** — a search input/affordance over chat history (client-side filter over
   `list_threads` results by title/preview is sufficient for this epic; full-text search
   over message content is a non-goal here — Architecture's existing FTS5 table, §7.3,
   is for notes, not chat, and extending it is out of scope for this plan).
5. **Chat History** — scrollable list of threads (title, relative timestamp), each item
   navigates to `/chat/:threadId`. Sourced from `GET /api/chat/threads`.
6. **Settings**

Approvals is not in this list because it is not part of the vision doc's priority order;
it keeps its existing route and gets a place in the sidebar below Settings, or folded
under Settings if the implementer judges that cleaner — this single placement decision
is left to implementation discretion (CLAUDE.md §5, "naming and organization"), but the
six items above must appear in the stated order.

### 5.3 `ChatPage` behavior

#### 5.3.1 Empty / new-chat state

When there is no `threadId` (`/`): render the composer centered or anchored at the
bottom of an otherwise empty transcript area with a short static prompt (e.g. "Ask
anything, or try a quiz"). No API call is made yet — a `ChatThread` is only created on
first submit (`POST /api/chat/threads`, then immediately
`POST /api/chat/threads/{id}/messages`), not eagerly on page load. This avoids littering
`list_threads` with empty abandoned threads every time a user opens the app.

#### 5.3.2 Existing-thread state

When `threadId` is present: `GET /api/chat/threads/{threadId}` on mount, render the full
message history in order, scroll to bottom. If the thread has an in-progress plugin as
its last assistant message (`action_type != NONE` and no corresponding `.../complete`
call has happened yet), rehydrate the inline widget from the existing quiz/writing
session data (`GET /api/quizzes/{id}` / equivalent writing fetch) so a page refresh
mid-quiz does not lose progress.

#### 5.3.3 Sending a message

Composer submit → optimistically render the user bubble immediately → call
`POST /api/chat/threads/{threadId}/messages` (creating the thread first if this is the
first message from `/`) → on response, replace the optimistic bubble with the persisted
one and append the assistant reply. Show a loading indicator (typing dots, matching
Claude Desktop's pattern) in the assistant's position while the request is in flight.

#### 5.3.4 Failure state

If the send request fails: keep the user's message visible (marked as failed, not
silently dropped), show an inline retry button on that message. Do not clear the
composer input on failure.

#### 5.3.5 Conversation persistence

Every user and assistant message is persisted immediately server-side (§3.4/§4.3) —
there is no local-only draft state beyond the composer's current unsent input. Refreshing
the page or navigating away and back must reproduce the exact transcript from the
server, not from local state.

### 5.4 Plugin integration (inline widgets)

**`PluginMenu`** — an affordance in the composer (e.g. a "+" or attachment-style icon,
matching the visual weight of Claude Desktop's composer tools, not a bulky toolbar) that
opens a small picker with exactly two direct-action items: **Quiz** and **Writing**.
Selecting one calls the existing action endpoints directly —
`POST /api/actions/start-quiz` / `POST /api/actions/start-writing` if those exist as
plain REST actions today, or, if no such endpoints currently exist outside the chat
domain, the manual-trigger path goes through `ChatService.start_quiz_action` /
`start_writing_action` (§4.2) via a small dedicated router endpoint
(`POST /api/chat/threads/{thread_id}/quiz/manual`,
`POST /api/chat/threads/{thread_id}/writing/manual`) — **no LLM call** for the manual
path, matching the execution prompt's explicit instruction that `PluginMenu` actions
call quiz/writing directly with no LLM involved. Confirm which of these two paths
matches the current `backend/app/*/router.py` reality before implementing Epic 14; do
not assume — inspect the repo at implementation time, since routers may have changed
between this plan's authoring and Epic 14 starting.

**`InlineQuizWidget`** — reuses `QuestionCard`, `SessionSummary` from
`frontend/src/features/quizzes/components/` (do not duplicate this UI). Renders inside
the chat transcript at the position of the assistant message that has
`action_type=QUIZ`. On completion (all questions graded), calls
`POST /api/chat/threads/{threadId}/quiz/{sessionId}/complete` (§4.3) so the coach can
continue the conversation, then the assistant's follow-up message appends normally below
the widget.

**`InlineWritingWidget`** — same pattern, reusing `WritingEditor`,
`EvaluationFeedback`, `WritingPromptCard` from `frontend/src/features/writing/components/`,
calling `.../writing/{submissionId}/complete` on completion.

Both widgets render at a width consistent with the chat transcript's message width (not
full-bleed page width) — they are chat content, not embedded pages.

### 5.5 Loading & empty states — summary table

| Situation | Required behavior |
|---|---|
| App loads at `/`, no threads exist yet | Empty composer, static prompt, no spinner (nothing to fetch) |
| App loads at `/`, threads exist | Same as above — `/` never auto-redirects into an existing thread |
| Navigating to `/chat/:id` | Skeleton/loading state for the transcript area while `GET .../threads/:id` resolves |
| Sidebar "Chat History" | Skeleton list items while `GET /api/chat/threads` resolves; empty state ("No conversations yet") if the list is empty |
| Sending a message | Typing-indicator in assistant position; composer stays enabled but submit is disabled until response or failure |
| Inline widget loading its own data (e.g. quiz questions) | Widget owns its own loading state, independent of the outer chat loading state |

### 5.6 Responsive / mobile behavior

- Below a defined breakpoint (implementer may use the project's existing Tailwind
  breakpoints — do not introduce a new breakpoint system), the sidebar defaults to fully
  collapsed/hidden behind a hamburger toggle, overlaying the content pane rather than
  pushing it, so the chat transcript keeps full width on small screens.
- The composer remains fixed to the bottom of the viewport on mobile (standard chat-app
  behavior), transcript scrolls independently above it.
- Inline widgets must remain usable at mobile widths — reuse whatever responsive
  behavior `QuestionCard`/`WritingEditor` already have; do not redesign them for this
  epic beyond fitting the transcript's width constraint.

### 5.7 Visual design constraints

- Follow Claude Desktop's visual language for: layout proportions, sidebar width and
  collapse behavior, message bubble spacing, composer shape, typography scale, and
  transition/animation timing (subtle, fast — no bouncy or elaborate transitions).
- Preserve Praxis's existing brand tokens already in the codebase (serif logotype,
  `bg-cream`/`text-ink` color tokens visible in current `App.tsx` — do not replace these
  with generic Claude brand colors; match Claude's *structure and spacing*, not its
  literal palette, per the vision doc's "preserve Praxis branding" constraint).
- Do not invent new design tokens ad hoc — extend the existing Tailwind theme
  configuration if new tokens are genuinely needed, and note any such addition in the
  Epic 14 patch description so it's reviewable.

### 5.8 API client additions

`frontend/src/features/chat/api/chat.ts` — new file, TanStack Query hooks
(`useThreads`, `useThread`, `useSendMessage`, `useCompleteQuiz`, `useCompleteWriting`,
`useCreateThread`, `useDeleteThread`), following the existing hook patterns in
`frontend/src/features/quizzes/hooks/index.ts`. Add corresponding response types to
`frontend/src/api/types.ts` (`ChatThread`, `ChatMessage`, `ChatActionType`) — do not
create a parallel type system; extend the existing shared `types.ts`.

---

## 6. Epics

### 6.1 Epic 12 — Chat Data Model & Persistence

**In scope:** §3 in full (tables, migration, `ChatService` CRUD methods, first four
endpoints). No LLM code — `generate_reply` and everything in §4 does not exist yet after
this epic. Router is registered in `main.py`.

**Acceptance criteria:**
- `alembic upgrade head` / `downgrade -1` / `upgrade head` all succeed cleanly.
- All six `ChatService` methods in §3.3 exist, are unit-tested, and match those
  signatures.
- The four endpoints in §3.4 exist, are covered by tests (create → list → get → delete),
  and return the specified status codes on the not-found paths.
- No file under `app/quizzes/`, `app/writing/`, or any existing router is modified.
- Full existing test suite still passes.

### 6.2 Epic 13 — Coach LLM Integration & Action Routing

**In scope:** §4 in full — `TaskType.COACH_CHAT`, `app/llm/prompts/coach.py`,
`CoachAction`/`CoachReply` schemas, all five `ChatService` methods in §4.2, the three
remaining endpoints in §4.3.

**Acceptance criteria:**
- `generate_reply` persists both the triggering user message (already persisted by the
  endpoint before calling it) and the assistant reply, and correctly sets
  `action_type`/`action_ref_id` when an action is present.
- Starting a quiz or writing session via the coach uses the existing
  `QuizService`/`WritingService` entry points unmodified — no duplicated quiz/writing
  generation logic inside `app/chat/`.
- `on_quiz_graded`/`on_writing_graded` produce a follow-up assistant message referencing
  the just-completed session.
- Full existing test suite (including Epic 12's tests) still passes.

### 6.3 Epic 14 — Chat Frontend (App Shell + Chat UI + Inline Widgets)

**In scope:** §5 in full. Subtasks, in required order:

- **14.1** — Sidebar shell component (expand/collapse, six nav items in specified order,
  responsive collapse behavior per §5.6).
- **14.2** — Routing rewrite in `App.tsx` per §5.1 (including deletion of
  `QuizPage.tsx`/`WritingPage.tsx` and their routes).
- **14.3** — `ChatPage` empty state (§5.3.1) + thread creation on first send.
- **14.4** — `ChatPage` existing-thread state (§5.3.2), history load, scroll-to-bottom.
- **14.5** — Composer: send flow, optimistic UI, loading indicator, failure/retry state
  (§5.3.3–5.3.4).
- **14.6** — `frontend/src/features/chat/api/chat.ts` + `api/types.ts` additions (§5.8) —
  should land before or alongside 14.3, since 14.3–14.5 depend on it; sequencing within
  14.3–14.6 is implementer's call as long as all four are done before 14.7.
- **14.7** — `PluginMenu` + manual quiz/writing trigger (§5.4, first two paragraphs).
- **14.8** — `InlineQuizWidget` + `InlineWritingWidget`, reusing existing components,
  wired to the `.../complete` endpoints (§5.4, remaining paragraphs).
- **14.9** — Sidebar "Chat History" list + "Search" affordance (§5.2 items 4–5), wired to
  `useThreads`.

**Acceptance criteria:**
- `npx tsc --noEmit` — zero errors.
- `npm run test` — all tests pass.
- `python -m pytest tests/ -v` (backend, unaffected by this epic but must still pass —
  confirms no accidental backend breakage from any router registration changes).
- `/` renders `ChatPage` with an empty composer, not `DashboardPage`.
- `QuizPage.tsx`, `WritingPage.tsx`, and their routes no longer exist in the codebase.
- A full manual walkthrough is possible: open app → land in new chat → send a message →
  receive a reply → coach triggers a quiz inline → complete it → coach continues the
  conversation → navigate to Dashboard via sidebar → navigate back to the same thread via
  Chat History → transcript and completed quiz state are intact.

---

## 7. Non-Goals (explicit, to reduce implementer guessing)

- No streaming token-by-token responses in this plan (synchronous request/response per
  ADR-08). Streaming is a plausible future enhancement, not part of Epics 12–14.
- No multi-user support, no auth changes.
- No full-text search over message content (only client-side filter over thread
  title/preview, §5.2 item 4).
- No persistence of sidebar collapsed/expanded state across sessions.
- No changes to the Approval workflow, its ADR, or its UI beyond a possible sidebar
  placement decision (§5.2).
- No new background jobs, cron, or scheduler usage (ADR-03, ADR-08 remain in force).
