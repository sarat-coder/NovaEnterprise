---
name: cost-report
description: Summarise Claude Code token and agent usage for this project.
argument-hint: [optional session id or "latest"]
context: fork
agent: general-purpose
model: haiku
background: false
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash
---

Your task is a usage report for this project. Scope: $ARGUMENTS (default: the latest session).

1. If `scripts/claude_usage/report.py` exists, run it with `python scripts/claude_usage/report.py` and summarise its output. Otherwise, read the session transcript (`*.jsonl`) and its `subagents/` folder under `~/.claude/projects/<project>/` (for this repo the folder is `c--Euron-NovaEnterprise`), and total `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` and `output_tokens` per model.
2. In both cases, then read `.claude/agent-calls.jsonl` and list, per agent type: spawn count, models requested, blocked calls, and the `description` of every general-purpose spawn.
3. Mention that `/usage` shows the main session's totals for free.

Return a short table per step. No prose beyond one summary line.
