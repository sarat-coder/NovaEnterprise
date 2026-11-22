# Phase 12 — Project System Design Evolution

## Starting Point: What Existed Before Phase 12

After Phases 1–11 we had:
- A fully configured FastAPI backend with auth, middleware, health, and all browse APIs
- A complete retrieval layer: vector, SQL, graph, hybrid
- 14 individual node functions that each perform one step of the research workflow
- Deterministic rules for analysis, complexity, decomposition, and routing
- Four memory scopes
- Guardrails, approval service, ingestion pipeline

**Missing:** The completed workflow (connecting nodes together), the research service (running it in the background), and the research API (the HTTP front door).

---

## Design Stage 1: The Workflow Tracer

Before connecting nodes, we needed a way to observe every node transition. The `WorkflowTracer` wraps any node function and records timing data to the database.

```mermaid
classDiagram
    class WorkflowTracer {
        session_id: str
        persist_fn: Callable
        +node(name) → decorator
    }

    class PersistFn {
        <<callable>>
        node: str
        event_type: str
        payload: dict
        duration_ms: float
    }

    class WorkflowEvent {
        id: int
        session_id: str
        node: str
        event_type: str
        payload: JSON
        duration_ms: float
        occurred_at: datetime
    }

    WorkflowTracer --> PersistFn : calls
    PersistFn --> WorkflowEvent : writes
```

**Design choice:** The tracer receives `persist_fn` as a constructor argument (dependency injection). This means:
- The tracer never imports `research_service.py` (no cycle)
- In tests, `persist_fn` can be a no-op or a list collector
- The service layer controls the database session lifetime

---

## Design Stage 2: Graph Wiring

The 14 nodes are connected into a LangGraph `StateGraph`. The assembly is defined in `agents/graph.py`.

```mermaid
flowchart TD
    START([Question]) --> AQ[analyze_query]
    AQ --> AC[assess_complexity]
    AC --> D[decompose]
    D --> RR[route_retrieval]
    RR --> VR[vector_retrieval]
    VR --> SR[sql_retrieval]
    SR --> GR[graph_retrieval]
    GR --> HR[hybrid_retrieval]
    HR --> CE[collect_evidence]
    CE --> CME[check_missing_evidence]
    CME --> |"missing & rounds < MAX"| CR[corrective_retrieval]
    CR --> CE
    CME --> |"complete"| VE[verify_evidence]
    VE --> SA[synthesize_answer]
    SA --> VC[verify_citations]
    VC --> END([Answer + citations_valid])
```

**Key design decision:** All four retrieval nodes run sequentially (not in parallel). Each node only processes sub-questions whose `strategy` matches its type — the others pass through unchanged. This means:

- For a simple question: `vector_retrieval` acts, the other three pass through
- For the canonical question: `graph_retrieval` handles sq1 and sq3; `sql_retrieval` handles sq2; `hybrid_retrieval` handles sq4

This is simpler than parallel fan-out for v1 and avoids race conditions on the shared evidence list.

---

## Design Stage 3: Research Service

The `ResearchService` orchestrates the workflow. It is called by the API layer but never imports FastAPI types.

```mermaid
sequenceDiagram
    participant API as research.py (API)
    participant SVC as research_service.py
    participant DB as Database
    participant WF as LangGraph workflow

    API ->> SVC: create_session(question, user_id)
    SVC ->> DB: INSERT research_sessions (status=running)
    SVC -->> API: session_id

    API ->> BG: BackgroundTasks.add_task(start_research)
    API -->> Browser: 202 {session_id, status: "running"}

    BG ->> SVC: start_research(session_id, question)
    SVC ->> WF: build_graph(tracer).invoke(initial_state)

    loop Every node
        WF ->> DB: INSERT workflow_events (via tracer persist_fn)
    end

    WF -->> SVC: final_state
    SVC ->> DB: UPDATE research_sessions (status=completed, answer=...)
```

**Why BackgroundTasks?** FastAPI's `BackgroundTasks` runs the workflow after the HTTP response is sent. The workflow takes 7+ seconds with fake providers; without background tasks, the browser would time out.

---

## Design Stage 4: Research API

Three endpoints expose the research workflow over HTTP.

```mermaid
flowchart LR
    subgraph Browser
        B1["POST /api/v1/research\n{question}"]
        B2["GET /api/v1/research/{id}\n(poll every 2s)"]
        B3["GET /api/v1/research/{id}/events"]
    end

    subgraph FastAPI
        A1["Validate (5–2000 chars)\nCheck analyst role\n→ 202 + session_id"]
        A2["Lookup DB\n→ ResearchSessionOut"]
        A3["Lookup DB\n→ list[WorkflowEventOut]"]
    end

    subgraph DB
        RS[(research_sessions)]
        WE[(workflow_events)]
    end

    B1 --> A1
    A1 --> RS
    B2 --> A2
    A2 --> RS
    B3 --> A3
    A3 --> WE
```

**RBAC enforcement:**
- `POST /api/v1/research` → requires `analyst` role (minimum)
- `GET /api/v1/research/{id}` → requires `viewer` role (everyone logged in)
- `GET /api/v1/research/{id}/events` → requires `viewer` role

---

## Design Stage 5: make demo

The demo script bootstraps the database, seeds data, ingests documents, and runs the workflow end-to-end, printing each node's timing and the final answer.

```mermaid
flowchart TD
    MAKE[make demo] --> BOOT[Bootstrap DB + seed]
    BOOT --> SEED[Seed knowledge graph]
    SEED --> INGEST[Ingest 15 documents]
    INGEST --> RUN[Run workflow via build_graph]
    RUN --> PRINT[Print node timings + answer]
```

---

## Final Architecture After Phase 12

```mermaid
graph TD
    subgraph Browser ["Browser (:3001)"]
        UI[research UI]
    end

    subgraph FastAPI ["FastAPI (:8001)"]
        AUTH[auth middleware]
        RAPI[api/research.py\nPOST research\nGET session\nGET events]
        SVC[services/research_service.py\ncreate_session\nstart_research\npersist_final]
    end

    subgraph Agents ["agents/ — NEW in Phase 12"]
        STATE[state.py\nResearchState]
        RULES[rules.py]
        GRAPH[graph.py\nbuild_graph]
        NODES[nodes/ × 14]
        TRACER[app/core/observability.py\nWorkflowTracer]
    end

    subgraph RAG ["rag/"]
        RETR[retriever.py]
        SQL[sql_retrieval.py]
        GRAPH_STORE[graph_store.py]
    end

    subgraph DB ["Database (SQLite / Postgres)"]
        RS[(research_sessions)]
        WE[(workflow_events)]
    end

    UI -->|"POST /api/v1/research"| AUTH
    AUTH --> RAPI
    RAPI -->|"create_session"| SVC
    SVC -->|"BackgroundTasks"| GRAPH
    GRAPH --> NODES
    NODES --> RULES
    NODES --> RETR
    NODES --> SQL
    NODES --> GRAPH_STORE
    TRACER -->|"persist_fn"| WE
    SVC --> RS
    UI -->|"poll GET /api/v1/research/{id}"| RAPI
    RAPI --> RS
    UI -->|"GET /api/v1/research/{id}/events"| RAPI
    RAPI --> WE
```

**Everything is now connected.** The browser can submit a question, receive an immediate response, and poll for the result while the AI assembly line runs in the background.
