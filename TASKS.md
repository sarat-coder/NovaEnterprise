# NovaEnterprise — Task tracker

> Concise checklist for GitHub-visible progress.
> Spec: `CLAUDE.md` · Requirements: `PLAN.md` · Phase exit criteria: `PLAN_PHASE.md` · Status: `MEMORY.md` · Git flow: `Git_GitHub_Workflow_Guide.md`

**Branch convention:** `feature/<repo-name>` (one feature branch per sub-task; open the PR against `development`)
**Status:** `Pending ❌` · `Completed ✅`

Sub-tasks in the same phase that do not share files can be open at the same time. Do not stack a branch on another feature branch. When a row names a predecessor, merge that predecessor first.

This file sets the execution order. Each phase waits only for the contract it actually uses. Every task must pass three checks before its PR: `make test` offline (`LLM_PROVIDER=fake`, memory stores, SQLite, fakeredis), `ruff check` and `ruff format --check`. Make targets and `/health/ready` checks are added by the task that builds them. Do not reference one before it exists.

---

## Phase 1 — Runtime skeleton

> Depends on: nothing. Unblocks: every later phase.
> Merge order: P1-1 first. P1-2, P1-4, and P1-5 in parallel after it. P1-3 after P1-2.

| Task | Branch | Status |
|------|--------|--------|
| P1-1 · Settings (`get_settings`, lru_cache) and JSON logging | `feature/backend-config-logging` | Completed ✅ |
| P1-2 · Health routes (`/health`, `/live`, `/ready` check registry) and `X-Request-ID` middleware | `feature/backend-health-request-id` | Completed ✅ |
| P1-3 · Offline pytest harness and fixtures | `feature/test-harness-offline` | Completed ✅ |
| P1-4 · uv project, Makefile (`setup`, `backend`, `test`, `lint`), ruff config, and `.env.example` | `feature/makefile-env-lint` | Completed ✅ |
| P1-5 · CI workflow: ruff and offline pytest | `feature/ci-lint-test` | Completed ✅ |

---

## Phase 2 — Persistence and sample data

> Depends on: P1-1. Unblocks: Phases 3, 5, 7, 8, and 10.
> Merge order: P2-1 and P2-4 in parallel. P2-2 and P2-3 in parallel after P2-1. P2-5 after P2-3 and P2-4.

| Task | Branch | Status |
|------|--------|--------|
| P2-1 · SQLAlchemy models and the shared `Evidence` schema | `feature/sqlalchemy-models-evidence` | Completed ✅ |
| P2-2 · Postgres schema, RLS policies, and migrations | `feature/postgres-schema-rls` | Completed ✅ |
| P2-3 · Repository layer | `feature/repository-layer` | Completed ✅ |
| P2-4 · Sample data JSON and the 15 documents (including the hostile vendor note) | `feature/sample-data-documents` | Completed ✅ |
| P2-5 · Seed service and lifespan bootstrap | `feature/seed-bootstrap` | Completed ✅ |

---

## Phase 3 — Identity and request guards

> Depends on: P1-2 and P2-1. Unblocks: the protected routes in Phases 5, 9, and 12.
> Merge order: P3-1 and P3-3 in parallel. P3-2 after P3-1. P3-4 last because it sets the middleware order.

| Task | Branch | Status |
|------|--------|--------|
| P3-1 · JWT and `require_role` (viewer < analyst < admin) | `feature/jwt-rbac` | Completed ✅ |
| P3-2 · Demo login routes and tokens | `feature/auth-demo-login` | Completed ✅ |
| P3-3 · Redis client, fakeredis fallback, and token-bucket rate limit | `feature/redis-rate-limit` | Completed ✅ |
| P3-4 · Audit middleware and middleware order | `feature/audit-middleware` | Completed ✅ |

---

## Phase 4 — AI providers and guardrails

> Depends on: P1-1. Parallel with: Phases 2 and 3. Unblocks: Phases 6, 10, and 11.
> Merge order: P4-1 first. P4-2 after it because both edit `core/llm.py`. P4-3 and P4-4 in parallel at any time.

| Task | Branch | Status |
|------|--------|--------|
| P4-1 · `get_llm()` provider factory and the fake LLM | `feature/llm-provider-factory` | Completed ✅ |
| P4-2 · `get_embedding_model()` and fake embeddings | `feature/embedding-provider-factory` | Completed ✅ |
| P4-3 · Prompt-injection wrap, scan, and flag | `feature/guardrail-injection` | Completed ✅ |
| P4-4 · Output scrub: secrets and hidden reasoning | `feature/guardrail-output-scrub` | Completed ✅ |

---

## Phase 5 — API contract and browse API

> Depends on: P2-3 and P3-1. Unblocks: Phase 13 (UI shell) and Phase 11 (research schemas). Does not block Phases 6, 7, or 8.
> Merge order: P5-1 first, so the API and the UI share one written contract. P5-2 and P5-3 in parallel after it.

| Task | Branch | Status |
|------|--------|--------|
| P5-1 · `docs/API_CONTRACT.md` and `docs/FRONTEND_ASSUMPTIONS.md` | `feature/api-contract-docs` | Completed ✅ |
| P5-2 · Browse API: customers, incidents, and decisions | `feature/api-browse-records` | Completed ✅ |
| P5-3 · Research request and response schemas | `feature/research-schemas` | Completed ✅ |

---

## Phase 6 — Vector RAG

> Depends on: P2-4, P4-2, and P4-3. Parallel with: Phases 5, 7, 8, 10, and 13.
> Merge order: P6-1 and P6-2 in parallel. P6-3 after P6-2. P6-4 after P6-1 and P6-2.

| Task | Branch | Status |
|------|--------|--------|
| P6-1 · Document parsing (md, txt, PDF) and chunking | `feature/rag-parsing-chunking` | Completed ✅ |
| P6-2 · `VectorStoreService` protocol and memory adapter | `feature/rag-vector-store-memory` | Completed ✅ |
| P6-3 · Qdrant adapter and readiness check | `feature/rag-vector-store-qdrant` | Completed ✅ |
| P6-4 · Hybrid retriever: semantic + BM25 + RRF + rerank | `feature/rag-hybrid-retriever` | Completed ✅ |

---

## Phase 7 — Graph RAG

> Depends on: P2-1 and P2-4. Parallel with: Phases 5, 6, 8, 10, and 13.
> Merge order: P7-1 first. P7-2 and P7-4 in parallel after it. P7-3 after P7-2.

| Task | Branch | Status |
|------|--------|--------|
| P7-1 · `GraphStoreService` protocol and memory adapter | `feature/graph-store-memory` | Completed ✅ |
| P7-2 · Typed traversals that also return their Cypher | `feature/graph-typed-traversals` | Completed ✅ |
| P7-3 · Neo4j adapter, read-only Cypher check, and degraded readiness | `feature/graph-store-neo4j` | Completed ✅ |
| P7-4 · Graph seeding from sample data (`make seed-graph`) | `feature/graph-seed` | Completed ✅ |

---

## Phase 8 — SQL retrieval

> Depends on: P2-3. Parallel with: Phases 5, 6, 7, 10, and 13.
> Merge order: P8-1 and P8-2 in parallel. P8-3 after both.

| Task | Branch | Status |
|------|--------|--------|
| P8-1 · `validate_sql()` and the table and column allowlist | `feature/sql-validator` | Completed ✅ |
| P8-2 · SQL query templates | `feature/sql-templates` | Completed ✅ |
| P8-3 · SQL retriever that records each query and returns `Evidence` | `feature/sql-retriever` | Completed ✅ |

---

## Phase 9 — Ingestion and document management

> Depends on: Phases 6 and 7, and P3-1. Parallel with: Phases 10, 11, and 13.
> Merge order: P9-1, P9-3, and P9-6 in parallel. P9-2 after P9-1. P9-4 after P9-2. P9-5 after P9-4.

| Task | Branch | Status |
|------|--------|--------|
| P9-1 · Entity and relationship extraction | `feature/rag-extraction` | Pending ❌ |
| P9-2 · Ingest pipeline into vector, DB, and graph (`make ingest`) | `feature/rag-ingest-pipeline` | Pending ❌ |
| P9-3 · `DocumentSource` protocol and mock adapters | `feature/integrations-document-sources` | Pending ❌ |
| P9-4 · Documents API with upload validation (size limit and extension allowlist) | `feature/api-documents-upload` | Pending ❌ |
| P9-5 · Approval service and admin-gated document delete | `feature/approval-document-delete` | Pending ❌ |
| P9-6 · Knowledge graph API: browse and expand nodes | `feature/api-knowledge-graph` | Pending ❌ |

---

## Phase 10 — Memory

> Depends on: P2-3, P3-3, and P4-4. Parallel with: Phases 6 through 9. Does not wait for the agents.
> Merge order: P10-1, P10-2, and P10-3 in parallel. P10-4 after all three.

| Task | Branch | Status |
|------|--------|--------|
| P10-1 · Organizational memory scope (fiscal calendar and shared facts) | `feature/memory-organizational` | Pending ❌ |
| P10-2 · Conversation memory in Redis | `feature/memory-conversation` | Pending ❌ |
| P10-3 · The other two scopes (confirm their names first, see CLAUDE.md §16) | `feature/memory-additional-scopes` | Pending ❌ |
| P10-4 · Memory service and analyst-owned memory API | `feature/memory-service-api` | Pending ❌ |

---

## Phase 11 — Research agents

> Depends on: P4-1 and P5-3 to start. P11-3 also needs Phases 6, 7, and 8.
> Merge order: P11-1 first. P11-2, P11-4, and P11-5 in parallel after it. P11-3 after P11-1 once Phases 6, 7, and 8 have merged. Each node branch includes its own test.

| Task | Branch | Status |
|------|--------|--------|
| P11-1 · `ResearchState` and deterministic `agents/rules.py` | `feature/agent-state-rules` | Pending ❌ |
| P11-2 · Analysis nodes: analyze_query, assess_complexity, decompose | `feature/agent-nodes-analysis` | Pending ❌ |
| P11-3 · Routing node and vector, SQL, graph, and hybrid retrieval nodes | `feature/agent-nodes-retrieval` | Pending ❌ |
| P11-4 · collect_evidence, check_missing_evidence, and bounded corrective retrieval | `feature/agent-nodes-corrective` | Pending ❌ |
| P11-5 · verify_evidence, synthesize_answer, and verify_citations | `feature/agent-nodes-verify-synthesize` | Pending ❌ |

---

## Phase 12 — Workflow graph and research API

> Depends on: Phases 10 and 11, and P3-4. Unblocks: Phase 14 research screens and `make demo`.
> Merge order: P12-1 and P12-2 in parallel. P12-3 after both. P12-4 after P12-3. P12-5 last.

| Task | Branch | Status |
|------|--------|--------|
| P12-1 · Workflow tracer (`tracer.node`) and `workflow_events` | `feature/workflow-tracer-events` | Pending ❌ |
| P12-2 · Graph wiring: `GRAPH_NODES`, `GRAPH_EDGES`, `build_graph()` | `feature/graph-wiring` | Pending ❌ |
| P12-3 · Research service: create session, background run, persist after each node | `feature/research-service` | Pending ❌ |
| P12-4 · Research API: 202 start, poll, and events | `feature/api-research` | Pending ❌ |
| P12-5 · `make demo` for the canonical and simple questions | `feature/demo-canonical-question` | Pending ❌ |

---

## Phase 13 — Console shell

> Depends on: P5-1 and P3-2. Parallel with: Phases 6 through 12.
> Merge order: P13-1 and P13-2 in parallel. P13-3 after both. P13-4 after P13-3.

| Task | Branch | Status |
|------|--------|--------|
| P13-1 · Next.js 15 app shell and navigation (:3001) | `feature/frontend-app-shell` | Pending ❌ |
| P13-2 · Typed API client that mirrors `API_CONTRACT.md` | `feature/frontend-api-client` | Pending ❌ |
| P13-3 · Login and role-aware layout | `feature/frontend-auth-layout` | Pending ❌ |
| P13-4 · Browse pages: customers, incidents, and decisions | `feature/frontend-browse-pages` | Pending ❌ |

---

## Phase 14 — Research and knowledge screens

> Depends on: Phase 13. P14-1 and P14-2 also need Phase 12. P14-3 needs only P9-6. P14-4 needs only P9-5.
> Merge order: P14-3 and P14-4 can start before the graph exists. P14-1 and then P14-2 once Phase 12 has merged. P14-5 last.

| Task | Branch | Status |
|------|--------|--------|
| P14-1 · `/search` page | `feature/frontend-search-page` | Pending ❌ |
| P14-2 · `/research/[id]`: 2 s polling, sub-questions, SQL and Cypher, evidence, cited answer, memory, and timeline | `feature/frontend-research-session` | Pending ❌ |
| P14-3 · `/knowledge-graph` explorer | `feature/frontend-knowledge-graph` | Pending ❌ |
| P14-4 · `/documents`: upload and delete request | `feature/frontend-documents` | Pending ❌ |
| P14-5 · Frontend unit tests and lint | `feature/frontend-unit-tests` | Pending ❌ |

---

## Phase 15 — Evaluation and delivery

> Depends on: Phase 12 for the eval suite. Image, Compose, and MCP files do not import the graph.
> Merge order: P15-1 after Phase 12. P15-2, P15-3, and P15-5 in parallel once the app boots. P15-4 after P15-1. P15-6 after P15-2 and P15-3.

| Task | Branch | Status |
|------|--------|--------|
| P15-1 · Eval dataset, `evaluate.py`, and CI thresholds | `feature/eval-metrics-thresholds` | Pending ❌ |
| P15-2 · Backend and frontend Dockerfiles | `feature/docker-images` | Pending ❌ |
| P15-3 · Compose stack: Postgres, Qdrant, Neo4j, and Redis | `feature/docker-compose` | Pending ❌ |
| P15-4 · CI: eval gate and frontend lint | `feature/ci-eval-gate` | Pending ❌ |
| P15-5 · MCP server over the read-only tools | `feature/integrations-mcp-server` | Pending ❌ |
| P15-6 · Deployment hygiene tests | `feature/deployment-hygiene-tests` | Pending ❌ |

---

## Dependency overview

```text
P1 Runtime
  ├─► P2 Data ──┬─► P3 Identity ─► P5 Contract + browse API ─► P13 Console shell ──────┐
  │             ├─► P7 Graph RAG ──┬──────────────────────┐                             │
  │             ├─► P8 SQL ────────┤                      │                             │
  │             └─► P10 Memory ────┼──────────┐           │                             │
  └─► P4 AI providers + guardrails │          │           │                             │
          └─► P6 Vector RAG ───────┤          │           └─► P9 Ingestion + docs API ──┤
                                   │          │                                         │
                                   └─► P11 Research agents ─► P12 Workflow + API ──────►P14 Research screens
                                                                                          └─► P15 Eval + delivery
```

Phases 2 and 4 start together after P1-1. After Phase 2, Phases 6, 7, 8, and 10 run in parallel. Phase 5 waits for Phase 3. Phase 13 starts once the API contract exists and does not wait for the agents. Phase 11 starts its non-retrieval nodes early and joins the three retrieval paths at P11-3. Phase 14 joins the console shell with the research workflow.

---

## Map to PRD requirements

| Requirement | Task |
|-------------|------|
| F1 202 + session id | P12-4 |
| F2 to F4 analyse, complexity, decompose | P11-2 |
| F5 routing | P11-3 |
| F6 hybrid retrieval | P6-4 |
| F7 read-only SQL | P8-1 |
| F8 typed graph traversals | P7-2 |
| F9 corrective retrieval | P11-4 |
| F10 to F12 verify, cite, verify citations | P11-5 |
| F13 ingest | P9-2 |
| F14 graph browse | P9-6 |
| F15 memory scopes | P10-4 |
| F16 events and timings | P12-1 |
| F17 approval on delete | P9-5 |
| N1 offline | P1-3 |
| N2 provider-agnostic | P4-1, P4-2 |
| N3 replaceable stores | P6-2, P7-1 |
| N4 canonical question about 7 s offline | P12-5 |
| N5 `X-Request-ID` | P1-2 |
| N6 rate limit | P3-3 |
| N7 upload validation | P9-4 |
| N8 injection guardrail | P4-3 |
| N9 no hidden reasoning | P4-4 |

---

## Progress summary

| Phase | Name | Tasks | Completed |
|-------|------|-------|-----------|
| 1 | Runtime skeleton | 5 | 5 |
| 2 | Persistence and sample data | 5 | 5 |
| 3 | Identity and request guards | 4 | 4 |
| 4 | AI providers and guardrails | 4 | 4 |
| 5 | API contract and browse API | 3 | 3 |
| 6 | Vector RAG | 4 | 4 |
| 7 | Graph RAG | 4 | 4 |
| 8 | SQL retrieval | 3 | 3 |
| 9 | Ingestion and document management | 6 | 0 |
| 10 | Memory | 4 | 0 |
| 11 | Research agents | 5 | 0 |
| 12 | Workflow graph and research API | 5 | 0 |
| 13 | Console shell | 4 | 0 |
| 14 | Research and knowledge screens | 5 | 0 |
| 15 | Evaluation and delivery | 6 | 0 |
| **Total** | | **67** | **22** |
