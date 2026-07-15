# CLAUDE

## 1. Purpose

This document is the project's engineering constitution. It governs how Claude Code works on this codebase: scope, decision boundaries, implementation discipline, validation expectations, and workflow. It does not replace the product or architecture documents; it operationalizes them for day-to-day implementation work.

## 2. Document Authority

When requirements, architecture, or execution guidance conflict, the following order applies:

1. [docs/Praxis_Architecture_v1_1.md](docs/Praxis_Architecture_v1_1.md)
2. [docs/Praxis_PRD_v1.0.md](docs/Praxis_PRD_v1_0.md)
3. [docs/TASK_PLAN_ClaudeCode.md](docs/TASK_PLAN_ClaudeCode.md)
4. [docs/CLAUDE.md](docs/CLAUDE.md)

If a question is not answered by those documents, stop and ask. Claude Code must never invent a fifth source of truth.

## 3. Engineering Philosophy

Work in the spirit of the architecture:

- Simplicity over cleverness.
- Readability over abstraction.
- Explicit over implicit.
- Reliability before optimization.
- Local-first, single-user design.
- Preserve the existing architectural boundaries.
- Prefer small, understandable changes over broad rewrites.

Do not introduce complexity without a clear need, and do not optimize before the behavior is correct.

## 4. Scope Discipline

Claude Code must:

- implement only the current task
- never begin future tasks
- never redesign the architecture
- never expand scope
- never add nice-to-have functionality
- never remove existing functionality
- stop and report blockers instead of improvising

If a task is not explicitly requested by the current task or the current epic, do not do it.

## 5. Decision Boundaries

Claude Code may decide internal implementation details such as:

- helper methods
- private refactoring
- naming and organization
- small code-structure choices
- local validation strategy

Claude Code may not decide:

- database schema changes
- API contract changes
- prompt contract changes
- architecture changes
- feature additions
- behavioral changes outside the current task

When a decision would cross one of those boundaries, stop and ask.

## 6. Coding Standards

Code should be straightforward, typed, and maintainable.

Follow the project's established conventions:

- use strong typing where the stack supports it
- keep naming consistent and descriptive
- keep functions focused and cohesive
- prefer modular design over monolithic files
- avoid duplication
- handle errors explicitly
- add meaningful docstrings for public interfaces and new modules
- keep comments minimal and useful

Use the project's configured linting, formatting, and type-checking tools rather than introducing ad hoc conventions.

## 7. Refactoring Rules

Refactoring is allowed only when it is internal and safe:

- behavior remains unchanged
- contracts remain unchanged
- validation continues to pass

Do not perform architectural refactoring as part of unrelated work. Do not rewrite completed modules simply because they could be improved.

## 8. Testing Philosophy

No task is complete until validation passes.

Use the architecture's testing approach as the baseline:

- test the real behavior being changed
- prefer fixing the root cause over weakening or rewriting tests
- cover the affected behavior with focused validation
- do not claim success without running the relevant checks

If a test fails, investigate it before changing the test to hide the issue.

## 9. Git Workflow

For each epic:

1. create an epic branch
2. complete the implementation for that epic
3. run the required validation
4. update the execution state in [docs/TASK_PLAN_ClaudeCode.md](docs/TASK_PLAN_ClaudeCode.md)
5. fill in the Epic Completion Report (in the existing section at the end of each epic)
6. stop and wait for human review

Claude Code must never merge into main. Only the human developer performs merges.

**Commit Process:** After the human confirms the epic is complete, Claude Code will execute the commit directly from the conversation using the provided commit message template.

## 10. TASK_PLAN Responsibilities

Treat the task plan as a living execution document.

After each completed epic, Claude Code should:

- update Project State
- update Epic Status
- record implementation decisions
- record deviations if any
- write the completion report

Do not leave the task plan stale or incomplete.

## 11. Handling Blocking Issues

If implementation is blocked by an architecture contradiction, missing requirement, impossible dependency, or ambiguous contract, stop immediately.

When blocked, provide:

- Problem
- Cause
- Proposed options

Do not silently redesign the system to bypass the issue.

## 12. Performance Philosophy

Prefer maintainability and correctness over premature performance work.

- measure before optimizing
- avoid unnecessary abstraction
- avoid complexity without evidence
- keep the implementation understandable before making it faster

## 13. AI Behaviour Rules

Claude Code must never:

- redesign the system to fit a preferred pattern
- rewrite completed modules unnecessarily
- modify frozen documents outside the agreed task
- skip validation
- ignore failed tests
- hide errors or inconsistencies
- fabricate successful execution

Communicate uncertainty directly and explicitly.

## 14. Definition of Done

A task is complete only when:

- the implementation is finished
- the relevant validation passes
- linting and formatting checks pass
- the acceptance criteria are satisfied
- any required documentation is updated

An epic is complete only when:

- all tasks in the epic are complete
- the task plan has been updated
- the epic report has been written
- the work is ready for human review
