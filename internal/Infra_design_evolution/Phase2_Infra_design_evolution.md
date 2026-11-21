# Phase 2 — Infrastructure Design Evolution

> This document explains the infrastructure wiring added in Phase 2: how the database is
> connected, how data flows at startup, and how the components are routed.
> Phase 2 adds SQLite (local) / Postgres (production) to the stack.

---

## Phase 2 Infrastructure Overview

Phase 1 had no persistent storage — just an in-process FastAPI server. Phase 2 adds the first data store: a **relational database** that holds all domain data and research state.

In development and CI: **SQLite** (a file on disk, zero external services needed).  
In production (Supabase): **PostgreSQL** (managed cloud database with Row-Level Security).

```mermaid
graph TD
    subgraph Developer workstation
        ENV[.env file\nDATABASE_URL=sqlite:///data/enterprise.db]
        SERVER[FastAPI :8001\nuvicorn]
        DB[(SQLite\ndata/enterprise.db)]
        SD[sample_data/\nJSON + 15 docs]
    end

    SERVER -->|reads DATABASE_URL| ENV
    SERVER -->|create tables + seed| DB
    SERVER -->|reads JSON at startup| SD
    SD -->|seeds rows into| DB
```

```mermaid
graph TD
    subgraph Production - Supabase
        ENV2[.env / environment secrets\nDATABASE_URL=postgresql://...]
        SERVER2[FastAPI container\n:8001]
        PG[(Supabase Postgres\nwith RLS)]
        STG[Supabase Storage\nuploaded documents]
    end

    SERVER2 -->|reads DATABASE_URL| ENV2
    SERVER2 -->|SQLAlchemy connection pool| PG
    PG -->|enforces RLS| PG
```

---

## Component Wiring Detail

### 1. Database engine initialisation (`core/db.py`)

The database engine is created **once** at startup using an `lru_cache`d function. This prevents multiple engine instances from competing for the same SQLite file.

```mermaid
sequenceDiagram
    participant LIFESPAN as FastAPI lifespan
    participant DB as core/db.py
    participant ENGINE as SQLAlchemy Engine (singleton)
    participant SQLITE as data/enterprise.db

    LIFESPAN->>DB: init_db()
    DB->>DB: get_settings().database_url
    DB->>DB: Path(db_path).parent.mkdir() [SQLite only]
    DB->>ENGINE: create_engine(url) [lru_cache]
    ENGINE->>SQLITE: CREATE TABLE IF NOT EXISTS (16 tables)
    DB->>DB: register_check("database", health_probe)
    DB-->>LIFESPAN: tables ready
```

**Key detail:** The `get_engine()` function is wrapped in `@functools.lru_cache(maxsize=1)`. This means no matter how many times it is called (from the seed service, from repository instances, from tests), the same engine object is returned. SQLAlchemy's connection pool is managed by this single engine.

### 2. Session lifecycle (`get_db()` generator)

Each HTTP request or service call gets its own database session:

```mermaid
sequenceDiagram
    participant API as API handler
    participant GETDB as get_db() generator
    participant SESSION as SQLAlchemy Session
    participant DB as SQLite / Postgres

    API->>GETDB: FastAPI Depends(get_db)
    GETDB->>SESSION: sessionmaker().create()
    API->>SESSION: repo.get_all() etc.
    SESSION->>DB: SELECT ...
    DB-->>SESSION: rows
    SESSION-->>API: Python objects
    API-->>GETDB: request complete
    GETDB->>SESSION: session.commit()
    GETDB->>SESSION: session.close()
```

Each session is committed on success and rolled back on exception. The session is always closed in the `finally` block.

### 3. Seed service data flow

The seed service reads JSON files from `sample_data/` and writes them to the database in dependency order:

```mermaid
graph LR
    subgraph Input - sample_data/
        TJ[teams.json]
        EJ[employees.json]
        SJ[services.json]
        CJ[customers.json]
        IJ[incidents.json]
        DJ[decisions.json]
        PJ[projects.json]
        TKJ[tickets.json]
        OMJ[organizational_memory.json]
        DOCSJ[documents/*.md\n15 files]
    end

    subgraph Dependency order
        TJ -->|must exist before| EJ & SJ
        SJ -->|must exist before| IJ
        CJ -->|must exist before| IJ
        IJ -->|must exist before| DJ
        SJ -->|must exist before| PJ
        PJ -->|must exist before| TKJ
        EJ -->|must exist before| TKJ
    end

    subgraph Output - database tables
        TJ --> TEAMS[(teams)]
        EJ --> EMPS[(employees)]
        SJ --> SVCS[(services)]
        CJ --> CUSTS[(customers)]
        IJ --> INCS[(incidents)]
        IJ --> ICL[(incident_customers)]
        DJ --> DECS[(decisions)]
        DJ --> IDL[(incident_decisions)]
        PJ --> PROJS[(projects)]
        TKJ --> TICKS[(tickets)]
        OMJ --> MEM[(memory_records\nscope=organizational)]
        DOCSJ --> DOCS[(documents\nflagged=True for vendor-note)]
    end
```

### 4. Health check registration

Phase 2 adds the `database` check to the `/health/ready` registry:

```mermaid
graph LR
    LIFESPAN[FastAPI lifespan] -->|register_check app| REGISTRY[health_check_registry]
    INIT[init_db] -->|register_check database| REGISTRY

    READY[GET /health/ready] -->|run_all_checks| REGISTRY
    REGISTRY -->|app check| APP_OK[status: ok, detail: fastapi]
    REGISTRY -->|database check| DB_CHECK[SELECT 1\nstatus: ok\ndetail: sqlite / postgresql]
```

The `/health/ready` response after Phase 2:

```json
{
  "status": "ok",
  "checks": {
    "app": {"status": "ok", "detail": "fastapi"},
    "database": {"status": "ok", "detail": "sqlite"}
  }
}
```

---

## SQLite vs Postgres: environment switching

The same application code runs against both databases. The only difference is the `DATABASE_URL` environment variable:

```mermaid
graph TD
    ENV[DATABASE_URL] --> SWITCH{starts with?}
    SWITCH -->|sqlite:///| SQLITEMODE[SQLite mode\ncheck_same_thread=False\nWAL pragma\nmkdir for file]
    SWITCH -->|postgresql://| PGMODE[Postgres mode\nconnection pool\nRLS enforced by DB]
    SQLITEMODE --> ENGINE[SQLAlchemy Engine]
    PGMODE --> ENGINE
```

| Setting | SQLite (dev/test) | Postgres (production) |
|---------|------------------|----------------------|
| `DATABASE_URL` | `sqlite:///data/enterprise.db` | `postgresql://user:pass@host/db` |
| Connection pooling | SQLAlchemy default (NullPool) | SQLAlchemy QueuePool |
| RLS | Handled in `app/core/security.py` | Enforced by Postgres itself |
| Migrations | `create_all()` at startup | `psql -f migrations/001_initial.sql` |
| Data persistence | Local file (git-ignored) | Managed cloud database |

---

## Directory layout after Phase 2

```mermaid
graph TD
    ROOT[project root] --> BACKEND[backend/]
    ROOT --> DATABASE[database/]
    ROOT --> SAMPLE[sample_data/]
    ROOT --> TESTS[tests/]
    ROOT --> DATA[data/\ngit-ignored]

    BACKEND --> APP[app/]
    APP --> CORE[core/\nconfig db health logging]
    APP --> MODELS[models/\nbase entities research]
    APP --> SCHEMAS[schemas/\ncommon Evidence]
    APP --> REPOS[repositories/\n6 repository classes]
    APP --> SERVICES[services/\nseed_service]
    APP --> API[api/\nhealth]
    APP --> MIDDLEWARE[middleware/\nrequest_context]

    DATABASE --> SCHSQL[schema.sql]
    DATABASE --> RLSSQL[rls_policies.sql]
    DATABASE --> SEEDSQL[seed.sql]
    DATABASE --> MIGRATIONS[migrations/\n001_initial.sql]

    SAMPLE --> JSONFILES[9 JSON files]
    SAMPLE --> DOCS[documents/\n15 .md files]

    TESTS --> UNIT[unit/\ntest_evidence_schema.py]
    TESTS --> API2[api/\ntest_seed_counts.py\ntest_health.py\ntest_request_id.py]

    DATA --> SQLITE[(enterprise.db\ntest.db)]
```

---

## What Phase 2 does NOT wire up yet

| Component | Status | Coming in |
|-----------|--------|-----------|
| Redis / cache | Not connected | Phase 3 |
| Vector store (Qdrant / in-memory) | Not connected | Phase 6 |
| Graph store (Neo4j / in-memory) | Not connected | Phase 7 |
| Authentication / JWT | Not enforced | Phase 3 |
| LLM provider | Not connected | Phase 4 |
| Docker Compose stack | Not present | Phase 15 |

The database is the only external data dependency added in Phase 2. All tests still run with zero external services: SQLite stores everything locally, and the seed service reads from local JSON files.
