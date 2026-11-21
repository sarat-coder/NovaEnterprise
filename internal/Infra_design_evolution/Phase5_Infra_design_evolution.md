# Phase 5 — Infrastructure Design Evolution: API Contract and Browse API

---

## Overview

Phase 5 is primarily a **contract and routing** phase — no new infrastructure components are
introduced. What changes is the routing table inside the FastAPI process and the addition of two
documentation files on disk. The external topology (SQLite, fakeredis, FakeLLM) is unchanged.

---

## Component Wiring

```mermaid
flowchart LR
    subgraph Developer Machine
        direction TB
        subgraph Process: FastAPI :8001
            MAIN[main.py create_app]
            MW[Middleware Stack\nCORS → RequestID → RateLimit → Audit]
            R_HEALTH[Router: /health]
            R_AUTH[Router: /api/v1/auth]
            R_CUSTOMERS[Router: /api/v1/customers ✨NEW]
            R_INCIDENTS[Router: /api/v1/incidents ✨NEW]
            R_DECISIONS[Router: /api/v1/decisions ✨NEW]
            MAIN --> MW --> R_HEALTH & R_AUTH & R_CUSTOMERS & R_INCIDENTS & R_DECISIONS
        end
        DB[(SQLite\ndata/enterprise.db)]
        FAKE_REDIS[fakeredis in-process]
        FAKE_LLM[FakeLLM in-process]
    end
    Browser -->|HTTP + JWT| FastAPI
    R_CUSTOMERS & R_INCIDENTS & R_DECISIONS --> DB
```

---

## Router Registration Sequence

```mermaid
sequenceDiagram
    participant M as main.py
    participant F as FastAPI app
    participant R as Router Registry

    M->>F: create_app()
    F->>F: add middleware stack
    M->>R: include_router(health_router)      /health/*
    M->>R: include_router(auth_router)        /api/v1/auth/*
    M->>R: include_router(customers_router)   /api/v1/customers, /{id}
    M->>R: include_router(incidents_router)   /api/v1/incidents, /{id}
    M->>R: include_router(decisions_router)   /api/v1/decisions, /{id}
```

---

## Request Lifecycle — Browse Endpoint

```mermaid
sequenceDiagram
    participant B as Browser
    participant MW as Middleware Stack
    participant RT as Browse Router
    participant SEC as JWT check
    participant REPO as Repository
    participant DB as SQLite

    B->>MW: GET /api/v1/incidents
    MW->>RT: (passes X-Request-ID, rate-limit token, audit log)
    RT->>SEC: Depends(get_current_user) — decode JWT
    SEC-->>RT: UserContext {role: viewer}
    RT->>REPO: IncidentRepository.get_all()
    REPO->>DB: SELECT * FROM incidents
    DB-->>REPO: ORM list
    REPO-->>RT: list[Incident]
    RT-->>B: 200 JSON  X-Request-ID: uuid
```

**Short-circuit paths:**
- No token → middleware passes, `get_current_user` raises 401 before any DB work
- Rate limit hit → `RateLimitMiddleware` returns 429 before the router is reached

---

## Dependency Injection Graph

```mermaid
flowchart TD
    REQ[HTTP Request] -->|Depends| GCU[get_current_user\njwt decode]
    REQ -->|Depends| GDB[get_db\nSQLAlchemy Session]
    GCU --> UC[UserContext]
    GDB --> SESSION[Session]
    UC & SESSION --> HANDLER[Route handler]
    HANDLER --> REPO[Repository]
    REPO --> SESSION
```

The session commits on success and rolls back on error inside `get_db`'s `finally` block.

---

## Pydantic Schema Bridge

```mermaid
flowchart LR
    ORM[SQLAlchemy ORM\nIncident / Customer / Decision] -->|model_validate\nfrom_attributes=True| SCHEMA[Pydantic Schema\nIncidentOut / CustomerOut / DecisionOut]
    SCHEMA -->|FastAPI serialises| JSON[HTTP JSON Response]
```

---

## What Has Not Changed

| Component | Status |
|-----------|--------|
| SQLite database | Unchanged — no schema changes |
| fakeredis | Unchanged |
| FakeLLM / FakeEmbeddings | Unchanged — no AI calls in browse endpoints |
| Middleware stack | Unchanged — browse requests flow through it |
| Health check registry | Unchanged — no new checks registered |
