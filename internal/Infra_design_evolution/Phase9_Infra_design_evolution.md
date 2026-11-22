# Phase 9 — Infrastructure Design Evolution: Ingestion and Document Management

## Overview

Phase 9 adds three new infrastructure concerns:
1. **Ingest pipeline** — an internal service that processes files and writes to multiple stores simultaneously
2. **HTTP file upload** — the documents API accepts binary file data from clients
3. **Approval persistence** — a new table records pending/approved/rejected delete requests

No new network components are introduced. Everything still runs in a single process during development.

---

## Component wiring: before Phase 9

```mermaid
graph TD
    subgraph "Process boundary: uvicorn :8001"
        FASTAPI[FastAPI app]
        ROUTERS[Routers\nhealth / auth / customers\nincidents / decisions]
        SEED[Seed service\nruns at startup]
        DB[(SQLite\nentities + research + documents)]
        VS[Memory Vector Store\nempty at startup]
        GS[Memory Graph Store\npopulated by seed-graph]
        REDIS[fakeredis\nrate-limit + sessions]
    end
    FASTAPI --> ROUTERS
    FASTAPI --> SEED
    SEED --> DB
    ROUTERS --> DB
```

The vector store was empty. Graph store was seeded only by running `make seed-graph` manually.

---

## Component wiring: after Phase 9

```mermaid
graph TD
    subgraph "Process boundary: uvicorn :8001"
        FASTAPI[FastAPI app]

        subgraph "New routers"
            DOC_ROUTER[Documents router\n/api/v1/documents\n/api/v1/approvals]
            GRAPH_ROUTER[Graph router\n/api/v1/graph/...]
        end

        subgraph "New services"
            INGEST[Ingest pipeline\nrag/ingest.py]
            APPROVAL_SVC[Approval service\nservices/approval_service.py]
            EXTRACT[Entity extractor\nrag/extraction.py]
        end

        subgraph "Data stores"
            DB[(SQLite\ndocuments + chunks\n+ approval_requests)]
            VS[Memory Vector Store\n~70 chunks after ingest]
            GS[Memory Graph Store\n~85 nodes / 260 edges]
        end

        REDIS[fakeredis]
    end

    CLIENT[HTTP Client\nbrowser / curl] -->|multipart/form-data| DOC_ROUTER
    DOC_ROUTER --> INGEST
    DOC_ROUTER --> APPROVAL_SVC
    GRAPH_ROUTER --> GS
    INGEST --> VS
    INGEST --> DB
    INGEST --> EXTRACT
    EXTRACT --> GS
    APPROVAL_SVC --> DB
    FASTAPI --> REDIS
```

---

## File upload data flow

File upload uses HTTP multipart/form-data. The `python-multipart` library parses the request body into binary content in memory.

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Validator
    participant Ingest
    participant TempFS

    Client->>FastAPI: POST /api/v1/documents/upload\n(multipart: file bytes)
    FastAPI->>Validator: Check extension (.md/.txt/.pdf)
    Validator->>Validator: Check size ≤ MAX_UPLOAD_MB
    FastAPI->>Ingest: ingest_bytes(content, filename, session)
    Ingest->>TempFS: Write to temp file (tempfile.mkstemp)
    Ingest->>Ingest: ingest_file(tmp_path, session)
    Ingest->>TempFS: Delete temp file (always, even on error)
    Ingest-->>FastAPI: doc_id
    FastAPI-->>Client: 201 {doc_id, chunk_count, flagged}
```

The temp file approach means the ingest pipeline always works with file paths (consistent with the `make ingest` CLI flow) rather than raw bytes streams.

---

## Approval request data flow

```mermaid
graph LR
    subgraph "HTTP layer"
        DEL[DELETE /documents/{id}]
        APPROVE[POST /approvals/{id}/approve]
        REJECT[POST /approvals/{id}/reject]
        LIST[GET /approvals]
    end
    subgraph "Service layer"
        SVC[ApprovalService]
    end
    subgraph "Database"
        AR[(approval_requests table)]
        DOC[(documents table)]
    end

    DEL -->|analyst+| SVC
    SVC -->|INSERT status=pending| AR
    APPROVE -->|admin| SVC
    SVC -->|UPDATE status=approved| AR
    SVC -->|UPDATE doc.status=deleted| DOC
    REJECT -->|admin| SVC
    SVC -->|UPDATE status=rejected| AR
    LIST -->|admin| SVC
    SVC -->|SELECT| AR
```

The document is **never physically deleted** in v1. Setting `status=deleted` hides it from the API. Physical cleanup would be done by a separate job in production.

---

## Knowledge graph API routing

```mermaid
graph TD
    CLIENT[Viewer / Analyst]
    subgraph "Graph API router"
        STATS[GET /graph/stats\nviewer+]
        NODES[GET /graph/nodes\nviewer+ optional ?label=X]
        NODE[GET /graph/nodes/{id}\nviewer+]
        EXPAND[GET /graph/nodes/{id}/neighbors\nviewer+ ?direction=out/in/both]
        CYPHER[POST /graph/cypher\nanalyst+ read-only check]
    end
    subgraph "Graph store (interface)"
        MEMORY[MemoryGraphStore\ndefault in tests + dev]
        NEO4J[Neo4jGraphStore\nwhen GRAPH_STORE=neo4j]
    end

    CLIENT --> STATS
    CLIENT --> NODES
    CLIENT --> NODE
    CLIENT --> EXPAND
    CLIENT --> CYPHER
    STATS --> MEMORY
    NODES --> MEMORY
    NODE --> MEMORY
    EXPAND --> MEMORY
    CYPHER -->|validate_readonly| MEMORY
    MEMORY -.->|swap via config| NEO4J
```

---

## DocumentSource adapter architecture

```mermaid
graph TD
    subgraph "integrations/"
        PROTO[DocumentSource\nprotocol\nprotocols.py]
        LOCAL[LocalDirectoryAdapter\nreads disk]
        CONF_MOCK[ConfluenceMockAdapter\nreturns stubs]
        SP_MOCK[SharePointMockAdapter\nreturns stubs]
    end
    subgraph "Future"
        CONF_REAL[ConfluenceAdapter\nHTTP to Confluence Cloud]
        SP_REAL[SharePointAdapter\nMicrosoft Graph API]
        DRIVE[GoogleDriveAdapter\nGoogle Drive API]
    end
    subgraph "Ingest pipeline"
        INGEST[rag/ingest.py]
    end

    PROTO --> LOCAL
    PROTO --> CONF_MOCK
    PROTO --> SP_MOCK
    PROTO -.-> CONF_REAL
    PROTO -.-> SP_REAL
    PROTO -.-> DRIVE

    LOCAL --> INGEST
    CONF_MOCK --> INGEST
    CONF_REAL -.-> INGEST
```

The `DocumentSource` protocol ensures that any new adapter works with the existing ingest pipeline without changes to `rag/ingest.py`. Adapters are **swappable by configuration**.

---

## Development vs. production topology

```mermaid
graph TD
    subgraph "Development / test (Phase 9)"
        DEV_APP[FastAPI single process]
        DEV_VS[MemoryVectorStore\nin-process]
        DEV_GS[MemoryGraphStore\nin-process]
        DEV_DB[SQLite\ndata/enterprise.db]
        DEV_REDIS[fakeredis\nin-process]
        DEV_LOCAL[LocalDirectoryAdapter\nsample_data/documents/]
    end
    subgraph "Production (Phase 15 target)"
        PROD_APP[FastAPI + workers]
        QDRANT[Qdrant Cloud]
        NEO4J[Neo4j Aura]
        POSTGRES[Supabase Postgres]
        REDIS_REAL[Redis Cloud]
        CONF_PROD[Real Confluence adapter]
    end
    DEV_APP --> DEV_VS
    DEV_APP --> DEV_GS
    DEV_APP --> DEV_DB
    DEV_APP --> DEV_REDIS
    DEV_APP --> DEV_LOCAL

    PROD_APP --> QDRANT
    PROD_APP --> NEO4J
    PROD_APP --> POSTGRES
    PROD_APP --> REDIS_REAL
    PROD_APP --> CONF_PROD
```

The swap from in-memory to production stores requires only config changes (`VECTOR_STORE=qdrant`, `GRAPH_STORE=neo4j`, `DATABASE_URL=postgresql://...`). No code changes.

---

## Network / port summary (Phase 9 — development)

| Component | Port | Protocol | Notes |
|---|---|---|---|
| FastAPI backend | 8001 | HTTP | All requests go here |
| SQLite | n/a | File I/O | `data/enterprise.db` |
| MemoryVectorStore | n/a | In-process | No network call |
| MemoryGraphStore | n/a | In-process | No network call |
| fakeredis | n/a | In-process | No network call |
| Next.js frontend | 3001 | HTTP | Added in Phase 13 |
