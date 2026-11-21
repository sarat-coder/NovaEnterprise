# Phase 2 — System Design Evolution: Persistence and Sample Data

> This document tracks how the system design evolved during Phase 2.
> Starting point: the Phase 1 FastAPI skeleton with health checks and no data layer.
> End point: a fully seeded, layered data platform with a universal Evidence schema.

---

## Starting point (end of Phase 1)

At the end of Phase 1, the system was a working FastAPI server with no database, no domain models, and no data. The only things running were health routes and a request-ID middleware.

```mermaid
graph TD
    subgraph Phase 1 output
        CLIENT[Browser / curl] --> MAIN[FastAPI main.py]
        MAIN --> HEALTH[/health /live /ready]
        MAIN --> CFG[config.py Settings]
        MAIN --> LOG[logging.py]
        MAIN --> MW[X-Request-ID middleware]
    end
```

---

## After P2-1 — SQLAlchemy Models and Evidence Schema

The first Phase 2 task introduced the **data model layer**: all the domain entities (Team, Service, Incident, etc.) and the research entities (ResearchSession, DocumentRecord, etc.) defined as Python classes. The `Evidence` schema was also defined here — a Pydantic model that every retrieval path uses.

```mermaid
graph TD
    subgraph backend/app/models
        BASE[base.py\nDeclarativeBase]
        ENT[entities.py\nTeam Employee Service\nCustomer Incident Decision\nProject Ticket]
        RES[research.py\nResearchSession WorkflowEvent\nDocumentRecord DocumentChunk\nApprovalRequest MemoryRecord]
    end

    subgraph backend/app/schemas
        CMN[common.py\nEvidence\nsource_type: document|sql|graph\nlocator content score]
    end

    BASE --> ENT
    BASE --> RES
```

**Key design decision: One Evidence shape for all retrieval paths**

The `Evidence` model has a `source_type` discriminator (`document`, `sql`, `graph`) and a `locator` that points to the precise source. All three retrieval systems (vector search, SQL, graph) return `Evidence` objects. This makes it possible to build a single numbered citation list from disparate sources.

---

## After P2-2 — Postgres Schema, RLS Policies, and Migrations

The second task introduced the **Postgres-side SQL artifacts**: a complete `schema.sql`, row-level security policies in `rls_policies.sql`, and a migration script. These files mirror the SQLAlchemy models but target Postgres production deployments (Supabase).

```mermaid
graph TD
    subgraph database/
        SCH[schema.sql\n16 CREATE TABLE statements]
        RLS[rls_policies.sql\nper-table ENABLE ROW LEVEL SECURITY\ncurrent_app_role helper function\npolicies per role: viewer analyst admin]
        MIG[migrations/001_initial.sql\npins schema.sql version]
    end

    subgraph ORM
        MODELS[app/models/*.py\nSQLAlchemy classes]
    end

    MODELS -->|must stay in sync with| SCH
    SCH -->|referenced by| MIG
    SCH -->|extended by| RLS
```

**Key design decision: RLS is defence-in-depth**

Row-Level Security enforces access rules inside Postgres, not just in application code. Even if a bug in the FastAPI layer accidentally skips a `require_role` check, the database itself refuses the query. This satisfies CLAUDE.md §8 (security) for the Supabase production path.

For local SQLite development, RLS is handled by `backend/app/core/security.py` (Phase 3). SQLite has no native RLS.

---

## After P2-3 — Repository Layer

The repository layer introduced a clean abstraction for all SQL access. No code outside `app/repositories/` is allowed to write SQL.

```mermaid
graph LR
    subgraph API Layer
        API[api/*.py\nHTTP handlers]
    end

    subgraph Service Layer
        SVC[services/*.py\norchestration]
    end

    subgraph Repository Layer
        TR[TeamRepository]
        CR[CustomerRepository]
        IR[IncidentRepository]
        DR[DecisionRepository]
        DOCR[DocumentRepository]
        RR[ResearchRepository]
    end

    subgraph Database
        DB[(SQLite / Postgres)]
    end

    API --> SVC
    SVC --> TR & CR & IR & DR & DOCR & RR
    TR & CR & IR & DR & DOCR & RR --> DB

    style API fill:#e8f4f8
    style SVC fill:#e8ffe8
    style TR fill:#fff8e8
    style CR fill:#fff8e8
    style IR fill:#fff8e8
    style DR fill:#fff8e8
    style DOCR fill:#fff8e8
    style RR fill:#fff8e8
```

**Key design decision: One-way import chain**

The layering rule `api → services → repositories → models` is enforced by CLAUDE.md §4.2 and tested in code review. Agents (`agents/`) never import repositories — they receive data from services. This prevents the retrieval logic from becoming entangled with the HTTP layer.

---

## After P2-4 — Sample Data and 15 Documents

This task populated the data layer with the fictional company's records: 9 JSON files and 15 Markdown documents. The design decision here is that sample data drives the whole evaluation pipeline.

```mermaid
graph TD
    subgraph sample_data/
        SD[JSON files\n9 files: teams employees\nservices customers incidents\ndecisions projects tickets\norganizational_memory]
        DOCS[documents/\n15 .md files]
        HOSTILE[vendor-note-processor-update.md\nDeliberate prompt-injection attempt\nFlagged at ingest time]
    end

    subgraph Canonical question coverage
        Q1[Who owns Payments API?] -->|services.json| A1[Payments Platform team]
        Q2[What incidents in Q3 2026?] -->|incidents.json| A2[INC-2031 INC-2036]
        Q3[Which customers impacted?] -->|incident_customers links| A3[5 customers]
        Q4[What decisions were made?] -->|decisions.json| A4[ADR-001 ADR-002]
    end

    SD --> Q1 & Q2 & Q3 & Q4
    DOCS -->|postmortem narrative| Q2
    HOSTILE -.->|indexed but never obeyed| HOSTILE
```

**Key design decisions:**
- The hostile vendor note is **not excluded** from the index — it must be retrievable as evidence (an analyst should be able to find it). What must not happen is its instructions changing the system's behaviour. That is enforced by the guardrail layer (Phase 4).
- The `organizational_memory.json` fiscal calendar definition is what allows the system to resolve "last quarter" to Q3 2026 without hard-coding dates.

---

## After P2-5 — Seed Service and Lifespan Bootstrap (final Phase 2 design)

The seed service and lifespan bootstrap wired everything together. The server now creates its own database and fills it with data on startup.

```mermaid
sequenceDiagram
    participant DEV as Developer / CI
    participant FASTAPI as FastAPI lifespan
    participant INITDB as init_db()
    participant SEED as seed_service.seed()
    participant DB as SQLite / Postgres

    DEV->>FASTAPI: make backend (or TestClient start)
    FASTAPI->>INITDB: Phase 2: create tables
    INITDB->>DB: Base.metadata.create_all()
    INITDB->>FASTAPI: register_check("database", ...)
    FASTAPI->>SEED: seed(session)
    SEED->>DB: INSERT teams (skip if exists)
    SEED->>DB: INSERT employees
    SEED->>DB: INSERT services
    SEED->>DB: INSERT customers
    SEED->>DB: INSERT incidents + incident_customers
    SEED->>DB: INSERT decisions + incident_decisions
    SEED->>DB: INSERT projects + tickets
    SEED->>DB: INSERT organizational_memory
    SEED->>DB: INSERT document_records (flag vendor-note)
    SEED-->>FASTAPI: seed complete
    FASTAPI-->>DEV: Startup complete
```

---

## Final Phase 2 Architecture — Complete Picture

```mermaid
graph TD
    subgraph External
        CLIENT[Browser / curl]
    end

    subgraph Project Root
        ENV[.env / .env.example]
        SD[sample_data/\nJSON + 15 docs]
    end

    subgraph database/
        SCHSQL[schema.sql]
        RLSSQL[rls_policies.sql]
        MIG[migrations/]
    end

    subgraph backend/app
        MAIN[main.py\nlifespan:\n1 app check\n2 init_db\n3 seed]

        subgraph core/
            CFG[config.py]
            LOG[logging.py]
            HLT[health.py\nregister_check: app + database]
            DB[db.py\nget_engine lru_cache\ninit_db create_all\nget_db generator]
        end

        subgraph models/
            BASE[base.py]
            ENT[entities.py\n10 tables]
            RES[research.py\n6 tables]
        end

        subgraph schemas/
            CMN[common.py\nEvidence]
        end

        subgraph repositories/
            TR[TeamRepository]
            CR[CustomerRepository]
            IR[IncidentRepository]
            DR[DecisionRepository]
            DOCR[DocumentRepository]
            RR[ResearchRepository]
        end

        subgraph services/
            SS[seed_service.py\nidempotent seed\nfrom JSON files]
        end

        subgraph api/
            HR[health.py\n/health /live /ready]
        end

        subgraph middleware/
            RCM[request_context.py\nX-Request-ID]
        end
    end

    subgraph tests/
        CONF[conftest.py]
        TSC[test_seed_counts.py\n14 tests]
        TEV[test_evidence_schema.py\n7 tests]
    end

    subgraph data/
        SQLITE[(enterprise.db / test.db)]
    end

    CLIENT -->|HTTP| MAIN
    MAIN -->|reads| CFG
    MAIN -->|wraps| RCM
    MAIN -->|routes| HR
    MAIN -->|startup| DB
    MAIN -->|startup| SS
    DB -->|create_all| SQLITE
    DB -->|register| HLT
    SS -->|reads| SD
    SS -->|INSERT| SQLITE
    TR & CR & IR & DR & DOCR & RR -->|SELECT| SQLITE
    ENV -->|loaded by| CFG
    SCHSQL -.->|mirrors| ENT & RES
    CONF -->|init_db + seed| TSC
```

---

## Design decisions locked in Phase 2

| Decision | Chosen approach | Why |
|----------|----------------|-----|
| One Evidence shape | `source_type` Literal + `locator` field | Enables a single numbered citation list from disparate retrieval paths |
| Repository layer | 6 classes, SQL only inside them | Prevents SQL from leaking into agents or API handlers; testable in isolation |
| Idempotent seed | Skip-if-exists per row | Server can restart without duplicating data; CI always gets a fresh state |
| Sample data in JSON | Human-editable flat files | Easy to audit, diff, and extend without touching Python code |
| SQLite for dev/test, Postgres for prod | `DATABASE_URL` env var | Zero Docker requirement for `make test`; production uses managed Postgres |
| Hostile vendor note flagged at seed time | `flagged=True` on the DocumentRecord | Guardrail can check the flag before passing content to the LLM — no false negative |
| Fiscal calendar in `organizational_memory.json` | Key-value memory record | The agent's memory service can resolve "last quarter" at runtime, not hard-coded |
