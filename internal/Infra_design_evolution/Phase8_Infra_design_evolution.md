# Phase 8 — Infrastructure Design Evolution: SQL Retrieval

> Component wiring, data flow, and infrastructure topology for the SQL retrieval layer.
> Each section explains what was added, how it connects to existing components, and why.

---

## Infrastructure state entering Phase 8

By the end of Phase 7, the running system had these components:

```mermaid
graph LR
    Browser -->|HTTPS :3001| NextJS[Next.js 15\nFrontend]
    NextJS -->|REST /api/v1| FastAPI[FastAPI\n:8001]
    FastAPI --> SQLite[(SQLite\ndata/enterprise.db)]
    FastAPI --> MemVec[In-Memory\nVector Store]
    FastAPI --> MemGraph[In-Memory\nGraph Store]
    FastAPI --> FakeRedis[FakeRedis\ncache + rate limit]
    FastAPI --> FakeLLM[Fake LLM\noffline provider]
```

SQLite was already present — it stores teams, services, incidents, customers, decisions, and all entity data. Phase 8 does not add a new data store; it adds a **new access path** to the existing SQLite (or PostgreSQL in production).

---

## What Phase 8 adds to the infrastructure

Phase 8 adds the SQL retrieval module as a new code-layer component. At the infrastructure level, this means:

- A new Python module (`rag/sql_retrieval.py`) that **reads** from the relational database.
- It uses the existing `get_db()` SQLAlchemy session factory — no new database connection pool.
- An in-process `RecordedQuery` store (a Python list) that acts as a lightweight audit buffer during a research session.

```mermaid
graph LR
    subgraph Backend Process :8001
        Agent[Research Agent\nagents/]
        SqlRet[SQL Retriever\nrag/sql_retrieval.py]
        Validator[validate_sql\n7-rule gate]
        Templates[QUERY_TEMPLATES\n5 pre-approved queries]
        Recorder[RecordedQuery Store\nin-process list]
        SessionFactory[get_db\nSQLAlchemy session]
    end

    subgraph Data
        SQLite[(SQLite\nenterprise.db)]
    end

    Agent -->|template_name + params| SqlRet
    SqlRet --> Validator
    SqlRet --> Templates
    SqlRet --> SessionFactory
    SessionFactory --> SQLite
    SqlRet --> Recorder
    SqlRet -->|Evidence items| Agent
```

---

## Component wiring: how data flows through the SQL retrieval path

### Step-by-step for the canonical question sub-question "what incidents occurred?"

```mermaid
sequenceDiagram
    participant RA as Research Agent
    participant SR as SqlRetriever
    participant V  as validate_sql()
    participant T  as QUERY_TEMPLATES
    participant DB as SQLAlchemy Session
    participant SQ as SQLite (enterprise.db)
    participant RQ as RecordedQuery Store

    RA->>T: Look up "incidents_by_service_and_date"
    T-->>SR: SQL template string
    SR->>V: validate(template with placeholders substituted)
    V-->>SR: Passes all 7 rules
    SR->>DB: session.execute(text(sql), params)
    DB->>SQ: SELECT ... FROM incidents JOIN services WHERE ...
    SQ-->>DB: Rows: [INC-2031, INC-2044]
    DB-->>SR: ResultProxy
    SR->>RQ: append(RecordedQuery{uuid, sql, params, rows, ts})
    SR-->>RA: [Evidence(sql-uuid-0), Evidence(sql-uuid-1)]
```

---

## Validator as a firewall component

The validator is best understood as an **application-layer firewall** that sits between the AI agent and the database.

```mermaid
graph LR
    Agent[AI Agent\n"write any SQL?"] -->|proposed SQL| Gate{validate_sql\n7 rules}
    Gate -->|PASS| DB[(Database)]
    Gate -->|FAIL| ERR[SqlValidationError\nquery rejected]

    style Gate fill:#f90,color:#000
    style ERR fill:#f33,color:#fff
    style DB fill:#393,color:#fff
```

The validator is stateless — it only inspects the SQL string, with no network calls, no database connection, and no side effects. This means it runs in milliseconds and is easy to unit-test in isolation.

**Rules enforced:**

```mermaid
flowchart TD
    IN[Input SQL] --> C1{Not empty?}
    C1 -->|fail| E1[❌ Empty statement]
    C1 -->|pass| C2{No -- comments?}
    C2 -->|fail| E2[❌ Inline comment]
    C2 -->|pass| C3{No block comments?}
    C3 -->|fail| E3[❌ Block comment]
    C3 -->|pass| C4{No semicolons?}
    C4 -->|fail| E4[❌ Multiple statements]
    C4 -->|pass| C5{Starts with SELECT?}
    C5 -->|fail| E5[❌ Not a SELECT]
    C5 -->|pass| C6{No forbidden keywords?}
    C6 -->|fail| E6[❌ DDL/DML keyword]
    C6 -->|pass| C7{All tables allowlisted?}
    C7 -->|fail| E7[❌ Unknown table]
    C7 -->|pass| OK[✅ Validated]
```

---

## Template registry as a configuration component

The `QUERY_TEMPLATES` dictionary is a **static registry** loaded at module import time. It is validated once at startup. No runtime configuration is needed.

```mermaid
graph TD
    subgraph Module Load time
        Import[import rag.sql_retrieval] --> TReg[QUERY_TEMPLATES dict\n5 entries]
        TReg --> BootVal[validate_sql each template\nat import time]
        BootVal -->|any fail| Crash[RuntimeError\napp refuses to start]
        BootVal -->|all pass| Ready[Module ready]
    end

    subgraph Runtime
        Agent --> TReg
        TReg -->|template SQL| Val[validate_sql again]
        Val --> DB[(Database)]
    end
```

The double-validation (at import + at runtime) means template SQL is checked **twice**. This is an intentional redundancy: it catches developer mistakes early and defends against hypothetical template mutation at runtime.

---

## RecordedQuery store: in-process vs. persistent

In Phase 8 the recorded query store is a Python list in memory:

```mermaid
graph LR
    subgraph Backend process
        SR[SqlRetriever] -->|append| RQS[_recorded_queries\nin-process list]
        RQS -->|read| EVT[GET /research/id/events\nreturns query text]
    end
```

**Production evolution (Phase 12+):** When the research service persists agent state to the database after every node, recorded queries will be serialised as part of the session's event log. The in-process list is a stepping stone that keeps Phase 8 fully self-contained.

---

## Database access: same session factory, new consumer

Phase 8 reuses the SQLAlchemy session factory already wired up in `backend/app/core/db.py`. The SQL retriever receives a session as a constructor argument (`SqlRetriever(db_session=session)`), keeping it testable:

- In production: a real `Session` from `get_db()`.
- In tests and the offline demo: `None` → returns empty rows, still records the query.

```mermaid
graph TD
    subgraph Test / Offline
        TA[Test / Offline Agent] --> SR1[SqlRetriever\ndb_session=None]
        SR1 -->|empty rows| EV1[Evidence: "returned no results"]
    end

    subgraph Production
        PA[Production Agent] --> SR2[SqlRetriever\ndb_session=Session]
        SR2 --> SL[(SQLite / PostgreSQL)]
        SL --> EV2[Evidence with real rows]
    end
```

This pattern — inject the session, default to None — is the same approach used by the repositories layer in Phase 2.

---

## Full infrastructure view after Phase 8

```mermaid
graph TD
    Browser -->|:3001| NextJS
    NextJS -->|/api/v1| FastAPI

    subgraph FastAPI :8001
        API[api/\nrouters]
        SVC[services/\norchestration]
        REPO[repositories/\nSQLAlchemy]
        AGENT[agents/\nresearch workflow]
        VRAG[rag/retriever.py\nvector + BM25 + RRF]
        GRAG[rag/graph_store.py\ngraph traversals]
        SRAG[rag/sql_retrieval.py\nvalidator + templates + recorder]
    end

    subgraph Data Stores
        SQLite[(SQLite\nenterprise.db)]
        MemVec[(In-Memory\nVector Store)]
        MemGraph[(In-Memory\nGraph Store)]
        FakeRedis[(FakeRedis)]
        FakeLLM[(Fake LLM)]
    end

    API --> SVC --> AGENT
    REPO --> SQLite
    AGENT --> VRAG --> MemVec
    AGENT --> GRAG --> MemGraph
    AGENT --> SRAG --> SQLite
    SVC --> REPO
    FastAPI --> FakeRedis
    FastAPI --> FakeLLM
```

The key observation: the SQL retriever and the repository layer both access SQLite, but through different channels:
- **Repositories** are used by the API services layer for CRUD operations (Phase 2).
- **SQL retriever** is used by the agent for research queries — it is read-only and query-validated.

They share the same underlying database but serve different purposes and are kept in separate modules.

---

## Offline / CI infrastructure

No new infrastructure components are required for Phase 8 to run offline:

| Component | Phase 8 state |
|---|---|
| SQLite | Already present from Phase 2 |
| SQLAlchemy | Already a dependency |
| `rag/sql_retrieval.py` | New pure-Python module, no external deps |
| `RecordedQuery` store | In-process Python list |
| Test runner | `pytest` with `PYTHONPATH=backend` |

`make test` and `ruff check` are the only commands needed. No Docker, no network, no API key.
