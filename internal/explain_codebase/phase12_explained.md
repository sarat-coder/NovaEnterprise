# Phase 12 — Workflow Graph and Research API: Plain-Language Explanation

## What problem are we solving?

By Phase 11 we had built every individual ingredient of the research assistant:
- Rules to understand questions (Phase 11)
- 14 node functions that each perform one step of the investigation (Phase 11)
- Vector search, SQL queries, graph traversals (Phases 6–8)
- Memory (Phase 10)
- Authentication, documents, approval (Phases 3, 9)

But none of those pieces were **connected together** and none could be **called from a web browser**.

Phase 12 is the assembly step: it wires all the nodes into one running workflow, exposes a research API endpoint, and makes the whole thing work end-to-end so you can type a question and receive a cited answer.

---

## Analogy: a factory assembly line

Think of the previous phases as building individual machines in a factory:
- Phase 6 built a document search machine
- Phase 7 built a relationship-graph machine
- Phase 8 built a database query machine
- Phase 11 built the control panels (the nodes) that operate each machine

Phase 12 **lays the conveyor belt** that connects all the machines in the right order and **adds the front door** (the API) so customers can submit work orders.

---

## The four things Phase 12 adds

### 1. The workflow tracer — the factory's logging system

Every machine on the assembly line has a sensor that records:
- When it started running
- How long it took
- What it produced

The workflow tracer (`backend/app/core/observability.py`) is exactly that sensor. It wraps every node function and writes a **workflow event** to the database after the node finishes. These events become the "event timeline" that the analyst sees in the UI.

```
analyze_query  → ✓ completed in 12ms
assess_complexity → ✓ completed in 3ms
decompose      → ✓ completed in 5ms
...
verify_citations → ✓ completed in 8ms
```

If a node crashes, the tracer still writes an error event so the analyst knows exactly where the workflow stopped.

### 2. The graph wiring — the assembly line blueprint

`agents/graph.py` defines the blueprint: which nodes run in what order, and what the branching conditions are.

The 14 nodes are connected in this order:

```
analyze_query
    ↓
assess_complexity
    ↓
decompose
    ↓
route_retrieval
    ↓
vector_retrieval → sql_retrieval → graph_retrieval → hybrid_retrieval
    ↓ (all feed into)
collect_evidence
    ↓
check_missing_evidence
    ├─ (some missing, rounds < limit) → corrective_retrieval → collect_evidence (loop back)
    └─ (complete) → verify_evidence
                        ↓
                   synthesize_answer
                        ↓
                   verify_citations
                        ↓
                       END
```

The only "decision point" is after `check_missing_evidence`: the system looks at whether any sub-question came back empty-handed. If yes (and we haven't tried corrective retrieval yet), it runs a broader search and tries again. If no (or we've already tried), it moves on to writing the answer.

**Why is this important?** The graph shape is a **contract with the front-end**: the UI shows node names as steps in a progress bar. The test `test_graph_shape_matches_frontend_assumptions` ensures no one silently renames or removes a node.

### 3. The research service — the factory floor manager

`backend/app/services/research_service.py` is the manager who:
1. Creates a "job ticket" (a row in the `research_sessions` database table) when a question comes in
2. Starts the assembly line running in the background (so the analyst doesn't have to wait at the door)
3. After each node finishes, updates the job ticket with the latest state
4. When the assembly line finishes, writes the final answer to the job ticket

The key insight: **the database row is the progress bar**. At any moment, the analyst can check the database row to see how far the assembly line has gotten, without waiting for it to finish.

### 4. The research API — the front door

`backend/app/api/research.py` adds three HTTP endpoints:

| Endpoint | What it does |
|---|---|
| `POST /api/v1/research` | Submit a research question → instantly returns a job ticket ID (202 response) |
| `GET /api/v1/research/{id}` | Check the status of a job ticket |
| `GET /api/v1/research/{id}/events` | See every step the assembly line took, with timings |

**Why 202 instead of 200?** HTTP 202 means "Accepted — I've queued your request but it's not done yet." This is the right status code when work takes longer than a web request (which times out after ~30 seconds). The research workflow may take 7+ seconds, so we return immediately and let the browser poll for updates.

---

## The request flow, step by step

Here's exactly what happens when an analyst types: *"Which customers were impacted by the Payments API last quarter?"*

```
1. Browser sends:  POST /api/v1/research
                   { "question": "Which customers were impacted..." }
                   Authorization: Bearer <jwt-token>

2. FastAPI checks: Is the token valid? Is the user an analyst? ✓

3. Research service: Creates a row in research_sessions table
                     session_id = "abc-123", status = "running"

4. API responds:   202 Accepted
                   { "session_id": "abc-123", "status": "running" }
                   (browser receives this in <100ms)

5. Background:     The workflow starts running (analyst doesn't wait)
                   analyze_query → assess_complexity → decompose → ...
                   Each node writes an event to workflow_events table

6. Browser polls:  GET /api/v1/research/abc-123  (every 2 seconds)
                   Response: { "status": "running", "complexity": "complex", ... }

7. Workflow ends:  verify_citations completes
                   research_sessions row updated: status = "completed", answer = "..."

8. Next poll:      GET /api/v1/research/abc-123
                   Response: { "status": "completed", "answer": "Acme Corp and Globex [1][2]..." }
```

---

## The make demo command

Before Phase 12 there was no way to run the whole system from the command line. Now you can run:

```bash
make demo
```

This:
1. Initialises the database
2. Seeds the sample data
3. Indexes all 15 documents
4. Runs the canonical question through the entire workflow
5. Prints every node's timing and the final cited answer

You can also test a custom question:

```bash
make demo QUESTION="What is our data retention policy?"
```

---

## Who can use the research API?

| User role | Can start research? | Can view results? |
|---|---|---|
| `viewer` | ❌ 403 Forbidden | ✓ |
| `analyst` | ✓ | ✓ |
| `admin` | ✓ | ✓ |

A viewer trying to `POST /api/v1/research` receives a **403** error immediately, before any workflow runs.

---

## Summary of files created in Phase 12

| File | What it does |
|---|---|
| `backend/app/core/observability.py` | WorkflowTracer — wraps nodes and records timing events |
| `agents/__init__.py`, `agents/nodes/__init__.py` | Package markers |
| `agents/state.py` | ResearchState TypedDict — the shared data bag |
| `agents/rules.py` | Deterministic analysis, complexity scoring, decomposition, routing |
| `agents/prompts.py` | LLM prompt templates |
| `agents/nodes/analyze_query.py` | Node: extract intent, entities, time range |
| `agents/nodes/assess_complexity.py` | Node: classify simple / moderate / complex |
| `agents/nodes/decompose.py` | Node: split question into sub-questions |
| `agents/nodes/route_retrieval.py` | Node: validate and re-apply routing rules |
| `agents/nodes/vector_retrieval.py` | Node: run hybrid vector search |
| `agents/nodes/sql_retrieval.py` | Node: run SQL template queries |
| `agents/nodes/graph_retrieval.py` | Node: run typed graph traversals |
| `agents/nodes/hybrid_retrieval.py` | Node: run vector + graph combined |
| `agents/nodes/collect_evidence.py` | Node: deduplicate and number evidence |
| `agents/nodes/check_missing_evidence.py` | Node: detect unanswered sub-questions |
| `agents/nodes/corrective_retrieval.py` | Node: broadened search for missing evidence |
| `agents/nodes/verify_evidence.py` | Node: scan evidence through guardrails |
| `agents/nodes/synthesize_answer.py` | Node: produce a cited answer with LLM |
| `agents/nodes/verify_citations.py` | Node: check every [n] resolves to evidence |
| `agents/graph.py` | GRAPH_NODES, GRAPH_EDGES, build_graph() — the assembly line |
| `backend/app/services/research_service.py` | Orchestrates workflow, persists state |
| `backend/app/api/research.py` | POST research, GET session, GET events |
| `scripts/demo.py` | End-to-end demo script |
| `tests/workflow/test_graph_shape.py` | Guards node/edge contract with frontend |
| `tests/workflow/test_canonical_question.py` | Full canonical question exercise |
| `tests/workflow/test_simple_question.py` | Simple question routing verification |
| `tests/workflow/test_corrective_retrieval.py` | Bounded loop verification |
| `tests/workflow/test_citations.py` | Citation integrity verification |
| `tests/api/test_research_lifecycle.py` | 202 start, poll, events, RBAC |
