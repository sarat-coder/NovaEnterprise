---
name: test
description: Write and run targeted offline tests for a plan, file or behaviour.
argument-hint: <plan path, file, or behaviour to test>
context: fork
agent: test-engineer
background: false
---

Your task is to write and run tests for: $ARGUMENTS. Tests must run offline (fake LLM, memory stores, SQLite, fakeredis). Return every test file changed, the pass/fail result of each targeted test, and any failure with `file:line`.
