---
name: implement
description: Implement an approved plan from docs/plans/ (or a named routine change).
argument-hint: <plan path or change, e.g. "docs/plans/P1-2-backend-health-request-id.md">
context: fork
agent: implementer
background: false
---

Your task is to implement: $ARGUMENTS. Work only from that plan (or the files named), write the named tests first, run the targeted tests and ruff on the changed files. Return every changed file, the test and lint results, and any open issue.
