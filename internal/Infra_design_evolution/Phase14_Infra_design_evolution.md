# Phase 14 — Infrastructure and Component Wiring Evolution

## Overview

Phase 14 adds no new infrastructure components. The same five services that Phase 13 wired remain:

| Service | Port | Technology |
|---------|------|-----------|
| Next.js frontend | 3001 | Node.js / React |
| FastAPI backend | 8001 | Python / uvicorn |
| SQLite (or Postgres) | — | File / TCP |
| Memory vector store (or Qdrant) | — | In-process |
| Memory graph store (or Neo4j) | — | In-process |

What Phase 14 adds is **wire coverage** — more paths between the frontend and backend are now actively used. This section shows those paths.

---

## Component wiring map — Phase 13 vs Phase 14

```mermaid
graph LR
    subgraph "Browser"
        P_Login["/login"]
        P_Browse["/customers\n/incidents\n/decisions"]
        P_Search["/search"]
        P_Research["/research/[id]"]
        P_KG["/knowledge-graph"]
        P_Docs["/documents"]
    end

    subgraph "Next.js :3001"
        Client["API client\nfetch + JWT header"]
        Rewrites["next.config rewrites\n/api/v1/* → :8001"]
    end

    subgraph "FastAPI :8001"
        Auth["/auth/login\n/auth/me"]
        Browse["/customers\n/incidents\n/decisions"]
        Research["/research (POST)\n/research/{id} (GET)\n/research/{id}/events"]
        Graph["/graph/stats\n/graph/nodes\n/graph/nodes/{id}\n/graph/nodes/{id}/neighbors\n/graph/cypher"]
        Docs["/documents\n/documents/upload\n/documents/{id} DELETE\n/approvals"]
        Health["/health/ready"]
    end

    P_Login --> Client --> Auth
    P_Browse --> Client --> Browse
    P_Search --> Client --> Research
    P_Research --> Client --> Research
    P_KG --> Client --> Graph
    P_Docs --> Client --> Docs
    Client --> Rewrites --> FastAPI

    classDef new fill:#bbf7d0,stroke:#16a34a
    class P_KG,P_Docs,Graph,Docs new
```

Green nodes = new paths activated in Phase 14.

---

## Request routing detail

### How the browser reaches the backend

The Next.js config rewrites proxy rules so the browser only ever speaks to `:3001`. The backend lives on `:3001/api/v1/*` as far as the browser is concerned.

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js :3001
    participant F as FastAPI :8001

    B->>N: GET /api/v1/graph/stats
    Note over N: next.config rewrite rule matches /api/v1/:path*
    N->>F: GET http://localhost:8001/api/v1/graph/stats
    F-->>N: {"node_count": 85, "edge_count": 260}
    N-->>B: same JSON + X-Request-ID header
```

This proxy means:
- No CORS headers needed on the backend for the browser
- The browser cannot directly address `:8001` — all traffic goes through Next.js
- In production, Next.js is replaced by a reverse proxy (nginx / Vercel edge) with the same rewrite

---

## New API surfaces activated in Phase 14

### Knowledge graph endpoints

```mermaid
sequenceDiagram
    participant UI as /knowledge-graph page
    participant API as FastAPI /graph

    UI->>API: GET /graph/stats
    API-->>UI: {node_count, edge_count}

    UI->>API: GET /graph/nodes?label=Service&limit=100
    API-->>UI: GraphNode[]

    UI->>API: GET /graph/nodes/{id}/neighbors?direction=both
    API-->>UI: {node, neighbors[], edges[]}

    opt analyst only
        UI->>API: POST /graph/cypher {cypher, params}
        API-->>UI: {rows[], row_count, cypher}
    end
```

### Document upload endpoint (multipart)

The upload path is special: it must NOT send `Content-Type: application/json` because the browser needs to set a multipart boundary automatically. The API client handles this:

```mermaid
sequenceDiagram
    participant UI as /documents page
    participant Client as api-client.ts
    participant API as FastAPI /documents/upload

    UI->>Client: documentsApi.upload(file)
    Note over Client: Creates FormData\nSets Authorization header\nDoes NOT set Content-Type
    Client->>API: POST /api/v1/documents/upload\n  Authorization: Bearer <jwt>\n  Content-Type: multipart/form-data; boundary=...
    API-->>Client: 201 DocumentUploadResponse
    Client-->>UI: {doc_id, chunk_count, flagged}
```

### Delete request → approval flow

```mermaid
sequenceDiagram
    participant UI as /documents page
    participant API as FastAPI
    participant DB as SQLite

    UI->>API: DELETE /api/v1/documents/{id}
    API->>DB: INSERT approval_requests
    API-->>UI: 202 ApprovalRequest {id, status:"pending"}
    Note over UI: Shows "awaiting admin approval"
    Note over DB: Document status still "indexed"

    opt Admin approves later
        API->>DB: UPDATE approval_requests status=approved\nUPDATE documents status=deleted
    end
```

---

## Runtime data flow — full research session

```mermaid
sequenceDiagram
    participant UI as /research/[id]
    participant API as FastAPI
    participant BG as Background task
    participant Stores as SQLite + VectorStore + GraphStore

    UI->>API: POST /research {question}
    API-->>UI: 202 {session_id}
    API->>BG: start research(session_id) [BackgroundTasks]

    loop every 2 seconds
        UI->>API: GET /research/{session_id}
        API->>Stores: SELECT research_sessions WHERE id=...
        Stores-->>API: ResearchSession (partial state)
        API-->>UI: JSON with status, sub_questions, evidence built so far

        UI->>API: GET /research/{session_id}/events
        API->>Stores: SELECT workflow_events WHERE session_id=...
        Stores-->>API: WorkflowEvent[]
        API-->>UI: timeline rows
    end

    BG->>Stores: persist after every node
    Note over UI,BG: UI sees progress because DB is the shared state
```

---

## Network isolation and security wiring

```mermaid
graph TB
    subgraph "Public (browser-facing)"
        CORS_Allowed["CORS: localhost:3001 only\n(CORS_ORIGINS env var)"]
    end

    subgraph "Frontend :3001"
        SessionStorage["sessionStorage\nJWT + role\n(cleared on tab close)"]
        AuthHeader["Authorization: Bearer <jwt>\ninjected by api-client.ts"]
    end

    subgraph "Backend :8001"
        JWTVerify["JWT verify\nrequire_role()"]
        RateLimit["Redis token bucket\n120 req/min"]
        AuditLog["Audit middleware\nstate-changing requests"]
        ReadOnly["SQL validator\nCypher read-only guard"]
    end

    SessionStorage -->|read by| AuthHeader
    AuthHeader -->|every request| JWTVerify
    JWTVerify -->|403 if wrong role| ResponseError["403 Forbidden"]
    JWTVerify -->|pass| RateLimit
    RateLimit -->|429 if exceeded| ResponseError429["429 Too Many Requests"]
    RateLimit -->|pass| AuditLog
    AuditLog --> ReadOnly
```

---

## Health degradation display

The `/health/ready` endpoint is polled once on page load by the health banner component. Phase 14 screens use this to show partial-availability warnings.

```mermaid
graph TD
    HB["Health Banner\n(every page)"]
    API["/health/ready"]
    HB -->|GET on mount| API
    API -->|status ok| NoWarning["No banner shown"]
    API -->|status degraded| Warning["Amber banner:\n'Some capabilities may be limited'"]
    API -->|status error| Error["Red banner:\n'Service unavailable'"]
```

---

## Infrastructure summary: Phase 14

No new services, containers, or ports were added. The changes are entirely in routing paths and wire coverage:

| New wire | Endpoint | From page |
|----------|----------|-----------|
| Graph stats | GET /graph/stats | /knowledge-graph |
| Node list | GET /graph/nodes | /knowledge-graph |
| Node expansion | GET /graph/nodes/{id}/neighbors | /knowledge-graph |
| Cypher query | POST /graph/cypher | /knowledge-graph |
| Document upload | POST /documents/upload | /documents |
| Delete request | DELETE /documents/{id} | /documents |

All backend endpoints existed since Phases 9 and 10; Phase 14 is what actually calls them from the browser.
