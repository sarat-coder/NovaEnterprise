# Phase 9 — System Design Evolution: Ingestion and Document Management

## Starting point (end of Phase 8)

After Phase 8, the system could retrieve information from three stores using read-only SQL queries. But the vector store and graph store contained no real document data — there was no pipeline to get documents *into* the system. The system was query-ready but had no content to query.

```mermaid
graph LR
    subgraph "End of Phase 8"
        API[FastAPI :8001]
        SQL[SQL Retriever]
        VS[Vector Store\nempty]
        GS[Graph Store\nseeded manually]
        DB[(SQLite)]
    end
    API --> SQL
    API -.-> VS
    API -.-> GS
    SQL --> DB
```

The vector store was empty. The graph store could only be populated by running `make seed-graph` manually.

---

## Step 1 — Entity extraction layer (P9-1)

The first addition is a pattern-based extractor that reads document text and finds references to known entities: incident IDs like `INC-2031`, service names like `Payments API`, team names like `Payments Platform Team`, and ADR IDs like `ADR-001`.

```mermaid
graph TD
    DOC[Document text] --> EXTRACT[extraction.py]
    EXTRACT -->|entities| NODES[GraphNodes]
    EXTRACT -->|relationships| EDGES[GraphEdges]
    NODES --> GS[Graph Store]
    EDGES --> GS
```

The extractor uses regular expressions, not an LLM, so it works offline with `LLM_PROVIDER=fake`. It is intentionally conservative: a missed entity is safer than a wrong relationship.

---

## Step 2 — Ingest pipeline (P9-2)

The ingest pipeline is the core of Phase 9. It orchestrates all the steps needed to take a raw file and make it searchable.

```mermaid
flowchart TD
    FILE[Raw file\n.md / .txt / .pdf]
    PARSE[Parse\nchunking.parse_document]
    CHUNK[Chunk\nchunking.chunk_document]
    GUARD[Guardrail scan\nguardrails.process_chunk]
    EXTRACT[Entity extraction\nextraction.extract_entities]
    VS[Vector Store\nadd_chunks]
    DB[(Document table\nchunk table)]
    GS[Graph Store\nadd_node / add_edge]

    FILE --> PARSE --> CHUNK --> GUARD
    GUARD -->|safe chunks| VS
    GUARD -->|flagged=true?| DB
    GUARD -->|original text| EXTRACT
    EXTRACT --> GS
    GUARD --> DB
```

Each step has a specific responsibility and can fail independently:
- If the guardrail flags a chunk, the redacted version is stored (not the original)
- If the vector store fails, the error is logged but the pipeline continues
- If a graph edge is a duplicate, the error is silently ignored

---

## Step 3 — Integration protocol layer (P9-3)

The system is designed to eventually pull documents from external tools. We define a `DocumentSource` protocol that any adapter must implement, and ship three mock adapters for testing.

```mermaid
graph TD
    subgraph "Protocol layer"
        PROTO[DocumentSource\nprotocol]
    end
    subgraph "Current adapters"
        LOCAL[LocalDirectoryAdapter\nreads sample_data/documents/]
        CONF[ConfluenceMockAdapter\nreturns stub documents]
        SP[SharePointMockAdapter\nreturns stub documents]
    end
    subgraph "Future adapters"
        REAL_CONF[Real Confluence adapter\nneeds API credentials]
        REAL_SP[Real SharePoint adapter\nneeds Azure credentials]
    end
    PROTO --> LOCAL
    PROTO --> CONF
    PROTO --> SP
    PROTO -.-> REAL_CONF
    PROTO -.-> REAL_SP
```

The demo never requires the real adapters. All tests pass with the mock adapters.

---

## Step 4 — Documents HTTP API and approval service (P9-4, P9-5)

The documents API exposes the ingest pipeline over HTTP and enforces role-based access.

```mermaid
sequenceDiagram
    participant Analyst
    participant API
    participant Ingest
    participant Admin

    Analyst->>API: POST /api/v1/documents/upload (file)
    API->>API: Validate extension + size (N7)
    API->>Ingest: ingest_bytes(content, filename)
    Ingest-->>API: doc_id, chunk_count, flagged
    API-->>Analyst: 201 {doc_id, chunk_count, flagged}

    Analyst->>API: DELETE /api/v1/documents/{id}
    API->>ApprovalService: request_document_delete(id, analyst)
    ApprovalService-->>API: ApprovalRequest {status: "pending"}
    API-->>Analyst: 202 approval pending

    Admin->>API: POST /api/v1/approvals/{id}/approve
    API->>ApprovalService: approve(id, admin)
    ApprovalService->>DB: document.status = "deleted"
    API-->>Admin: 200 {status: "approved"}
```

The document is never deleted immediately. The two-step approval gate (F17) means no data can be lost without a human review.

---

## Step 5 — Knowledge graph API (P9-6)

The final addition is the API that lets users browse the knowledge graph directly.

```mermaid
graph LR
    subgraph "HTTP routes"
        STATS[GET /graph/stats]
        NODES[GET /graph/nodes]
        NODE[GET /graph/nodes/{id}]
        EXPAND[GET /graph/nodes/{id}/neighbors]
        CYPHER[POST /graph/cypher]
    end
    subgraph "Graph store"
        GS[MemoryGraphStore\nor Neo4j]
    end
    STATS --> GS
    NODES --> GS
    NODE --> GS
    EXPAND --> GS
    CYPHER -->|read-only check| GS
```

The Cypher endpoint validates that the query contains no write operations before executing it. If you try `CREATE`, `MERGE`, `DELETE`, or `SET`, you get a 422 error immediately.

---

## Final architecture (end of Phase 9)

```mermaid
graph TB
    UI[Browser / API Client]
    FASTAPI[FastAPI :8001]

    subgraph "New in Phase 9"
        DOC_API[Documents API\nupload / list / delete request]
        GRAPH_API[Graph API\nbrowse / expand / cypher]
        APPROVAL[Approval Service\npending → approved / rejected]
        INGEST[Ingest Pipeline\nparse → chunk → guardrail → store]
        EXTRACT[Entity Extractor\npattern-based]
        INTEGRATION[DocumentSource adapters\nlocal / mock / future real]
    end

    subgraph "Data stores"
        VS[Vector Store\n≈70 chunks after ingest]
        GS[Graph Store\n≈85 nodes / 260 edges]
        DB[(SQLite\ndocuments + chunks + approvals)]
    end

    UI --> FASTAPI
    FASTAPI --> DOC_API
    FASTAPI --> GRAPH_API
    DOC_API --> APPROVAL
    DOC_API --> INGEST
    INGEST --> EXTRACT
    EXTRACT --> GS
    INGEST --> VS
    INGEST --> DB
    GRAPH_API --> GS
    INTEGRATION -.->|future| INGEST
```

The system now has a complete content pipeline. Documents can be uploaded, ingested, and retrieved. The knowledge graph is enriched from document text in addition to the seed data. All destructive operations are gated behind admin approval.
