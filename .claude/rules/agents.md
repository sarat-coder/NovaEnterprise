---
paths:
  - "agents/**"
---

# Agent and workflow conventions (CLAUDE.md §6, §15)

- Rules first, LLM second: `agents/rules.py` holds deterministic analysis, complexity, decomposition and routing. The LLM proposes; rules correct. Everything works with `LLM_PROVIDER=fake`.
- A question that needs relationships is never routed vector-only, whatever the model says.
- Node ids are a contract with the frontend (`docs/FRONTEND_ASSUMPTIONS.md`); changing `GRAPH_NODES` / `GRAPH_EDGES` breaks `test_graph_shape_matches_frontend_assumptions`.
- Every node is wrapped in `tracer.node(...)`; state is persisted after every node.
- Corrective retrieval respects `MAX_CORRECTIVE_ROUNDS`; no unbounded loops. Sub-questions ≤ `MAX_SUBQUESTIONS`.
- All retrievers return the one `Evidence` shape; every answer claim cites an evidence id as `[n]`.
- Evidence verification and citation verification stay separate nodes.
- A failed store records an error on its sub-question; the workflow continues (degrade, don't crash).
- Agents never talk to HTTP, the browser, or repositories directly.
- Expose decisions, queries, evidence and timings only — never raw reasoning.
- Expected outputs: canonical → complex, 4 sub-questions (graph, sql, graph, hybrid), 9 evidence, 0 corrective rounds. Simple → 1 sub-question, vector only.
