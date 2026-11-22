# Phase 7 — Infrastructure Design Evolution: Graph RAG

> This document explains the component wiring, routing, and infrastructure introduced in Phase 7. It shows how the graph store fits into the platform's overall infrastructure, the connection paths used in development vs. production, and how the system behaves when the graph store is unavailable.

---

## Infrastructure Baseline After Phase 6

After Phase 6, the platform used three infrastructure components:

```mermaid
graph LR
    subgraph "Process boundary"
        BE[FastAPI backend<br/>:8001]
        VS[(Vector Store<br/>in-process RAM)]
    end

    subgraph "External (optional)"
        QD[Qdrant<br/>vector DB]
    end

    subgraph "Always external"
        DB[(SQLite / PostgreSQL)]
        RD[(Redis / fakeredis)]
    end

    BE <-->|VECTOR_STORE=memory| VS
    BE <-->|VECTOR_STORE=qdrant| QD
    BE <-->|DATABASE_URL| DB
    BE <-->|REDIS_URL| RD
```

Phase 7 adds the graph store — a fourth persistence layer with its own adapter pattern.

---

## Phase 7 Addition: The Graph Store

```mermaid
graph LR
    subgraph "Process boundary"
        BE[FastAPI backend<br/>:8001]
        VS[(Vector Store<br/>in-process RAM)]
        GS[(Graph Store<br/>in-process RAM)]
    end

    subgraph "External (optional)"
        QD[Qdrant<br/>vector DB]
        N4J[Neo4j<br/>graph DB<br/>:7474 / :7687]
    end

    subgraph "Always external"
        DB[(SQLite / PostgreSQL)]
        RD[(Redis / fakeredis)]
    end

    BE <-->|VECTOR_STORE=memory| VS
    BE <-->|VECTOR_STORE=qdrant| QD
    BE <-->|GRAPH_STORE=memory| GS
    BE <-->|GRAPH_STORE=neo4j<br/>bolt://host:7687| N4J
    BE <-->|DATABASE_URL| DB
    BE <-->|REDIS_URL| RD
```

**New env vars introduced in Phase 7:**

| Variable | Default | Purpose |
|---|---|---|
| `GRAPH_STORE` | `memory` | Selects the adapter: `memory` or `neo4j` |
| `NEO4J_URI` | _(empty)_ | Bolt connection string, e.g. `bolt://localhost:7687` |
| `NEO4J_USER` | _(empty)_ | Neo4j username |
| `NEO4J_PASSWORD` | _(empty)_ | Neo4j password |

---

## Deployment Mode 1: Fully Offline (Development / CI)

No external services. Everything runs in-process.

```mermaid
graph TD
    subgraph "Single process — no network calls"
        APP[FastAPI app<br/>uvicorn :8001]
        MEM_VS[MemoryVectorStore<br/>in-process RAM]
        MEM_GS[MemoryGraphStore<br/>in-process RAM]
        FAKE_LLM[FakeChatModel<br/>deterministic]
        FAKE_EMB[FakeEmbeddings<br/>deterministic]
        FAKEREDIS[fakeredis<br/>in-process]
        SQLITE[(SQLite<br/>data/enterprise.db)]
    end

    APP <--> MEM_VS
    APP <--> MEM_GS
    APP <--> FAKE_LLM
    APP <--> FAKE_EMB
    APP <--> FAKEREDIS
    APP <--> SQLITE

    ENV["Environment variables<br/>LLM_PROVIDER=fake<br/>VECTOR_STORE=memory<br/>GRAPH_STORE=memory<br/>REDIS_URL=<empty>"]
    ENV -.->|configures| APP
```

**Startup sequence (lifespan):**
1. Create SQLite tables
2. Seed domain data (teams, services, customers, incidents, decisions)
3. Register vector store health check
4. **Register graph store health check** ← new in Phase 7
5. Register LLM health check
6. Build the LangGraph research workflow (Phase 12)

**Health check output (offline):**
```json
{
  "status": "ok",
  "checks": {
    "database": {"status": "ok", "detail": "sqlite"},
    "redis": {"status": "ok", "detail": "fakeredis"},
    "vector_store": {"status": "ok", "detail": "memory (70 chunks)"},
    "graph_store": {"status": "ok", "detail": "memory (85 nodes, 260 edges)"},
    "llm": {"status": "ok", "detail": "fake"}
  }
}
```

---

## Deployment Mode 2: Production Stack (Docker Compose)

Production adds real external services. This is wired in Phase 15, but the adapters are ready now.

```mermaid
graph TD
    subgraph "docker-compose network: nova-net"
        subgraph "app container"
            APP[FastAPI<br/>:8001]
        end

        subgraph "Data stores"
            PG[(PostgreSQL<br/>:5432)]
            QD[(Qdrant<br/>:6333)]
            N4J[(Neo4j<br/>:7474 HTTP<br/>:7687 Bolt)]
            RD[(Redis<br/>:6379)]
        end

        subgraph "AI providers (external)"
            OAI[OpenAI API]
            ANT[Anthropic API]
        end
    end

    APP <-->|DATABASE_URL=postgresql://...| PG
    APP <-->|VECTOR_STORE=qdrant<br/>QDRANT_URL=http://qdrant:6333| QD
    APP <-->|GRAPH_STORE=neo4j<br/>NEO4J_URI=bolt://neo4j:7687| N4J
    APP <-->|REDIS_URL=redis://redis:6379| RD
    APP <-->|LLM_PROVIDER=openai/anthropic| OAI
    APP <-->|LLM_PROVIDER=anthropic| ANT
```

**Network routing details for Neo4j:**
- The Neo4j container exposes two ports: `7474` (HTTP browser interface) and `7687` (Bolt binary protocol)
- The backend uses the **Bolt protocol** (`bolt://neo4j:7687`) — this is the high-performance binary wire protocol for the Python driver
- Inside the Docker network, the hostname `neo4j` resolves to the Neo4j container's IP automatically
- Authentication: `NEO4J_USER=neo4j`, `NEO4J_PASSWORD` set in `.env`

---

## Component Wiring: The Adapter Factory Pattern

The selection of which graph store adapter to use happens in one place:

```mermaid
graph TD
    CFG[get_settings<br/>reads GRAPH_STORE env var]
    CFG -->|"memory"| MGS[MemoryGraphStore<br/>rag/graph_store.py]
    CFG -->|"neo4j"| NGS[Neo4jGraphStore<br/>rag/neo4j_adapter.py]

    subgraph "get_graph_store() factory"
        SING["_instance singleton<br/>(None on first call)"]
        SING -->|first call| CFG
        SING -->|subsequent calls| CACHED[return cached instance]
    end

    MGS -->|satisfies| PROTO[GraphStoreService protocol]
    NGS -->|satisfies| PROTO

    CALLERS[Research agents<br/>Health checks<br/>Graph seeder] --> PROTO
```

**Key guarantee:** `get_graph_store()` is called once at startup and cached. All subsequent callers share the same instance. `reset_graph_store()` clears the cache — used in tests to get a fresh empty store for each test.

---

## Connection Lifecycle: Neo4j Lazy Connection

The Neo4j adapter uses a **lazy connection** — the driver is not opened at import time, only when the first operation is called:

```mermaid
sequenceDiagram
    participant App as FastAPI startup
    participant Fac as get_graph_store()
    participant Adp as Neo4jGraphStore
    participant N4J as Neo4j server

    App->>Fac: get_graph_store()
    Fac->>Adp: Neo4jGraphStore() — no connection yet
    Fac-->>App: return adapter instance

    App->>Adp: health check ping()
    Adp->>N4J: GraphDatabase.driver(...).verify_connectivity()
    alt Neo4j is up
        N4J-->>Adp: OK
        Adp-->>App: True → "ok"
    else Neo4j is down
        N4J-->>Adp: timeout/refused
        Adp-->>App: ConnectionError → "degraded"
    end

    Note over App: If degraded, /health/ready reports degraded<br/>workflow continues without graph
```

**Why lazy?** Connecting at import time would cause the backend to fail to start if Neo4j is not ready yet. With a lazy connection, the backend starts, reports "degraded" on the health check, and the graph store becomes available as soon as Neo4j is reachable — without restarting the backend.

---

## Read-Only Cypher Request Flow

When an analyst submits a custom Cypher query:

```mermaid
sequenceDiagram
    participant UI as Browser
    participant API as FastAPI /api/v1/graph/cypher
    participant Guard as assert_readonly_cypher()
    participant Store as GraphStoreService

    UI->>API: POST {cypher: "MATCH (n:Service) RETURN n"}
    API->>Guard: assert_readonly_cypher(cypher)
    Guard-->>API: OK (no write keywords)
    API->>Store: execute_cypher_readonly(cypher, params)
    Store-->>API: list[dict] results
    API-->>UI: 200 OK results

    UI->>API: POST {cypher: "CREATE (n:Service {name:'bad'})"}
    API->>Guard: assert_readonly_cypher(cypher)
    Guard-->>API: ValueError — 'CREATE' is not permitted
    API-->>UI: 400 Bad Request {"detail": "Write operation 'CREATE' is not permitted..."}
```

**Where the guard lives:** `rag/graph_store.py::assert_readonly_cypher()` — a pure function that both adapters import. This ensures the same enforcement regardless of which backend is active.

---

## Health Check Integration

The graph store registers its own readiness check during the lifespan startup:

```mermaid
graph TD
    subgraph "Lifespan startup"
        RGSCK[register_graph_store_check]
    end

    subgraph "Health registry"
        REG["_registry: dict[str → CheckFn]"]
        REG -->|"database"| DB_CK[db check]
        REG -->|"redis"| RD_CK[redis check]
        REG -->|"vector_store"| VS_CK[vector store check]
        REG -->|"graph_store"| GS_CK[graph store check ← new]
        REG -->|"llm"| LLM_CK[llm check]
    end

    RGSCK -->|registers| GS_CK

    subgraph "graph_store check logic"
        GS_CK -->|GRAPH_STORE=memory| OK["ok: memory (85 nodes, 260 edges)"]
        GS_CK -->|GRAPH_STORE=neo4j, neo4j up| OK2["ok: neo4j (N nodes, E edges)"]
        GS_CK -->|GRAPH_STORE=neo4j, neo4j down| DEG["degraded: neo4j unreachable"]
        GS_CK -->|unexpected exception| ERR["error: <message>"]
    end

    subgraph "run_all_checks() result"
        OK --> OVERALL_OK[overall: ok]
        OK2 --> OVERALL_OK
        DEG --> OVERALL_DEG[overall: degraded]
        ERR --> OVERALL_ERR[overall: error]
    end
```

**Status semantics:**
- `"ok"` — store is fully functional
- `"degraded"` — store is unavailable but the platform can still answer questions from documents and SQL; this is the expected Neo4j-down state
- `"error"` — unexpected failure; should be investigated

---

## make seed-graph: The Seeder Command

```mermaid
graph LR
    subgraph "make seed-graph"
        SD[rag/graph_seed.py<br/>__main__] --> RGS[reset_graph_store]
        RGS --> GGS[get_graph_store]
        GGS -->|GRAPH_STORE=memory| MGS[MemoryGraphStore]
        GGS -->|GRAPH_STORE=neo4j| NGS[Neo4jGraphStore]
        SD --> LOAD[Load 8 JSON files<br/>from sample_data/]
        LOAD --> SEED[seed_graph store]
        SEED -->|add 85 nodes| MGS & NGS
        SEED -->|add ~260 edges| MGS & NGS
        SEED --> OUT["Graph seeded:<br/>85 nodes, 260 edges"]
    end
```

**Usage:**
```bash
make seed-graph          # seeds using GRAPH_STORE from .env (default: memory)
GRAPH_STORE=neo4j make seed-graph  # seeds a running Neo4j instance
```

The seeder is **idempotent** for Neo4j (uses MERGE internally), and for the in-memory adapter it replaces existing nodes via upsert.

---

## Summary: What Phase 7 Adds to Infrastructure

| Concern | Before Phase 7 | After Phase 7 |
|---|---|---|
| Graph store | None | `MemoryGraphStore` (default) or `Neo4jGraphStore` |
| Graph connection | — | Lazy, with degraded fallback |
| Health endpoint | 4 checks | 5 checks (adds `graph_store`) |
| Read-only guard | SQL validator | SQL validator + Cypher guard |
| Seed command | — | `make seed-graph` (85 nodes, ~260 edges) |
| Env vars | 10 | 14 (adds `GRAPH_STORE`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`) |
