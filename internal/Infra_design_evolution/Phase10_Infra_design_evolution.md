# Phase 10 — Memory: Infrastructure and Component Wiring

## Overview

Phase 10 adds the memory layer. From an infrastructure perspective, it introduces two new types of data flow:

1. **Redis** (or `fakeredis`) is now used not just for rate limiting (Phase 3) but also for **conversation memory**.
2. The **`memory_records` table** in SQLite/PostgreSQL (which was created in Phase 2 but unused) is now actively read and written by the memory service.

No new services are added. The memory layer wires into existing components.

---

## Component map after Phase 10

```mermaid
graph TD
    subgraph Client
        Browser["Browser<br/>Next.js :3001<br/>(Phase 13)"]
    end

    subgraph Backend [FastAPI :8001]
        Main["main.py<br/>+ memory_router"]
        MemAPI["api/memory.py<br/>GET /organizational<br/>GET /organizational/quarter<br/>GET/POST/DELETE /notes"]
        MemService["memory/memory_service.py"]
        OrgScope["memory/scopes/organizational.py"]
        ConvScope["memory/scopes/conversation.py"]
        SessScope["memory/scopes/session.py"]
        AnaScope["memory/scopes/analyst.py"]
    end

    subgraph Storage
        OrgFile["sample_data/<br/>organizational_memory.json<br/>(read-only)"]
        Redis[(Redis / fakeredis<br/>conv:{session_id} lists)]
        SQLite[(SQLite / PostgreSQL<br/>memory_records table)]
    end

    Browser -->|JWT| Main
    Main --> MemAPI
    MemAPI --> MemService
    MemService --> OrgScope --> OrgFile
    MemService --> ConvScope --> Redis
    MemService --> SessScope --> SQLite
    MemService --> AnaScope --> SQLite
```

---

## Redis wiring for conversation memory

Redis was introduced in Phase 3 for rate limiting. Phase 10 reuses the same `get_redis_client()` function for conversation memory, adding a second usage pattern.

```mermaid
graph LR
    App["FastAPI backend"] -->|get_redis_client()| RedisClient["redis.Redis or<br/>fakeredis.FakeRedis"]

    RedisClient -->|RPUSH conv:sess-X turn| ConvList["Redis list<br/>key: conv:{session_id}"]
    RedisClient -->|LRANGE conv:sess-X 0 -1| ConvList
    RedisClient -->|EXPIRE conv:sess-X 86400| ConvList

    RedisClient -->|INCR + EXPIRE| RateLimit["rate_limit:{ip}<br/>(Phase 3)"]

    style ConvList fill:#ef9a9a
    style RateLimit fill:#ef9a9a
```

**Key naming**:
- Rate limit: `rate_limit:{client_ip}` — integer counter, TTL 60s
- Conversation: `conv:{session_id}` — JSON list, TTL 86400s (24h)

There is no collision between these key namespaces.

---

## Fakeredis for offline development

When `REDIS_URL` is empty (the default in `.env.example`), both rate limiting and conversation memory fall back to `fakeredis.FakeRedis`:

```mermaid
graph TD
    Config["REDIS_URL=<empty>"]
    Config -->|"empty → fakeredis"| FakeRedis["fakeredis.FakeRedis<br/>in-memory, no server needed"]
    FakeRedis -->|same API| RateLimit["Rate limit (Phase 3)"]
    FakeRedis -->|same API| ConvMemory["Conversation memory (Phase 10)"]

    RealRedis["REDIS_URL=redis://..."] -->|redis.Redis| RateLimit
    RealRedis -->|redis.Redis| ConvMemory
```

This means `make test` and `make demo` require **zero external services** — a core constraint of the project (N1).

---

## Database wiring for session and analyst memory

The `memory_records` table was defined in Phase 2 as part of `MemoryRecord` (in `backend/app/models/research.py`). Phase 10 is the first phase to actually write to it.

```mermaid
graph TD
    ResearchWorkflow["Research Workflow<br/>(Phase 11/12)"] -->|upsert_session_fact| SessScope
    AnalystAPI["POST /api/v1/memory/notes"] -->|upsert| AnaScope

    SessScope["memory/scopes/session.py"] -->|INSERT/UPDATE WHERE scope='session'| DB
    AnaScope["memory/scopes/analyst.py"] -->|INSERT/UPDATE WHERE scope='analyst'| DB

    DB[(memory_records table<br/>SQLite/PostgreSQL)]

    DB -->|SELECT WHERE scope='analyst' AND owner_id=user_id| AnaScope
    DB -->|SELECT WHERE scope='session' AND owner_id=session_id| SessScope
```

The `scope` and `owner_id` columns act as the namespace. A single `SELECT` query with these filters is all that's needed to isolate one analyst's notes from another's.

---

## Import and dependency wiring

The memory package lives in `memory/` at the repo root (the same level as `backend/`, `rag/`, `agents/`). It follows the same PYTHONPATH convention: `PYTHONPATH=backend;.`

```mermaid
graph TD
    MemAPI["backend/app/api/memory.py"]
    MemService["memory/memory_service.py"]
    OrgScope["memory/scopes/organizational.py"]
    ConvScope["memory/scopes/conversation.py"]
    SessScope["memory/scopes/session.py"]
    AnaScope["memory/scopes/analyst.py"]
    Model["backend/app/models/research.py<br/>MemoryRecord"]
    DB["backend/app/core/db.py"]
    Security["backend/app/core/security.py"]

    MemAPI --> MemService
    MemAPI --> Model
    MemAPI --> DB
    MemAPI --> Security
    MemService --> OrgScope
    MemService --> ConvScope
    MemService --> SessScope
    MemService --> AnaScope
    SessScope --> Model
    AnaScope --> Model
```

The `memory/` package imports from `app.models` (via PYTHONPATH) but **never from `app.api` or `app.services`** — keeping the layering rule: memory is a leaf layer alongside `rag/` and `agents/`.

---

## Request flow: analyst adds a personal note

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as POST /api/v1/memory/notes
    participant Sec as security.py
    participant AnaScope as analyst.py scope
    participant DB as memory_records (SQLite)

    UI->>API: POST {key: "preference.format", value: "bullets"} + Bearer JWT
    API->>Sec: require_role(ANALYST)
    Sec-->>API: UserContext {user_id: "analyst"}
    API->>AnaScope: upsert(db, "analyst", "preference.format", "bullets")
    AnaScope->>DB: SELECT WHERE scope='analyst' AND owner_id='analyst' AND key='preference.format'
    DB-->>AnaScope: None (new record)
    AnaScope->>DB: INSERT memory_records (id=uuid, scope='analyst', owner_id='analyst', ...)
    DB-->>AnaScope: MemoryRecord
    AnaScope-->>API: MemoryRecord
    API-->>UI: 201 {id: "...", key: "preference.format", scope: "analyst", ...}
```

---

## Request flow: organizational quarter resolution

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as GET /api/v1/memory/organizational/quarter
    participant OrgScope as organizational.py scope
    participant JSON as organizational_memory.json

    UI->>API: GET + Bearer JWT (viewer or above)
    API->>OrgScope: resolve_quarter("last quarter")
    OrgScope->>JSON: read fiscal_calendar.quarters (lru_cached)
    JSON-->>OrgScope: Q1-Q4 month definitions
    OrgScope-->>API: {quarter: "Q3", start_date: "2026-07-01", end_date: "2026-09-30", year: 2026}
    API-->>UI: 200 {quarter: "Q3", start_date: ..., end_date: ..., label: "July – September"}
```

The JSON is loaded once at first call and cached for the lifetime of the process — no disk reads after startup.

---

## Production infrastructure note

| Component | Dev / test (default) | Production option |
|---|---|---|
| Conversation memory | `fakeredis` in-process | Redis or Redis Cluster |
| Session + analyst memory | SQLite `memory_records` | PostgreSQL `memory_records` |
| Organizational memory | JSON file on disk | Same (it's static config) |

No environment variable changes are needed to switch — `REDIS_URL` and `DATABASE_URL` already control the backing stores from Phase 2 and Phase 3.
