---
name: review
description: Review the current uncommitted diff and rank findings as blocker, major or minor.
argument-hint: [optional focus, e.g. "security" or a path]
context: fork
agent: code-reviewer
background: false
---

Your task is to review the current uncommitted diff (`git diff` and `git diff --staged`), focusing on: $ARGUMENTS. Return findings ranked blocker, major, minor, each with `file:line` and a one-line fix. Return "No findings" if there are none.
