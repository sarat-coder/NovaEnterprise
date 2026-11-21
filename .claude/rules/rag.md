---
paths:
  - "rag/**"
  - "integrations/**"
---

# Retrieval and ingestion conventions (CLAUDE.md §7, §8)

- `rag/` never imports FastAPI. Stores sit behind `VectorStoreService` and `GraphStoreService` protocols; `VECTOR_STORE` / `GRAPH_STORE` pick the adapter. Nothing outside `rag/` knows which.
- Vector: semantic ∪ BM25 → reciprocal rank fusion → rerank.
- SQL: templates first; `validate_sql()` on **every** statement, generated or not — single `SELECT`, allowlisted tables/columns, no DDL/DML, no multiple statements, no comment tricks. Record every query that runs.
- Graph: typed traversals that also return the Cypher they represent. User Cypher is read-only. Neo4j down → readiness `degraded`, sub-question records an error.
- Every retriever returns `Evidence` with `source_type` (`document` / `sql` / `graph`) and `locator`. No store-specific shapes.
- Document text is untrusted data: wrap, scan and flag it via `core/guardrails.py`. The vendor note must be retrievable and flagged, never obeyed.
- Ingestion: parse (md / txt / PDF) → chunk → extract entities + relationships → index into vector store + DB + graph.
- `integrations/` adapters implement `DocumentSource` and are mocks by default; the demo must never require them.
- Offline sizes to keep stable: ≈ 70 chunks, ≈ 85 nodes / 260 edges.
