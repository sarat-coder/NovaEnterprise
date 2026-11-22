# Phase 6 — Infrastructure Design Evolution: Vector RAG

> This document explains the component wiring, networking, and infrastructure choices introduced in Phase 6.

---

## Infrastructure state entering Phase 6

The backend ran as a single FastAPI process. It connected to:
- **SQLite** (file-based database, no network)
- **fakeredis** (in-process Redis emulator)
- **FakeChatModel** (in-process LLM stub)

No external vector search service existed. The `rag/` module did not exist.

```mermaid
graph LR
    subgraph Process ["Single Python process (:8001)"]
        APP["FastAPI app"]
        DB["SQLite\n(file: data/enterprise.db)"]
        FAKE_REDIS["fakeredis\n(in-process)"]
        FAKE_LLM["FakeChatModel\n(in-process)"]
        FAKE_EMB["FakeEmbeddings\n(in-process)"]
    end
    APP --> DB
    APP --> FAKE_REDIS
    APP --> FAKE_LLM
    APP --> FAKE_EMB
```

---

## What Phase 6 adds: the vector store layer

Phase 6 introduces a **pluggable vector store** that the app selects via the `VECTOR_STORE` environment variable.

### Offline / test / demo path (`VECTOR_STORE=memory`)

```mermaid
graph LR
    subgraph Process ["Single Python process (:8001)"]
        APP["FastAPI app"]
        FACTORY["get_vector_store()\nreturns MemoryVectorStore"]
        MEM["MemoryVectorStore\n(list of chunks + vectors in RAM)"]
        FAKE_EMB["FakeEmbeddings\n(in-process)"]
        HEALTH["/health/ready\nvector_store: ok (memory, N chunks)"]
    end
    APP --> FACTORY --> MEM
    MEM --> FAKE_EMB
    APP --> HEALTH
```

No new network socket. No new process. No new container.
Everything lives in the same Python process, in RAM.

### Production path (`VECTOR_STORE=qdrant`)

```mermaid
graph LR
    subgraph Process ["FastAPI process (:8001)"]
        APP["FastAPI app"]
        FACTORY["get_vector_store()\nreturns QdrantVectorStore"]
        QD["QdrantVectorStore\n(HTTP client wrapper)"]
        HEALTH["/health/ready\nvector_store: ok (qdrant, N chunks)"]
    end

    subgraph External ["External (Docker or Cloud)"]
        QDRANT["Qdrant service\n(:6333 HTTP / :6334 gRPC)"]
    end

    APP --> FACTORY --> QD
    QD -->|QDRANT_URL + QDRANT_API_KEY| QDRANT
    APP --> HEALTH
```

The Qdrant adapter uses the official `qdrant_client` library over HTTP/gRPC. Credentials come from `.env`:
```
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=              # empty for local Docker, set for Qdrant Cloud
```

---

## Component wiring: how data flows through Phase 6

```mermaid
flowchart TD
    subgraph Ingestion ["Document ingestion (Phase 9 will wire this fully)"]
        FILE["sample_data/documents/*.md"]
        PARSE["parse_document()\nchunking.py"]
        CHUNK["chunk_document()\nchunking.py"]
        ADD["store.add_chunks()\nvector_store.py"]
    end

    subgraph Retrieval ["Retrieval (used by research agent in Phase 11+)"]
        Q["Question string"]
        SEM["store.similarity_search()"]
        KW["store.keyword_search()"]
        RRF["reciprocal_rank_fusion()\nretriever.py"]
        RERANK["rerank()\nretriever.py"]
        EV["Evidence list\nschemas/common.py"]
    end

    subgraph Store ["Vector store (memory or qdrant)"]
        VECTORS["Chunk vectors\n(cosine-indexed)"]
        TOKENS["Chunk token lists\n(BM25 index)"]
    end

    FILE --> PARSE --> CHUNK --> ADD
    ADD --> VECTORS
    ADD --> TOKENS
    Q --> SEM --> VECTORS
    Q --> KW --> TOKENS
    SEM --> RRF
    KW --> RRF
    RRF --> RERANK --> EV
```

---

## Startup sequence (updated for Phase 6)

```mermaid
sequenceDiagram
    participant OS as OS / shell
    participant UV as uv run uvicorn
    participant APP as FastAPI lifespan
    participant VS as VectorStoreService

    OS->>UV: make backend
    UV->>APP: startup event
    APP->>APP: create_tables(), seed()
    APP->>APP: register_redis_check()
    APP->>APP: register_llm_check()
    APP->>VS: get_vector_store() [singleton created]
    VS-->>APP: MemoryVectorStore (or QdrantVectorStore)
    APP->>APP: register_vector_store_check()
    APP-->>OS: :8001 ready
```

The vector store is created lazily on first access; the check is registered at startup. No documents are loaded at startup yet — that happens in Phase 9 (`make ingest`).

---

## Health check output after Phase 6

```json
GET /health/ready

{
  "status": "ok",
  "checks": {
    "app":          { "status": "ok",    "detail": "fastapi" },
    "database":     { "status": "ok",    "detail": "sqlite" },
    "redis":        { "status": "ok",    "detail": "fakeredis" },
    "llm":          { "status": "ok",    "detail": "fake" },
    "vector_store": { "status": "ok",    "detail": "memory (0 chunks)" }
  }
}
```

After `make ingest` (Phase 9) the detail will show `memory (70 chunks)`.

---

## Docker Compose (Phase 15 — not yet active)

When Docker Compose is introduced in Phase 15, Qdrant will be a sidecar container:

```mermaid
graph TD
    subgraph compose ["docker-compose.yml (Phase 15)"]
        BE["backend service\n:8001"]
        QD["qdrant service\n:6333"]
        PG["postgres service\n:5432"]
        NEO["neo4j service\n:7687"]
        RD["redis service\n:6379"]
    end
    BE -->|QDRANT_URL=http://qdrant:6333| QD
    BE -->|DATABASE_URL=postgresql://...| PG
    BE -->|NEO4J_URI=bolt://neo4j:7687| NEO
    BE -->|REDIS_URL=redis://redis:6379| RD
```

For now all stores run in-process. No `docker-compose.yml` file exists yet.

---

## Summary of infrastructure changes in Phase 6

| Component | Before Phase 6 | After Phase 6 |
|-----------|---------------|---------------|
| Vector search | Not present | In-process (memory) or Qdrant (production) |
| New env vars | — | `VECTOR_STORE`, `QDRANT_URL`, `QDRANT_API_KEY` (all already in `.env.example` from Phase 1 spec) |
| New packages | — | `pypdf>=4.0.0` (parsing); `qdrant-client` optional (not in pyproject.toml yet — added in Phase 15) |
| Health check | `llm` | `llm` + `vector_store` |
| External services needed offline | None | None |
| External services needed in production | LLM API | LLM API + Qdrant |
