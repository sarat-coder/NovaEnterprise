---
name: finish-task
description: Finish a TASKS.md sub-task - run lint and offline tests, update .gitignore/.env.example/MEMORY.md, and write the PR description.
argument-hint: <task id, e.g. P1-2>
disable-model-invocation: true
---

Finish sub-task **$ARGUMENTS** on its current feature branch. Do not commit, push or merge.

1. **Branch check.** `git branch --show-current` must equal the branch in the `$ARGUMENTS` row of `TASKS.md`. Stop if not.
2. **Lint.** `uv run ruff check .` and `uv run ruff format --check .` (once `frontend/` exists, also `npm run lint` there). Fix what they report.
3. **Tests.** `make test` (or `uv run pytest` before the Makefile exists), offline. If the output is long, use the log-triage agent. Fix failures; report any that remain.
4. **Exit criteria.** Compare the change against the task's part of the phase in `PLAN_PHASE.md` and the `PLAN.md` rows it delivers. List each criterion as met / not met.
5. **Hygiene.**
   - `.gitignore`: add any new generated files, caches, data or secret paths the task introduced (`git status --short --ignored` helps). Report what you added, or "no change".
   - `.env.example`: every new setting has a placeholder entry.
   - `MEMORY.md`: update the status row, add locked decisions, close answered questions, append a change-log line.
   - Never stage `.env`, `data/`, `*.db` or keys.
6. **Review.** Run `/review` on the diff and fix any blocker.
7. **PR description.** Output a block ready for GitHub's "Add a description" box:

   ```markdown
   ## <task id> · <task title>
   **Branch:** `feature/...` → `development`

   ### What
   - <2–5 bullets of what changed>

   ### Why
   <one sentence: the PRD rows (F/N) or phase goal it serves>

   ### How to test
   - `make test` (offline)
   - <one manual check, e.g. a curl>

   ### Checklist
   - [x] ruff check / format clean
   - [x] tests pass offline
   - [x] .gitignore / .env.example updated (or not needed)
   - [x] MEMORY.md updated
   ```

8. Remind the user: after the PR merges, set the row in `TASKS.md` to `Completed ✅` and update the Progress summary count.
