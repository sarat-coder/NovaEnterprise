---
name: start-task
description: Start a TASKS.md sub-task - check predecessors, create its feature branch from development, then plan it.
argument-hint: <task id, e.g. P1-2>
disable-model-invocation: true
---

Start sub-task **$ARGUMENTS** from `TASKS.md`.

1. **Find the row.** Read the `$ARGUMENTS` row in `TASKS.md`: title, branch name, status. Stop if it is already `Completed ✅`.
2. **Check dependencies.** Read the phase's "Depends on" and "Merge order" lines. List each predecessor and its status. If any predecessor is `Pending ❌`, stop and report which ones; do not start.
3. **Read context.** `MEMORY.md` (open questions that block this task — §3 "Blocks" column), the `PLAN_PHASE.md` exit criteria for the phase, and the `PLAN.md` rows the task delivers. If an open question blocks it, stop and ask it in one sentence.
4. **Branch.** Run `git status --short`; stop if the working tree has uncommitted changes. Then:
   `git checkout development && git pull origin development && git checkout -b <branch from the row>`.
   If `development` does not exist, stop and point to section 3 of `Git_GitHub_Workflow_Guide.md`.
   Use the branch name exactly as written in the row.
5. **Plan.** Run `/plan $ARGUMENTS` and show the plan path and its file list. Wait for approval before `/implement`.

Do not change TASKS.md status here.
