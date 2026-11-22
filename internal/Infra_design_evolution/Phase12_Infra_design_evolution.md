# Phase 12 — Infrastructure and Component Wiring Design Evolution

## Overview

Phase 12 is the first phase where the entire system becomes a runnable application. All components built in earlier phases are now wired together and exposed over HTTP.

---

## Component Map After Phase 12

```mermaid
graph LR
    subgraph Client ["Client Layer"]
        BROWSER["Browser / curl\n:3001 (future)\nor direct :8001"]
    end

    subgraph Gateway ["HTTP Gateway\nFastAPI :8001"]
        MW["Middleware stack\n(CORS → RequestContext → RateLimit → Audit)"]
        AUTH_API["POST /api/v1/auth/login"]
        RESEARCH_API["POST /api/v1/research\nGET /api/v1/research/{id}\nGET /api/v1/research/{id}/events"]
        OTHER_API["Browse API\nDocuments API\nGraph API\nMemory API\nHealth API"]
    end

    subgraph WorkerThread ["Background Thread\n(FastAPI BackgroundTasks)"]
        SVC["research_service.py\nstart_research()"]
        TRACER["WorkflowTracer\npersist_fn"]
        WORKFLOW["LangGraph\nbuild_graph().invoke()"]
        NODES["14 Node Functions"]
    end

    subgraph DataLayer ["Data Layer"]
        SQLITE["SQLite / Postgres\nresearch_sessions\nworkflow_events\ndocuments\nincidents\n..."]
        VECTOR["MemoryVectorStore\n(or Qdrant)"]
        GRAPH_STORE["MemoryGraphStore\n(or Neo4j)"]
        REDIS["fakeredis / Redis\n(conversation memory,\nrate limiting)"]
    end

    BROWSER -->|"JWT Bearer"| MW
    MW --> AUTH_API
    MW --> RESEARCH_API
    MW --> OTHER_API

    RESEARCH_API -->|"202 + session_id"| BROWSER
    RESEARCH_API -->|"BackgroundTasks"| SVC

    SVC --> TRACER
    SVC --> WORKFLOW
    TRACER -->|"persist_fn"| SQLITE
    WORKFLOW --> NODES
    NODES -->|"retrieve()"| VECTOR
    NODES -->|"retrieve()"| GRAPH_STORE
    NODES -->|"retrieve()"| SQLITE
    SVC -->|"UPDATE research_sessions"| SQLITE

    BROWSER -->|"poll GET /{id}"| RESEARCH_API
    RESEARCH_API --> SQLITE
```

---

## Request Threading Model

One of Phase 12's most important design decisions is **how long work is handled without blocking the web server**.

```mermaid
sequenceDiagram
    participant B as Browser
    participant W as Web Server (main thread)
    participant BG as Background Thread
    participant DB as Database

    B->>W: POST /api/v1/research
    W->>DB: INSERT research_sessions (status=running)
    W-->>B: 202 {session_id}  ← immediate

    Note over W,BG: Web server hands off to background
    W->>BG: start_research(session_id)

    loop Workflow executes (7-30s)
        BG->>DB: INSERT workflow_events (each node)
    end

    BG->>DB: UPDATE research_sessions (status=completed)

    loop Browser polls every 2s
        B->>W: GET /api/v1/research/{id}
        W->>DB: SELECT research_sessions
        W-->>B: {status: "running" | "completed"}
    end
```

**Why this matters for infrastructure:** The web server thread is never blocked waiting for AI. This means:
- One web server process can handle many concurrent research requests
- Each research run uses a separate background thread
- In production, this would be replaced with a proper worker queue (Celery, Redis Queue, or LangGraph's checkpoint-postgres)

---

## Database Write Pattern After Phase 12

Each node in the workflow writes to the database via the tracer:

```mermaid
flowchart LR
    NODE["Any node function\n(e.g. analyze_query)"] -->|"calls persist_fn"| TRACER["WorkflowTracer"]
    TRACER -->|"opens DB session"| SESSION["SQLAlchemy Session"]
    SESSION -->|"INSERT"| WE[("workflow_events\n{session_id, node,\nevent_type, payload,\nduration_ms}")]
    SESSION -->|"commit"| CLOSE["close session"]
```

**One session per event** — the tracer opens and closes a database session for each node. This avoids holding a long-lived session across the entire workflow run, which would cause locking issues under SQLite.

---

## Health Check Coverage After Phase 12

```mermaid
graph TD
    READY["GET /health/ready"]
    READY --> DB_CHECK["database ✓\n(SQLite connection)"]
    READY --> REDIS_CHECK["redis ✓\n(fakeredis ping)"]
    READY --> VECTOR_CHECK["vector_store ✓\n(MemoryVectorStore)"]
    READY --> GRAPH_CHECK["graph_store ✓\n(MemoryGraphStore)"]
    READY --> LLM_CHECK["llm ✓\n(fake provider)"]
    READY --> APP_CHECK["app ✓\n(fastapi)"]
```

All five store types are checked on startup. If any store is `degraded` (e.g., Neo4j is down), the system still starts but reports `degraded` on the health endpoint. The workflow continues — a failed store records an error on the sub-question instead of crashing.

---

## Development vs Production Wiring

```mermaid
graph TD
    subgraph Development ["Development (make demo / make test)"]
        DEV_DB["SQLite\ndata/enterprise.db"]
        DEV_VEC["MemoryVectorStore\n(in-process)"]
        DEV_GRAPH["MemoryGraphStore\n(in-process)"]
        DEV_REDIS["fakeredis\n(in-process)"]
        DEV_LLM["FakeChatModel\n(no API key)"]
    end

    subgraph Production ["Production (Docker Compose)"]
        PROD_DB["Postgres / Supabase"]
        PROD_VEC["Qdrant Cloud"]
        PROD_GRAPH["Neo4j Aura"]
        PROD_REDIS["Redis"]
        PROD_LLM["OpenAI / Anthropic\n(API key required)"]
    end
```

The same application code runs in both environments. Only environment variables change (`DATABASE_URL`, `VECTOR_STORE`, `GRAPH_STORE`, `LLM_PROVIDER`). The interfaces (protocols) ensure no code changes are needed to switch from development to production stores.

---

## make demo Flow

```mermaid
flowchart TD
    MAKE["make demo\nor\npython scripts/demo.py"]
    MAKE --> INIT["init_db()\nCreate all tables"]
    INIT --> SEED["seed(session)\nLoad sample JSON data"]
    SEED --> GRAPH_SEED["seed_graph()\nBuild 85 nodes / 260 edges"]
    GRAPH_SEED --> INGEST["ingest_all()\nChunk + embed 15 documents"]
    INGEST --> BUILD["build_graph(tracer=demo_tracer)"]
    BUILD --> INVOKE["compiled.invoke(initial_state)"]
    INVOKE --> PRINT["Print node timings"]
    PRINT --> SHOW["Print answer + evidence summary"]
```

This replicates the full startup sequence that `main.py` lifespan runs in production — confirming the entire system works offline in under 10 seconds.
