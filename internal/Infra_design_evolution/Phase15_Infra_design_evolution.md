# Phase 15 — Infrastructure and Component Wiring Evolution

## Overview

Phase 15 is the first phase that actually defines and wires the **production infrastructure**. Every earlier phase ran on in-process fakes (fakeredis, in-memory vector store, in-memory graph, SQLite). Phase 15 introduces the real services — PostgreSQL, Qdrant, Neo4j, and Redis — wired together with Docker Compose, and packages the application itself into Docker images.

---

## From in-process fakes to real services

```mermaid
graph LR
    subgraph "Phases 1–14 (offline / dev)"
        SQLite["SQLite\n(file: data/enterprise.db)"]
        FakeRedis["fakeredis\n(in-process Python)"]
        MemVector["MemoryVectorStore\n(in-process Python dict)"]
        MemGraph["MemoryGraphStore\n(in-process Python dict)"]
    end

    subgraph "Phase 15 (Docker Compose / production)"
        PG["PostgreSQL :5432\n(postgres:16-alpine)"]
        Redis["Redis :6379\n(redis:7-alpine)"]
        Qdrant["Qdrant :6333\n(qdrant/qdrant:v1.11.3)"]
        Neo4j["Neo4j :7687\n(neo4j:5.24-community)"]
    end

    SQLite -.->|DATABASE_URL=postgresql://...| PG
    FakeRedis -.->|REDIS_URL=redis://redis:6379| Redis
    MemVector -.->|VECTOR_STORE=qdrant| Qdrant
    MemGraph -.->|GRAPH_STORE=neo4j| Neo4j
```

The switch is purely configuration — the application code picks the right adapter at startup based on environment variables. No code changes are needed.

---

## Docker Compose service topology

```mermaid
graph TB
    subgraph "Host machine"
        subgraph "docker-compose.yml"
            subgraph "Infrastructure tier"
                PG["postgres\nimage: postgres:16-alpine\nport: 5432\nvolume: postgres_data\nhealthcheck: pg_isready"]
                RD["redis\nimage: redis:7-alpine\nport: 6379\nvolume: redis_data\nhealthcheck: redis-cli ping"]
                QD["qdrant\nimage: qdrant/qdrant:v1.11.3\nport: 6333/6334\nvolume: qdrant_data\nhealthcheck: curl /healthz"]
                N4["neo4j\nimage: neo4j:5.24-community\nports: 7474, 7687\nvolume: neo4j_data\nhealthcheck: wget :7474"]
            end
            subgraph "Application tier"
                BE["backend\nbuild: backend/Dockerfile\nport: 8001\nenv_file: .env\ndepends_on: all 4 stores\nhealthcheck: curl /health/live"]
                FE["frontend\nbuild: frontend/Dockerfile\nport: 3001\ndepends_on: backend"]
            end
        end
    end

    PG -.->|healthy| BE
    RD -.->|healthy| BE
    QD -.->|healthy| BE
    N4 -.->|healthy| BE
    BE -.->|healthy| FE
```

---

## Start-up sequence (dependency chain)

```mermaid
sequenceDiagram
    participant D as docker compose up
    participant PG as postgres
    participant RD as redis
    participant QD as qdrant
    participant N4 as neo4j
    participant BE as backend
    participant FE as frontend

    D->>PG: start
    D->>RD: start
    D->>QD: start
    D->>N4: start

    loop until healthy
        PG->>PG: pg_isready check
        RD->>RD: redis-cli ping
        QD->>QD: curl /healthz
        N4->>N4: wget :7474
    end

    Note over PG,N4: All four stores report healthy
    D->>BE: start (depends_on condition: service_healthy)
    BE->>BE: init_db() + seed() + build_graph() + ingest()

    loop until healthy
        BE->>BE: curl /health/live
    end

    Note over BE: Backend reports healthy
    D->>FE: start (depends_on condition: service_healthy)
    FE-->>D: ready on :3001
```

---

## Network isolation in Docker Compose

By default, all services in a `docker-compose.yml` share a private Docker network. Services refer to each other by their **service name** as the hostname — not by IP address or `localhost`.

```mermaid
graph TB
    subgraph "Docker internal network (nova_default)"
        BE["backend\n(hostname: backend)"]
        PG["postgres\n(hostname: postgres)"]
        RD["redis\n(hostname: redis)"]
        QD["qdrant\n(hostname: qdrant)"]
        N4["neo4j\n(hostname: neo4j)"]
        FE["frontend\n(hostname: frontend)"]
    end

    subgraph "Host OS — only published ports are reachable"
        H_BE[":8001"]
        H_FE[":3001"]
        H_PG[":5432"]
        H_RD[":6379"]
        H_QD[":6333"]
        H_N4a[":7474"]
        H_N4b[":7687"]
    end

    BE <-->|TCP| PG
    BE <-->|TCP| RD
    BE <-->|HTTP| QD
    BE <-->|Bolt| N4
    FE <-->|HTTP| BE

    BE --- H_BE
    FE --- H_FE
    PG --- H_PG
    RD --- H_RD
    QD --- H_QD
    N4 --- H_N4a & H_N4b
```

The backend connects to Postgres with `DATABASE_URL=postgresql+psycopg2://nova:...@postgres:5432/nova` — the hostname `postgres` resolves inside the Docker network to the postgres container.

---

## Backend container internals

```mermaid
graph TB
    subgraph "backend container"
        subgraph "Layer 1: OS (python:3.12-slim)"
            OS["Debian slim\nnon-root user nova"]
        end
        subgraph "Layer 2: .venv (copied from builder)"
            PY["Python 3.12\nFastAPI + LangGraph\n+ all dependencies"]
        end
        subgraph "Layer 3: application source"
            Src["backend/ agents/ rag/ memory/\nintegrations/ sample_data/"]
        end
        subgraph "Runtime"
            UV["uvicorn app.main:app\n--host 0.0.0.0 --port 8001"]
        end
    end

    OS --> PY --> Src --> UV
```

**What is NOT in the image:**
- `.env` files (config is injected via `env_file` or `environment` in Compose)
- `data/` directory (the SQLite file; in production this uses Postgres)
- `tests/` directory
- `frontend/` directory

---

## Frontend container internals

```mermaid
graph TB
    subgraph "frontend container (3 stages)"
        subgraph "Stage 1: deps"
            D1["node:20-alpine\nnpm ci --omit=dev"]
        end
        subgraph "Stage 2: builder"
            D2["node:20-alpine\nnpm ci\nnpm run build\n→ .next/standalone/"]
        end
        subgraph "Stage 3: runner (final image)"
            D3["node:20-alpine\nnon-root user nova\n.next/standalone/server.js\nEXPOSE 3001"]
        end
    end

    D1 -->|node_modules| D2
    D2 -->|.next/standalone| D3
```

The standalone output includes a minimal Node.js server (`server.js`) and only the files needed to run the app — not the full `node_modules` (the build tools are discarded).

---

## MCP server wiring

The MCP server runs as a separate process alongside (or instead of) the backend. It communicates over `stdin/stdout` using the JSON-RPC 2.0 protocol.

```mermaid
graph LR
    subgraph "External AI agent process"
        Agent["Claude / other\nMCP client\n(sends JSON on stdout)"]
    end

    subgraph "mcp_server.py process"
        MCPIn["stdin\nread JSON-RPC line"]
        Dispatch["_handle_message()\ndispatch by method"]
        MCPOut["stdout\nwrite JSON-RPC response"]
    end

    subgraph "Platform (same Python process)"
        V["rag.retriever\n(search_knowledge)"]
        G["rag.graph_store\n(query_graph)"]
        S["rag.sql_retrieval\n(run_sql_query)"]
        R["app.repositories\n(list_*, get_*)"]
    end

    Agent -->|pipe / spawn| MCPIn
    MCPIn --> Dispatch
    Dispatch --> V & G & S & R
    V & G & S & R --> MCPOut
    MCPOut -->|pipe| Agent
```

**How to start it:**
```bash
# Start the MCP server and pipe a tools/list request to it
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | uv run python -m integrations.mcp_server
```

---

## CI infrastructure wiring

```mermaid
graph TB
    subgraph "GitHub Actions"
        subgraph "Job: lint-and-test"
            PY312_1["Python 3.12\n+ uv"]
            Ruff["ruff check + format --check"]
            Pytest["pytest tests/\n(excl. eval + deployment)\n293 tests"]
        end
        subgraph "Job: eval-gate"
            PY312_2["Python 3.12\n+ uv"]
            EvalRun["python -m tests.evaluation.evaluate\n5 questions × 6 metrics"]
            EvalGate{"Thresholds met?"}
        end
        subgraph "Job: deployment-hygiene"
            PY312_3["Python 3.12\n+ uv"]
            HygieneTests["pytest tests/deployment/\n16 tests"]
        end
        subgraph "Job: frontend-lint-test"
            Node20["Node.js 20\nnpm ci"]
            ESLint["npm run lint\n(next lint)"]
            Jest["npm run test:ci\n(jest --ci)"]
        end
    end

    PY312_1 --> Ruff --> Pytest
    PY312_2 --> EvalRun --> EvalGate
    PY312_3 --> HygieneTests
    Node20 --> ESLint --> Jest

    Pytest & EvalGate & HygieneTests & Jest --> Merge{"All pass?\nPR mergeable"}
```

---

## Volume persistence across container restarts

```mermaid
graph LR
    subgraph "Named volumes (survive container restart)"
        V1["postgres_data\n/var/lib/postgresql/data"]
        V2["redis_data\n/data"]
        V3["qdrant_data\n/qdrant/storage"]
        V4["neo4j_data\n/data"]
    end

    subgraph "Containers"
        PG["postgres"] --> V1
        RD["redis"] --> V2
        QD["qdrant"] --> V3
        N4["neo4j"] --> V4
    end

    Note1["docker compose down\n(removes containers,\nkeeps volumes)"]
    Note2["docker compose down -v\n(removes containers\nAND volumes — full reset)"]
```

---

## Infrastructure summary: Phase 15

| Component | Technology | Port | Volume | Health check |
|-----------|-----------|------|--------|-------------|
| PostgreSQL | postgres:16-alpine | 5432 | postgres_data | pg_isready |
| Redis | redis:7-alpine | 6379 | redis_data | redis-cli ping |
| Qdrant | qdrant/qdrant:v1.11.3 | 6333 | qdrant_data | curl /healthz |
| Neo4j | neo4j:5.24-community | 7474/7687 | neo4j_data | wget :7474 |
| Backend | python:3.12-slim | 8001 | — (uses Postgres) | curl /health/live |
| Frontend | node:20-alpine | 3001 | — (stateless) | (none — depends on backend) |
| MCP server | same Python env | stdio | — | — |
