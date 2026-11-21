---
name: <agent-name>
description: <one line: what it does and when to use it. Add "Use proactively ..." if Claude should call it unprompted.>
model: <haiku | sonnet | opus>
effort: <low | medium | high>
maxTurns: <number>
tools: <Read, Grep, Glob[, Edit, Write, Bash]>   # never list Agent
---

<!-- If this agent uses opus, add its name to ALLOW_EXPENSIVE in .claude/hooks/agent_guard.py. -->
<!-- Copy this file into .claude/agents/ to activate it; every file in agents/ loads as a live agent. -->

<Role in one sentence.>

- <Scope: which files or folders it may touch.>
- <How it works: steps, commands.>
- <Output format.>

Report every changed file, every open issue and every failing test in full. Do not shorten those lists. Keep everything else brief.
If you reach your turn limit, say so first and list what is left undone.
If a design question blocks you, stop and return the question in one sentence instead of guessing.
