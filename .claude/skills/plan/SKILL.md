---
name: plan
description: Write an implementation plan to docs/plans/ for a TASKS.md sub-task or a multi-file change.
argument-hint: <task id or change, e.g. "P1-2 · Health routes and request-id middleware">
context: fork
agent: planner
background: false
---

Your task is to write an implementation plan for: $ARGUMENTS. Read TASKS.md, CLAUDE.md and the PRD rows involved, then write the plan to `docs/plans/`. Return the plan's path, the list of files it will change, the tests it names, and any open design question.
