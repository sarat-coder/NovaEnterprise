# Phase 15 — Project System Design Evolution

## Overview

Phase 15 completes the NovaEnterprise platform by adding the outer ring of production readiness: evaluation, packaging, deployment, and an external integration surface. No core business logic changes — this phase proves the platform works and shows how to run it anywhere.

---

## Stage 1: Before Phase 15 — Working platform, no delivery layer

After Phase 14 the platform had all 14 phases of business logic running. What was missing:

- No automated quality gate on AI answer quality
- No packaging (Dockerfiles) — required a manual Python + Node.js setup
- No single-command deployment (Compose)
- No external integration surface (MCP)
- No automated hygiene checks

```mermaid
graph TB
    subgraph "Before Phase 15"
        Browser["Browser :3001\n(Next.js)"]
        Backend["FastAPI :8001"]
        SQLite["SQLite\n(runtime only)"]
        Memory["In-process vector\n+ graph stores"]
        FakeRedis["fakeredis\n(in-process)"]
    end

    subgraph "Missing"
        Docker["❌ Dockerfiles"]
        Compose["❌ docker-compose.yml"]
        Eval["❌ Evaluation suite"]
        MCP["❌ MCP server"]
        Hygiene["❌ Hygiene tests"]
    end

    Browser --> Backend --> SQLite
    Backend --> Memory
    Backend --> FakeRedis
```

---

## Stage 2: Evaluation suite (P15-1)

The first addition is a closed feedback loop: does the AI actually give good answers?

```mermaid
graph LR
    subgraph "Eval pipeline"
        Cases["eval_cases.json\n5 questions with\nground truth"]
        Runner["evaluate.py\nruns each question\noffline"]
        Scorer["6 metric scorers\n(relevance, SQL, graph,\nmulti-hop, citation, grounding)"]
        Report["Score report\nvs. CI thresholds"]
        Gate{"All thresholds\nmet?"}
    end

    Cases --> Runner --> Scorer --> Report --> Gate
    Gate -->|Yes| Pass["CI: PASS"]
    Gate -->|No| Fail["CI: FAIL\n(build blocked)"]
```

**CI thresholds (from CLAUDE.md §12):**

```mermaid
xychart-beta
    title "Eval thresholds vs observed scores"
    x-axis ["retrieval\nrelevance", "SQL\ncorrectness", "graph\ncorrectness", "multi-hop\ncoverage", "citation\nsupport", "answer\ngrounding"]
    y-axis "Score" 0 --> 1
    bar [0.80, 1.00, 1.00, 0.66, 1.00, 0.50]
```

---

## Stage 3: Container packaging (P15-2)

Both the backend and frontend are packaged as multi-stage Docker images.

```mermaid
graph TB
    subgraph "backend/Dockerfile"
        B1["Stage 1: builder\npython:3.12-slim\n+ uv install deps"]
        B2["Stage 2: runner\npython:3.12-slim\n+ copy .venv only\n+ non-root user nova\n+ EXPOSE 8001"]
    end

    subgraph "frontend/Dockerfile"
        F1["Stage 1: deps\nnode:20-alpine\nnpm ci --omit=dev"]
        F2["Stage 2: builder\nnode:20-alpine\nnpm ci + npm run build"]
        F3["Stage 3: runner\nnode:20-alpine\ncopy .next/standalone only\nnon-root user nova\nEXPOSE 3001"]
    end

    B1 -->|.venv copied| B2
    F1 -->|node_modules| F2
    F2 -->|standalone output| F3
```

**Security invariants:**

```mermaid
graph TD
    subgraph "What is NOT in the images"
        A[".env file"]
        B["Real API keys"]
        C["SUPABASE_SERVICE_ROLE_KEY\n(must never reach frontend)"]
        D["Source code test files"]
        E["node_modules (stripped in runner)"]
    end

    subgraph "How they are excluded"
        A --> G1[".dockerignore\n.env entry"]
        B --> G2["No ENV key=value\nin Dockerfile"]
        C --> G3["Frontend Dockerfile\nnever references it"]
    end
```

---

## Stage 4: Docker Compose stack (P15-3)

The Compose file wires all six services with correct dependency ordering and health checks.

```mermaid
graph TB
    subgraph "docker-compose.yml services"
        PG["postgres:16\n:5432\nvolume: postgres_data"]
        RD["redis:7\n:6379\nvolume: redis_data"]
        QD["qdrant:v1.11.3\n:6333\nvolume: qdrant_data"]
        N4["neo4j:5.24\n:7474 HTTP\n:7687 Bolt\nvolume: neo4j_data"]
        BE["backend\nbuild: backend/Dockerfile\n:8001\nenv_file: .env"]
        FE["frontend\nbuild: frontend/Dockerfile\n:3001"]
    end

    PG -->|healthcheck:\npg_isready| BE
    RD -->|healthcheck:\nredis-cli ping| BE
    QD -->|healthcheck:\ncurl /healthz| BE
    N4 -->|healthcheck:\nwget 7474| BE
    BE -->|healthcheck:\ncurl /health/live| FE
```

**Environment wiring for the backend in Compose:**

```mermaid
graph LR
    PG["postgres:5432"] -->|DATABASE_URL\npostgresql+psycopg2://...| BE["backend"]
    RD["redis:6379"] -->|REDIS_URL\nredis://redis:6379| BE
    QD["qdrant:6333"] -->|QDRANT_URL\nhttp://qdrant:6333\nVECTOR_STORE=qdrant| BE
    N4["neo4j:7687"] -->|NEO4J_URI bolt://neo4j:7687\nGRAPH_STORE=neo4j| BE
```

---

## Stage 5: CI pipeline (P15-4)

The CI workflow now runs four jobs in parallel after every push.

```mermaid
graph TD
    Push["git push / PR"]
    Push --> J1["lint-and-test\nruff + pytest (293 tests)\nexcl. eval + deployment"]
    Push --> J4["frontend-lint-test\nnext lint + jest"]
    J1 --> J2["eval-gate\nevaluate.py\nthreshold check"]
    J1 --> J3["deployment-hygiene\npytest tests/deployment/\n(16 tests)"]

    J2 --> Gate{"All pass?"}
    J3 --> Gate
    J4 --> Gate
    Gate -->|Yes| Merge["PR mergeable"]
    Gate -->|No| Block["PR blocked"]
```

---

## Stage 6: MCP server (P15-5)

The MCP server adds an external integration surface — any MCP-compatible AI agent can now query the platform.

```mermaid
graph LR
    subgraph "External AI agent"
        Claude["Claude / GPT / other\nMCP client"]
    end

    subgraph "MCP server (stdio)"
        Proto["JSON-RPC 2.0\nover stdin/stdout"]
        Tools["6 read-only tools"]
    end

    subgraph "Platform internals"
        Vector["rag/retriever.py"]
        Graph["rag/graph_store.py"]
        SQL["rag/sql_retrieval.py"]
        DB["app/repositories/*"]
    end

    Claude -->|tools/list| Proto
    Claude -->|tools/call| Proto
    Proto --> Tools
    Tools -->|search_knowledge| Vector
    Tools -->|query_graph| Graph
    Tools -->|run_sql_query| SQL
    Tools -->|list_incidents\nlist_customers\nget_research_session| DB
```

**Read-only guarantee:**

```mermaid
graph TD
    MCPTool["tools/call request"]
    MCPTool --> Check{"Is tool name\na write verb?"}
    Check -->|No: search, query, list, get| Execute["Execute handler\n(reads only)"]
    Check -->|Yes: create/delete/upload| Refused["Not in TOOLS list\n→ tool not found error"]
    Execute --> ValidateSQL["validate_sql()\non every SQL statement"]
    Execute --> ReadOnly["Cypher read-only check\non every Cypher query"]
```

---

## Final Architecture: Phase 15

```mermaid
graph TB
    subgraph "External"
        Browser["Browser :3001"]
        MCPClient["External AI agent\n(MCP client)"]
    end

    subgraph "Frontend :3001 (Docker)"
        NextJS["Next.js 15\n(14 screens)"]
    end

    subgraph "Backend :8001 (Docker)"
        FastAPI["FastAPI\n16 routers\nmiddleware stack"]
        LangGraph["LangGraph\n14-node workflow"]
        Guardrails["Guardrails\n(injection + scrub)"]
    end

    subgraph "Data stores (Docker)"
        PG["PostgreSQL :5432"]
        RD["Redis :6379"]
        QD["Qdrant :6333"]
        N4["Neo4j :7687"]
    end

    subgraph "MCP server (stdio)"
        MCPServer["mcp_server.py\n6 read-only tools"]
    end

    subgraph "CI (GitHub Actions)"
        CI["lint-and-test\neval-gate\ndeployment-hygiene\nfrontend-lint-test"]
    end

    Browser --> NextJS --> FastAPI
    MCPClient --> MCPServer --> FastAPI
    FastAPI --> LangGraph --> Guardrails
    FastAPI --> PG & RD & QD & N4
    LangGraph --> QD & N4 & PG
```

---

## Summary of design decisions in Phase 15

| Decision | Alternative | Why chosen |
|----------|-------------|------------|
| Offline eval with fake LLM | Eval against real LLM | Deterministic, no cost, runs in CI |
| Thresholds below observed scores | Exact observed scores | Catches regression without failing on noise |
| Multi-stage Dockerfiles | Single-stage | Runner image is smaller; build tools don't reach production |
| Non-root container user | Root user | Least-privilege; industry standard |
| Health checks on every store | No health checks | Compose respects start order; prevents race conditions |
| stdio MCP transport | HTTP/SSE | Simpler; no extra port; composable with pipe |
| Read-only MCP tools only | Full CRUD tools | External agents must not mutate enterprise data |
| Hygiene tests via pytest | Manual review | Automated; enforced on every PR |
