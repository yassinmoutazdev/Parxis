# Praxis: Quiz Consolidation + CEFR Proficiency System — Implementation Plan

Status: agreed in discussion, ready for implementation.
Scope: two related but separable changes. Can be shipped as two PRs/sessions.
Note: this plan is written for direct execution by a coding agent
(nemotron-3-ultra, run via the Claude Code harness). All previously-open
design points have been decided here rather than deferred to the
executor — if something in this doc reads as ambiguous, treat it as an
oversight worth flagging, not an invitation to improvise a different
architecture.

---

## Part A — Quiz consolidation (multiple-choice only)

### A.1 Rationale (for the record)
- `QuizMode` currently has 6 values (RECALL, FILL_BLANK, MULTIPLE_CHOICE,
  ERROR_CORRECTION, REWRITE_NATURALLY, RANDOM). Only 3 are even reachable
  from the chat coach tool schema today.
- The weekly quiz path (`reports/router.py::start_weekly_quiz`) has a bug:
  it passes `mode=QuizScope.WEEKLY_REVIEW` into a parameter typed as
  `QuizMode`. `_mode_to_task()` doesn't recognize it and silently falls
  back to `TaskType.QUIZ_RECALL` for every question. This is being fixed
  as part of this change, not separately.
- Decision: quiz becomes MULTIPLE_CHOICE only. The model's creative
  latitude moves from "what format" to "what to test and how to build
  distractors that probe natural usage" (register, collocation, tense,
  word choice — not just recall of definitions).
- Weekly quiz and ad-hoc quiz become the **same mechanism**. The only
  difference is retrieval scope: weekly biases toward items
  studied/reviewed in the last 7 days and uses a larger size. No separate
  question-generation or grading path for "weekly."
- Weekly quiz and weekly writing stay as **two independent due-items**
  under the same `week_id`, not a merged session. `WeeklyReport` already
  has separate `quiz_summary_json` / `weekly_writing_evaluation_id`
  fields — it remains the aggregation point, one level up from the task.

### A.2 Data model changes
- `backend/app/db/models/quiz.py`:
  - Collapse `QuizMode` to a single value. Recommend keeping the enum
    (rather than deleting the column) for schema/history stability, but
    reduce it to `MULTIPLE_CHOICE` only. Existing rows with other mode
    values are historical data — leave them as-is, don't backfill.
  - **`quiz_mode: QuizMode = Field(default=QuizMode.RECALL, index=True)`
    — the default must change to `QuizMode.MULTIPLE_CHOICE`.** This was
    missed in the first draft of this plan; called out explicitly so it
    isn't left pointing at a mode that no longer exists.
  - Add a migration (Alembic) noting the mode restriction. No column
    drop required — SQLite/SQLModel enum validation happens at the ORM
    layer, so old rows won't be re-validated on read.

### A.3 Backend changes
- `backend/app/quizzes/service.py`:
  - Remove `_select_random_mode`, `DETERMINISTIC_GRADING_MODES` /
    `LLM_GRADING_MODES` split (everything is deterministic now — MC
    grading is exact-match against `correct_answer`/`options_json`).
  - Simplify `_generate_question` to drop the `session_mode == RANDOM`
    branch entirely; always resolve to `QuizMode.MULTIPLE_CHOICE`.
  - Simplify `_mode_to_task` to a single mapping
    (`MULTIPLE_CHOICE -> TaskType.QUIZ_MULTIPLE_CHOICE`); remove the
    dict-based fallback-to-RECALL behavior that caused the weekly bug.
  - `start_session()`: remove the `mode` parameter from the public
    signature entirely (decided — not left as "keep or remove"). Callers
    pass only `size`, `scope`, and `week_id`.
- `backend/app/llm/interface.py`: remove `QUIZ_RECALL`, `QUIZ_FILL_BLANK`,
  `QUIZ_ERROR_CORRECTION`, `QUIZ_REWRITE_NATURALLY`, `QUIZ_RANDOM` from
  `TaskType`. Keep `QUIZ_MULTIPLE_CHOICE`.
- `backend/app/llm/prompts/quiz.py`: delete
  `QUIZ_FILL_BLANK_PROMPT`/version and any other removed-mode prompts.
  Rewrite `QUIZ_MULTIPLE_CHOICE_PROMPT` (see Appendix A-1 draft below) to
  explicitly instruct the model to build distractors that test natural
  usage, not just factual recall — this is where the "creative freedom"
  moves to.
- `backend/app/llm/tools.py` (`START_QUIZ_TOOL`): remove the `quiz_mode`
  parameter entirely (no enum, nothing for the model to choose format-wise).
  Keep `quiz_size`. Update the tool description if needed.
- `backend/app/chat/service.py`: remove the `quiz_mode_str` /
  `QuizMode(quiz_mode_str)` parsing block in `handle_turn` (or wherever
  `start_quiz` tool results are handled) — always call
  `start_quiz_action(thread_id, size)` without a mode argument.
- `backend/app/quizzes/router.py`: drop/ignore `mode` from the
  `StartQuizRequest` (or keep the field for backward compatibility but
  ignore its value server-side, documented as deprecated).
- `backend/app/reports/router.py` (`start_weekly_quiz`): fix the bug —
  call `QuizService.start_session(size=<weekly_size>, scope=QuizScope.WEEKLY_REVIEW, week_id=<id>)`
  with no `mode` argument (or `MULTIPLE_CHOICE` if the param survives).
- `backend/app/retrieval/service.py` (`select_eligible_items`): add a
  scope-aware selection path. Proposed signature:
  `select_eligible_items(size: int, since: date | None = None)` — when
  `since` is provided (weekly path passes `week_start`), bias/filter
  toward `LearningItem`s created or last-reviewed within that window
  before falling back to the normal due/weak-item pool if there aren't
  enough. Weekly default size: **15** (decided; ad-hoc keeps its
  existing default, ~10).

### A.4 Frontend changes
- Locate and simplify any quiz-mode-conditional rendering in the quiz
  widget components (free-text input for RECALL/FILL_BLANK/
  ERROR_CORRECTION/REWRITE_NATURALLY vs. option buttons for MC) down to
  the single MC rendering path. This should *shrink* the quiz component
  code meaningfully.
- Remove any mode-selection UI if one exists (e.g. a picker before
  starting a manual quiz).
- No change needed to how weekly quiz is surfaced as a due-item — same
  component, just always MC now.

### A.5 Explicitly out of scope for this change
- Writing tasks (mini and weekly) stay free-text, unchanged in
  interaction model. Only the quiz feature is being collapsed to MC.

### A.6 Cleanup checklist (do not skip — this is dead-code-prevention, not optional polish)
- **`GRADE_QUIZ_ANSWER` is now entirely dead** and must be removed, not
  just its callers: `TaskType.GRADE_QUIZ_ANSWER` (`llm/interface.py`),
  `_GRADE_QUIZ_ANSWER_PROMPT` and its registry entry
  (`llm/prompts/__init__.py`), its `inference_settings.py` entry, its
  branch in `llm/validation.py` (`elif task == "grade_quiz_answer"`),
  and the call site + surrounding `DETERMINISTIC_GRADING_MODES` branch
  logic in `quizzes/service.py` (~lines 275, 388-395). This was the
  LLM-graded fallback for free-text modes; with MC-only there is no
  caller left.
- **`llm/prompts/__init__.py`'s task→prompt registry dict** currently
  has explicit entries for `QUIZ_RECALL`, `QUIZ_FILL_BLANK`,
  `QUIZ_ERROR_CORRECTION`, `QUIZ_REWRITE_NATURALLY` — remove these
  entries in the same commit as removing the `TaskType` members, or the
  module will reference `TaskType` attributes that no longer exist and
  fail on import.
- **Frontend files with mode-specific logic to simplify/remove** (found
  by direct grep, not exhaustive-by-guess):
  `features/quizzes/components/QuestionCard.tsx`,
  `features/quizzes/components/SessionSummary.tsx`,
  `features/quizzes/components/QuizRunner.tsx`,
  `features/quizzes/components/QuizModeSelector.tsx` (delete this
  component entirely — it's a mode picker with nothing left to pick),
  `features/quizzes/QuizPage.tsx`, `features/quizzes/hooks/index.ts`,
  `features/chat/ChatPage.tsx`, `features/chat/components/ComposerPlusMenu.tsx`,
  `api/types.ts` (drop the mode union type / narrow it to a single
  literal).
- **`backend/tests/integration/test_quiz_service.py` needs a real
  rewrite, not incidental patching.** It has ~20 references to removed
  modes, including tests that assert `RANDOM` resolves to one of the
  concrete modes and fixtures instantiating sessions with
  `QuizMode.RECALL`. Delete tests that test now-nonexistent behavior;
  don't leave them patched-to-pass against dead code paths.
- Grep sweep before considering Part A done: `grep -rn "QuizMode\."` and
  `grep -rn "QUIZ_RECALL\|QUIZ_FILL_BLANK\|QUIZ_ERROR_CORRECTION\|QUIZ_REWRITE_NATURALLY\|QUIZ_RANDOM\|grade_quiz_answer"`
  across `backend/app` and `frontend/src` should return nothing outside
  of historical-data comments/migrations.

---

## Part B — CEFR-anchored writing evaluation + overall proficiency

### B.1 Rationale (for the record)
- Grading calls already run at `temperature=0` — sampling noise isn't
  the reliability problem. The problem is the rubric itself: "Overall
  (0-100): general quality assessment" gives the model no fixed external
  anchor, so equivalent essays can land far apart for no principled
  reason.
- Fix: anchor the **weekly** writing evaluation to real CEFR "can-do"
  descriptors and force a discrete band decision (A2/B1/B2/C1/C2) with a
  short justification, instead of free-floating 0-100 "overall."
  Sub-scores (grammar/vocabulary/coherence/naturalness, still 0-100)
  remain as diagnostic detail *supporting* the band call, not
  independently blended into a derived number.
- Mini writing evaluation (chat-triggered, quick) stays exactly as it is
  today — corrections + naturalness notes, no CEFR banding. It already
  does not feed the dashboard's `proficiency` calculation
  (`_calculate_writing_performance_avg` only queries weekly
  `WritingEvaluation` rows) — this stays true, no change needed there.
- New: a top-level **CEFR band** becomes the headline proficiency
  metric, computed from the last N weekly writing evals (primary
  signal) with quiz performance only nudging within a narrow range
  (secondary/confirming signal, not independently pulling the level).
  Item-level `mastery_score` is untouched — it answers a different
  question ("did you retain this specific thing") and keeps its current
  role in the category-mastery view.
- **Hysteresis**: the displayed CEFR band only changes after multiple
  consecutive weekly evals support the new band — not on a single
  eval. This is the actual mechanism that makes the feature feel
  "reliable and stable," not a claim that any single grading call is
  perfect.

### B.2 Data model changes
- `backend/app/db/models/writing.py` (`WritingEvaluation`): add
  `cefr_band: str | None` (e.g. "B2") and `cefr_justification: str | None`
  columns. Populate only for weekly evals (leave `None` for mini).
- **Decision: no new table for hysteresis state.** The current/confirmed
  CEFR band is computed on read, not stored as mutable state. Rationale:
  a stored counter (`consecutive_support_count`) is state that can
  desync from the data it's supposed to summarize (e.g. after a manual
  data fix, backfill, or bug); a value derived fresh from
  `WritingEvaluation.cefr_band` history every time is always correct by
  construction and trivially testable/replayable. The dashboard query
  volume here is small (a handful of weekly rows), so recomputation cost
  is a non-issue.

### B.3 Backend changes
- `backend/app/llm/prompts/writing_eval.py`:
  - Rewrite `WEEKLY_WRITING_EVAL_RUBRIC` to embed condensed CEFR writing
    descriptors (A2 through C2) and require the model to select one band
    and justify it against the descriptor text, not invent its own scale.
    See Appendix B-1 draft below.
  - Update `WEEKLY_WRITING_EVAL_PROMPT`'s JSON schema to include
    `"cefr_band"` and `"band_justification"` alongside the existing
    dimension scores.
  - `MINI_WRITING_EVAL_PROMPT`/`RUBRIC`: unchanged.
- `backend/app/llm/schemas.py` (`WeeklyWritingEvalOutput`): add
  `cefr_band: Literal["A1","A2","B1","B2","C1","C2"]` and
  `band_justification: str` fields; update validation
  (`llm/validation.py`) accordingly.
- New service, e.g. `backend/app/proficiency/service.py`
  (`ProficiencyService`):
  - `get_current_band() -> dict`: the single entry point. Implementation:
    1. Query `WritingEvaluation` rows with a non-null `cefr_band`,
       joined to `WeeklyReport`, ordered chronologically by
       `week_start` ascending. Define a fixed band ordering
       `["A1","A2","B1","B2","C1","C2"]` (used only for the "trend"
       direction, not for the confirmation logic itself).
    2. Run this exact algorithm (deterministic, replay-from-history,
       no stored counters) to get `computed_band`:
       ```python
       def compute_band(evals: list[str], threshold: int = 2) -> str | None:
           """evals: cefr_band values in chronological (oldest-first) order."""
           if not evals:
               return None
           band = evals[0]
           i = 1
           while i < len(evals):
               window = evals[i:i + threshold]
               if (
                   len(window) == threshold
                   and all(w == window[0] for w in window)
                   and window[0] != band
               ):
                   band = window[0]
                   i += threshold
               else:
                   i += 1
           return band
       ```
       In words: the confirmed band only changes once `threshold`
       *consecutive* weekly evals in a row all agree on a different
       band than the current one. A single off-week eval never moves
       it. Default `threshold = 2`.
    3. **Quiz-accuracy modifier (decided, not left as a vague "nudge"):**
       compute average MC quiz accuracy over the last 2 weeks. If it has
       moved by more than 10 percentage points in the *same direction*
       as the most recent pending band change (i.e. the latest 1-2 evals
       already disagree with `computed_band` in a consistent direction),
       call `compute_band` with `threshold=1` instead of `2` — i.e. quiz
       data corroborating a shift lets a single differing weekly eval
       confirm it immediately. If quiz accuracy is flat or moving the
       opposite direction, use `threshold=3` instead — require one extra
       week of agreement before trusting a band change that quiz data
       doesn't support. Otherwise (quiz signal is neutral/inconclusive),
       use the default `threshold=2`. Quiz accuracy never sets a band by
       itself; it only widens or narrows the confirmation window.
    4. `trend`: compare `computed_band` to the most recent single
       eval's `cefr_band` using the fixed band ordering — "up" if the
       latest eval is higher, "down" if lower, "steady" if equal.
    5. Return `{band: computed_band, trend, last_eval_week_start}`.
  - No `record_weekly_eval` write path is needed — there is no state to
    update on write. Grading a new weekly submission just adds a row;
    the next `get_current_band()` call picks it up naturally.
- `backend/app/dashboard/service.py`:
  - `overview()`: replace/augment the existing `proficiency` float with
    `ProficiencyService.get_current_band()`'s output. Recommend keeping
    the old blended float too (renamed, e.g. `mastery_index`) for the
    category-mastery-driven view, but making the CEFR band the headline.

### B.4 Frontend changes
- Dashboard: display the CEFR band (e.g. "B2") as the primary metric,
  with a small trend indicator (up/steady/down) rather than a bare
  percentage. Category mastery breakdown stays as the secondary,
  more-granular/volatile view — unchanged in spirit, just no longer the
  headline number.
- Weekly report view: surface `cefr_band` + `band_justification` from
  the latest weekly writing eval alongside the existing dimension
  scores.

### B.5 Explicitly out of scope for this change
- No change to `LearningItem.mastery_score` or its decay/update math.
- No change to mini writing's interaction model or grading depth.
- No retroactive CEFR-banding of historical `WritingEvaluation` rows.

---

## Appendix A-1 — Draft rewrite: `QUIZ_MULTIPLE_CHOICE_PROMPT`

```
You are building one multiple-choice question to test whether the learner
can use the following item correctly and naturally in English -- not just
recognize its definition.

Learning item:
{item_text}
Definition: {item_definition}
Example usage: {item_example}

Write a question (a sentence with a blank, or a short natural-usage
scenario) whose correct answer requires understanding how this item is
actually used -- register, collocation, tense, or common confusion with
a near-synonym -- not just matching a dictionary definition.

Then write exactly 3 distractors. Distractors must be:
- Plausible to someone with partial understanding (not obviously wrong)
- Wrong for a specific, describable reason (wrong register, wrong
  collocation, wrong tense/form, or a common confusable word) --
  avoid distractors that are simply unrelated words
- Each wrong for a different reason where possible, so the question
  probes more than one kind of mistake

Return JSON:
{
    "prompt_text": "...",
    "correct_answer": "...",
    "distractors": ["...", "...", "..."]
}
Return valid JSON only.
```

## Appendix B-1 — Draft rewrite: `WEEKLY_WRITING_EVAL_RUBRIC`

```
Evaluate this submission against the CEFR writing descriptors below.
Select exactly ONE band that best matches the submission, and justify
your choice by pointing to specific features of the text (not just
restating the descriptor).

A2: Can write short, simple connected text on familiar topics. Frequent
    basic errors; limited range of vocabulary and structures.
B1: Can write straightforward connected text on familiar topics.
    Generally understandable despite noticeable errors; some ability to
    link ideas, but limited variety of structures.
B2: Can write clear, detailed text on a range of subjects. Good control
    of grammar; errors don't obscure meaning; reasonable range of
    vocabulary and some idiomatic usage; ideas are logically organized.
C1: Can write clear, well-structured text with an effective logical
    structure. Wide range of vocabulary and grammar used flexibly and
    accurately; only occasional, minor errors; register is consistently
    appropriate.
C2: Can write clear, smoothly flowing, complex text in an appropriate,
    effective style. Precise, idiomatic control of language; errors are
    vanishingly rare; nuanced and natural throughout.

Also score these supporting dimensions (0-100), consistent with the band
you selected -- they should read as evidence for the band, not a
contradiction of it:

1. Grammar (0-100)
2. Naturalness (0-100)
3. Vocabulary (0-100)
4. Coherence (0-100)

Provide specific feedback for each dimension.
```

---

## Suggested sequencing
1. Ship Part A (quiz) first — it's smaller, fixes an active bug, and has
   no data-model risk beyond the enum restriction.
2. Ship Part B (CEFR) second — touches schema (new columns/table),
   prompt, and a new service; benefits from Part A already having
   simplified the quiz-grading surface.

---

# Implementation Prompt (hand this to the execution agent)

You are implementing an already-agreed design change to the Praxis app.
Do not re-litigate the design — the plan below is final. If you hit an
ambiguity not covered here, make the smallest reasonable choice
consistent with the rest of this doc and note it in your summary rather
than pausing to ask, unless it risks data loss.

**Part A — Quiz consolidation to multiple-choice only:**

1. Collapse `QuizMode` usage to `MULTIPLE_CHOICE` only across the
   backend: `quizzes/service.py` (remove RANDOM handling, the
   deterministic/LLM-graded mode split, simplify `_mode_to_task`),
   `llm/interface.py` (remove unused `TaskType.QUIZ_*` entries except
   `QUIZ_MULTIPLE_CHOICE`), `llm/prompts/quiz.py` (delete removed-mode
   prompts, rewrite the MC prompt per Appendix A-1 in
   `praxis_plan_quiz_cefr.md`), `llm/tools.py` (drop `quiz_mode` param
   from `START_QUIZ_TOOL`), `chat/service.py` (drop quiz-mode parsing),
   `quizzes/router.py` (drop/ignore `mode` from the request schema).
2. Fix the weekly-quiz bug in `reports/router.py::start_weekly_quiz`:
   it currently passes `mode=QuizScope.WEEKLY_REVIEW` into a
   `QuizMode`-typed parameter. Call `QuizService.start_session` with no
   mode argument (or `MULTIPLE_CHOICE` if the param remains), and
   `scope=QuizScope.WEEKLY_REVIEW`.
3. Add scope-aware retrieval: `retrieval/service.py::select_eligible_items`
   gains an optional `since: date | None` param that biases selection
   toward items created/reviewed since that date, falling back to the
   normal pool if too few match. Wire the weekly quiz path to pass the
   current week's start date and a larger `size` (15–20) than the
   ad-hoc default.
4. Simplify frontend quiz components down to the single MC rendering
   path; remove any quiz-mode picker UI if present.
5. Add an Alembic migration reflecting the `QuizMode` restriction
   (no destructive column changes; historical non-MC rows stay as-is).
6. Run/update existing quiz tests; add a regression test asserting the
   weekly quiz path produces `MULTIPLE_CHOICE` questions (covering the
   bug just fixed).
7. Work through the Cleanup Checklist (A.6) explicitly — in particular,
   delete the now-dead `GRADE_QUIZ_ANSWER` path in full (task type,
   prompt, inference settings entry, validation branch, call site), fix
   the `quiz_mode` default in `db/models/quiz.py`, and delete
   `QuizModeSelector.tsx`. Run the grep sweep listed at the end of A.6
   and confirm it's clean before considering Part A done.

**Part B — CEFR-anchored writing evaluation + overall proficiency:**

1. Add `cefr_band` and `cefr_justification` columns to
   `WritingEvaluation` (migration included), populated only for weekly
   evaluations.
2. Rewrite `WEEKLY_WRITING_EVAL_RUBRIC`/`WEEKLY_WRITING_EVAL_PROMPT` per
   Appendix B-1 in `praxis_plan_quiz_cefr.md`: force a single CEFR band
   selection with justification, keep the four 0-100 sub-scores as
   supporting evidence. Update `WeeklyWritingEvalOutput` schema and
   `llm/validation.py` to require `cefr_band` (one of
   A1/A2/B1/B2/C1/C2) and `band_justification`. Leave
   `MiniWritingEvalOutput`/mini prompt unchanged.
3. Create `proficiency/service.py::ProficiencyService.get_current_band()`
   implementing the **derived-on-read** hysteresis algorithm specified
   in section B.3 of this doc exactly as written (the `compute_band`
   function with `threshold` 1/2/3 selected by the quiz-accuracy
   modifier). Do not introduce a stored mutable counter/table — this was
   a deliberate decision, not an open point.
4. Wire `dashboard/service.py::overview()` to surface the CEFR band +
   trend as the headline `proficiency` field (keep the existing
   category-mastery blend available under a renamed key, e.g.
   `mastery_index`, rather than deleting it).
5. Update the weekly report response/view to include `cefr_band` and
   `band_justification` from the latest weekly writing eval.
6. Update frontend dashboard to show the CEFR band + trend indicator as
   the primary metric; category mastery stays as secondary detail.
7. Do not touch `LearningItem.mastery_score`/decay math, mini writing's
   interaction model, or retroactively band historical evaluations.

**Note on the app's inference backend (Ollama, not the coding agent
running this task):** the app calls Ollama with
`format=<pydantic_schema>` (grammar-constrained decoding), already in
place in `ollama_adapter.py` — this means new required/enum fields
(e.g. `cefr_band`) will be structurally enforced regardless of which
model Ollama is pointed at, so no extra schema-robustness work is
needed beyond defining the Pydantic schema correctly.

Deliver Part A and Part B as separate commits/PRs if possible, in that
order. Summarize what you changed, any migrations added, and any
judgment calls you made against an ambiguity, at the end.
