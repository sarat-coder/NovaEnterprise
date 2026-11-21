# Phase 5 — Infrastructure Design Evolution: API Contract and Browse API

---

## Overview

Phase 5 is primarily a **contract and routing** phase — no new infrastructure components are
introduced. What changes is the routing table inside the FastAPI process and the addition of
two documentation files that sit on disk. The infrastructure diagram is the same as Phase 4,
but the FastAPI router tree grows.

---

## Component Wiring (unchanged from Phase 4)

```mermaid
flowchart LR
    subgraph Developer Machine
        direction TB
        subgraph Process: FastAPI :8001
            MAIN[main.py\ncreate_app]
            MW[Middleware Stack\nCORS → RequestID → RateLimit → Audit]
            R_HEALTH[Router: /health]
            R_AUTH[Router: /api/v1/auth]
            R_CUSTOMERS[Router: /api/v1/customers ✨]
            R_INCIDENTS[Router: /api/v1/incidents ✨]
            R_DECISIONS[Router: /api/v1/decisions ✨]
            MAIN --> MW --> R_HEALTH & R_AUTH & R_CUSTOMERS & R_INCIDENTS & R_DECISIONS
        end

        DB[(SQLite\ndata/enterprise.db)]
        FAKE_REDIS[fakeredis\nin-process]
        FAKE_LLM[FakeLLM\nin-process]
    end

    Browser -->|HTTP + JWT| FastAPI
    R_CUSTOMERS & R_INCIDENTS & R_DECISIONS --> DB
    R_AUTH --> FAKE_REDIS
    MAIN --> FAKE_LLM
```

✨ = new in Phase 5

---

## Router Registration Flow

When `create_app()` runs, FastAPI builds its routing table in a single pass. The order of
`include_router()` calls determines URL priority (earlier = higher priority for conflicting paths).

```mermaid
sequenceDiagram
    participant M as main.py
    participant F as FastAPI app
    participant MW as Middleware
    participant R as Router Registry

    M->>F: create_app()
    F->>MW: add CORSMiddleware
    F->>MW: add RequestContextMiddleware
    F->>MW: add RateLimitMiddleware
    F->>MW: add AuditMiddleware
    M->>R: include_router(health_router)      /health, /health/live, /health/ready
    M->>R: include_router(auth_router)        /api/v1/auth/...
    M->>R: include_router(customers_router)   /api/v1/customers, /api/v1/customers/{id}
    M->>R: include_router(incidents_router)   /api/v1/incidents, /api/v1/incidents/{id}
    M->>R: include_router(decisions_router)   /api/v1/decisions, /api/v1/decisions/{id}
```

---

## Request Lifecycle — Browse Endpoint

Every browse request passes through all middleware layers before reaching the router.

```mermaid
sequenceDiagram
    participant B as Browser
    participant CORS as CORSMiddleware
    participant RID as RequestContextMiddleware
    participant RL as RateLimitMiddleware
    participant AUD as AuditMiddleware
    participant RT as Router (customers/incidents/decisions)
    participant SEC as get_current_user (JWT check)
    participant REPO as Repository
    participant DB as SQLite

    B->>CORS: GET /api/v1/incidents
    CORS->>RID: forward (adds / echoes X-Request-ID)
    RID->>RL: forward (checks token bucket in fakeredis)
    RL->>AUD: forward
    AUD->>RT: forward
    RT->>SEC: Depends(get_current_user) — decode JWT
    SEC-->>RT: UserContext {role: viewer}
    RT->>REPO: IncidentRepository(session).get_all()
    REPO->>DB: SELECT * FROM incidents
    DB-->>REPO: ORM objects
    REPO-->>RT: list[Incident]
    RT-->>B: 200 JSON  X-Request-ID: <uuid>
```

**Rate limit path (429):** RateLimitMiddleware returns before reaching the router — the JWT
check and the repository query never run.

**No token (401):** `get_current_user` raises `HTTPException(401)` before any database work.

---

## Dependency Injection Graph (Browse Endpoints)

FastAPI's DI system wires three dependencies automatically for each request:

```mermaid
flowchart TD
    REQ[HTTP Request] --> |Depends| GCU[get_current_user\njwt decode]
    REQ --> |Depends| GDB[get_db\nSQLAlchemy Session]
    GCU --> UC[UserContext]
    GDB --> SESSION[Session]
    UC & SESSION --> HANDLER[Route handler\nlist_incidents / get_incident / ...]
    HANDLER --> REPO[Repository\n.get_all() / .get_by_id()]
    REPO --> SESSION
```

The session is committed (or rolled back on error) in `get_db`'s `finally` block. The router
never touches the session lifecycle directly.

---

## Pydantic Schema Layer

```mermaid
flowchart LR
    ORM[SQLAlchemy ORM object\nIncident / Customer / Decision] -->|model_validate\nfrom_attributes=True| SCHEMA[Pydantic Schema\nIncidentOut / CustomerOut / DecisionOut]
    SCHEMA -->|.model_dump\nautomatically by FastAPI| JSON[HTTP JSON Response]
```

`model_config = {"from_attributes": True}` on each schema tells Pydantic to read ORM object
attributes as if they were dict fields. This avoids manual field mapping and means the ORM
model is the single source of field names.

---

## Documentation Files on Disk

```mermaid
flowchart LR
    docs/API_CONTRACT.md -->|read by| Frontend[Next.js typed API client\nPhase 13]
    docs/API_CONTRACT.md -->|read by| BackendDevs[Backend developers\nwhen adding endpoints]
    docs/FRONTEND_ASSUMPTIONS.md -->|read by| Frontend
    docs/FRONTEND_ASSUMPTIONS.md -->|read by| UIDevs[UI developers\nfor polling and node IDs]
```

These are static Markdown files — no runtime component. They are enforced by the test
`test_graph_shape_matches_frontend_assumptions` (Phase 12) which will verify the node IDs
in `FRONTEND_ASSUMPTIONS.md` against the actual `GRAPH_NODES` list.

---

## What Has Not Changed

| Component | Status |
|-----------|--------|
| SQLite database | Same — no schema changes |
| fakeredis | Same — rate limit and audit unchanged |
| FakeLLM / FakeEmbeddings | Same — no AI calls in browse endpoints |
| Middleware stack | Same — browse requests flow through it like any other |
| Health check registry | Same — no new checks registered |

The only infrastructure change is **inside the FastAPI process**: three new routers registered
and two new files written to disk.
