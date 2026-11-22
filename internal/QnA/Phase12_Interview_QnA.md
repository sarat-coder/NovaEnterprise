# Phase 12 — Interview Questions & Answers

## Workflow Graph and Research API

---

**Q1: What is the difference between Phase 11 and Phase 12? Why did you separate them?**

Phase 11 built the individual node functions — the 14 pure functions that each perform one step of the research workflow (analyze, decompose, retrieve, verify, synthesize). Phase 12 wired those nodes into a running LangGraph `StateGraph`, built the research service that runs the workflow in the background, and added the HTTP API that lets a browser submit questions and poll for answers.

The separation makes the nodes independently testable in Phase 11 without needing a running server. By Phase 12, all the pieces exist and we just need to connect them.

---

**Q2: Why does the POST /api/v1/research endpoint return 202 instead of 200?**

HTTP 200 means "Here is your complete answer." HTTP 202 means "I've accepted your request; the work is happening but isn't done yet." The research workflow takes 7+ seconds even with a fake LLM — far longer than a browser will wait for a synchronous HTTP response (which times out at 30–60 seconds in practice).

202 + background task + polling is the standard pattern for long AI workflows. The browser immediately has a `session_id` to poll against, and the UI can show a progress bar while the assembly line runs.

---

**Q3: How does the workflow tracer work without coupling the agents layer to the database?**

The `WorkflowTracer` accepts a `persist_fn` as a constructor argument. The tracer itself never imports `research_service.py` or any database code — it just calls whatever function it was given. The research service constructs the tracer and passes in a closure that opens a database session and writes a `WorkflowEvent` row.

This is dependency injection. It means:
- Agents never depend on the service layer (no import cycle)
- In tests, `persist_fn` is a no-op — no database needed
- The service layer controls the session lifetime, not the tracer

---

**Q4: Why is state persisted after every node rather than only at the end?**

CLAUDE.md says: "Persist after every node. The DB state is the UI's progress bar." If the workflow crashes after `decompose` but before `synthesize_answer`, the analyst can see exactly which step failed by polling the events endpoint. Without per-node persistence, a crash would look indistinguishable from "still running."

It also means the UI can show real-time progress: "✓ analyze_query (12ms) → ✓ assess_complexity (3ms) → ✓ decompose (8ms) → ⟳ graph_retrieval..."

---

**Q5: What is GRAPH_NODES and why is it a contract?**

`GRAPH_NODES` is a list of the 14 node id strings in `agents/graph.py`. The front-end renders these as steps in the research timeline — it references them by name. `test_graph_shape_matches_frontend_assumptions` checks that the set of node ids matches the expected set exactly.

If a developer renames `analyze_query` to `query_analysis`, the front-end would stop displaying that step. Making GRAPH_NODES an explicit, tested list prevents silent regressions.

---

**Q6: How do all four retrieval nodes run when only some sub-questions need each type?**

Each retrieval node filters by strategy. For example, `sql_retrieval` loops over `state["sub_questions"]` and **skips any sub-question whose strategy is not "sql"** — those pass through unchanged. Only the matching sub-questions are processed.

For the canonical question (4 sub-questions: graph, sql, graph, hybrid):
- `vector_retrieval` skips all 4 (none are "vector")
- `sql_retrieval` processes sq2 (strategy="sql"), skips the others
- `graph_retrieval` processes sq1 and sq3 (strategy="graph")
- `hybrid_retrieval` processes sq4 (strategy="hybrid")

The evidence lists accumulate as state passes through each node.

---

**Q7: Why is the corrective retrieval loop bounded at 1 round?**

CLAUDE.md §6.1 states the loop must terminate. `MAX_CORRECTIVE_ROUNDS=1` is the default. The `should_correct()` function in `agents/rules.py` returns `False` once `corrective_rounds >= max_rounds`, regardless of how many sub-questions are still missing evidence.

An unbounded loop is a research assistant that never answers. A bounded loop degrades gracefully: it tries once to fill gaps, and if that doesn't work, it synthesizes the best answer it can with what it has.

---

**Q8: How does the demo work without any external services?**

The demo uses environment variable overrides:
- `LLM_PROVIDER=fake` → FakeChatModel (deterministic hash-based responses, no API key)
- `VECTOR_STORE=memory` → MemoryVectorStore (Python dict, no Qdrant needed)
- `GRAPH_STORE=memory` → MemoryGraphStore (Python dict, no Neo4j needed)
- `DATABASE_URL=sqlite:///data/enterprise.db` → SQLite (no Postgres needed)
- `REDIS_URL=` (empty) → fakeredis (no Redis needed)

All five stores are replaceable by design. The demo proves the application runs end-to-end offline. This was a hard constraint from the beginning (N1: "Runs with no API key and no external service").

---

**Q9: What happens if the graph store (Neo4j) is down in production?**

Each store registers a readiness check with `register_check()`. If Neo4j is unavailable, `GET /health/ready` reports `degraded` for `graph_store`. The workflow continues but sub-questions routed to `graph_retrieval` will fail and have `status="error"` in their sub-question record. The workflow does not crash — it degrades gracefully and synthesizes an answer from whatever evidence was collected.

This is the "degrade, don't crash" principle from CLAUDE.md §15 rule 9.

---

**Q10: How is the research API protected from viewers submitting questions?**

`POST /api/v1/research` uses `require_role("analyst")`. This FastAPI dependency calls `get_current_user()` from the OAuth2 bearer token, checks the role enum value (viewer=1, analyst=2, admin=3), and raises `HTTP 403 Forbidden` if the role is below the minimum.

`test_viewer_cannot_start_research` in `tests/api/test_research_lifecycle.py` proves this. Any viewer token hitting the research endpoint receives a 403 before any workflow starts.

---

**Q11: What is the difference between ResearchState and ResearchSessionOut?**

`ResearchState` is the internal TypedDict that flows through the LangGraph workflow nodes. It lives in the `agents/` layer and contains everything the workflow needs to operate: sub-question dicts, raw Evidence objects, corrective round count, and intermediate analysis results.

`ResearchSessionOut` is a Pydantic model in `backend/app/schemas/research.py`. It's the HTTP API response shape — what the browser receives when polling. It's a cleaned-up, serialisable view of the data stored in the database, not a direct export of the workflow state.

Keeping these separate enforces the layering rule: agents never know about HTTP, and the API never exposes raw internal state.

---

**Q12: What would you change in Phase 12 if you were scaling to production?**

Three things:
1. **Replace BackgroundTasks with a proper worker queue** (Celery + Redis or LangGraph's `langgraph-checkpoint-postgres`). BackgroundTasks works for a single-process server but doesn't survive restarts or scale across multiple processes.
2. **Add Server-Sent Events or WebSockets** instead of 2-second polling. Polling creates unnecessary load; SSE would push events to the browser as they happen.
3. **Store full evidence and sub-questions in the database** rather than just counts. The current implementation stores `evidence_count` but not the full evidence list, so the GET poll response doesn't include evidence items. This would need a separate table or JSON column.
