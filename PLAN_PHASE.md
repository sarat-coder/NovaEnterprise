# PLAN_PHASE.md — NovaEnterprise phase exit criteria

> What "done" means for each phase in `TASKS.md`. A phase is closed only when **every** exit criterion holds,
> its tests pass offline, lint is clean, and the phase documents exist under `internal/`.
> Requirements: `PLAN.md` · Status: `MEMORY.md` · Spec: `CLAUDE.md`

**Every phase also requires**
- `make test` passes offline, and `ruff check` and `ruff format --check` are clean (from Phase 13 also `npm run lint`).
- `make demo` still works (from Phase 12, when it exists — CLAUDE.md §15 rule 13).
- New env vars are in `.env.example`; new generated paths are in `.gitignore`.
- `MEMORY.md` status row updated; TASKS.md rows set to `Completed ✅` after merge.
- Phase docs written (use `/close-phase <n>`):
  `internal/explain_codebase/phase<n>_explained.md`,
  `internal/design_evolution/Phase<n>_Project_System_Design_Evolution.md`,
  `internal/Infra_design_evolution/Phase<n>_Infra_design_evolution.md`,
  `internal/QnA/Phase<n>_Interview_QnA.md`.

---

## Phase 1 — Runtime skeleton

**Exit criteria**
- `make setup` creates `.venv` with uv and copies `.env.example` to `.env` if missing.
- `make backend` serves FastAPI on :8001; `/health` and `/health/live` return 200.
- `/health/ready` returns `{status, checks}` from a check registry (empty or app-only at this point).
- Every response, including errors, carries `X-Request-ID` (echoed when sent, generated otherwise); JSON logs include it.
- `get_settings()` reads env, is `lru_cache`d, and tests can reset it.
- CI runs ruff and pytest on every PR to `development`.

**Tests:** `tests/api/test_health.py`, `tests/api/test_request_id.py` (N5), offline fixtures in `tests/conftest.py` (N1).
**Demo checkpoint:** `curl -si localhost:8001/health` shows 200 and an `X-Request-ID` header.

## Phase 2 — Persistence and sample data

**Exit criteria**
- Startup creates tables in SQLite (`data/enterprise.db`) and seeds: 6 teams, 20 employees, 8 services, 10 customers,
  12 incidents, 8 decisions, 6 projects, 15 tickets, organizational memory.
- `sample_data/documents/` has the 15 documents, including `postmortem-inc-2031-payments-api-outage.md` and the
  hostile `vendor-note-processor-update.md`.
- `Evidence` schema exists in `backend/app/schemas/common.py` with `source_type` ∈ {document, sql, graph} and `locator`.
- `database/schema.sql`, `rls_policies.sql`, `seed.sql` and migrations exist (Postgres apply = needs credentials).
- Repositories are the only SQL path; `/health/ready` reports `database: ok (sqlite)`.

**Tests:** seed counts, repository CRUD-read tests, `Evidence` validation.
**Demo checkpoint:** delete `data/enterprise.db`, start the backend, row counts match the list above.

## Phase 3 — Identity and request guards

**Exit criteria**
- No token → 401; viewer on an analyst route → 403; role order viewer < analyst < admin.
- Demo login issues JWTs for the three roles.
- Rate limit returns 429 after `RATE_LIMIT_PER_MINUTE`; works on fakeredis when `REDIS_URL` is empty.
- State-changing requests write an audit row; middleware order is request-id → rate limit → audit.
- `/health/ready` reports `redis: ok (fakeredis|real)`.

**Tests:** `test_auth_required_and_rbac` (initial form), `test_rate_limit`, `test_audit_log`.
**Demo checkpoint:** log in as viewer and analyst; the viewer is refused an analyst route.

## Phase 4 — AI providers and guardrails

**Exit criteria**
- `get_llm()` and `get_embedding_model()` select among 8 providers by env; `fake` is the default and deterministic.
- Selecting a real provider without a key fails with a clear message, not at import time.
- Guardrails wrap every chunk as untrusted data, scan it, and flag the vendor note's injection attempt.
- Output scrub removes secrets and hidden reasoning from events, logs and responses.
- `/health/ready` reports `llm: ok` with the provider detail.

**Tests:** `tests/unit/test_providers.py` (N2), `tests/unit/test_guardrails.py` (N8), `tests/unit/test_output_scrub.py` (N9).
**Demo checkpoint:** the vendor note text run through the guardrail comes back flagged.

## Phase 5 — API contract and browse API

**Exit criteria**
- `docs/API_CONTRACT.md` lists every planned endpoint, request, response and status code;
  `docs/FRONTEND_ASSUMPTIONS.md` lists the graph node ids and polling guarantees.
- Customers, incidents and decisions list/detail endpoints return seeded data to any role.
- Research request/response Pydantic schemas exist and enforce 5..2000 chars.
- Errors use `{ "detail": string }`.

**Tests:** browse endpoint tests per role; schema validation tests.
**Demo checkpoint:** `GET /api/v1/incidents` returns 12 incidents.

## Phase 6 — Vector RAG

**Exit criteria**
- md, txt and PDF parse; chunking yields ≈ 70 chunks over the 15 documents.
- `VectorStoreService` protocol with memory and Qdrant adapters chosen by `VECTOR_STORE`; nothing outside `rag/` knows which.
- Hybrid retriever: semantic ∪ BM25 → RRF → rerank; returns `Evidence(source_type="document")`.
- `/health/ready` reports `vector_store: ok (memory (N chunks))`.

**Tests:** `tests/rag/test_retrieval_graph.py` (hybrid part, F6); chunking tests.
**Demo checkpoint:** a Payments API outage query ranks the INC-2031 postmortem first.
**Needs credentials:** Qdrant adapter validated only under Docker Compose (Phase 15).

## Phase 7 — Graph RAG

**Exit criteria**
- `GraphStoreService` protocol with memory and Neo4j adapters chosen by `GRAPH_STORE`.
- `make seed-graph` builds ≈ 85 nodes / 260 edges with at least AFFECTED, IMPACTED, OWNED_BY and decision ↔ incident links.
- Typed traversals (impacted customers, owning teams, related decisions) return results **and** their Cypher, as `Evidence(source_type="graph")`.
- User Cypher is read-only (CREATE, MERGE, DELETE, SET, REMOVE, DROP rejected).
- Neo4j down → `/health/ready` is `degraded`; nothing crashes.

**Tests:** `test_graph_traversals` (F8), read-only Cypher tests, degraded readiness test.
**Demo checkpoint:** customers impacted by Payments API incidents last quarter, with the Cypher shown.

## Phase 8 — SQL retrieval

**Exit criteria**
- `validate_sql()` accepts one `SELECT` on allowlisted tables/columns and rejects DDL, DML, multiple statements and comment tricks.
- Templates cover incidents by service and date range.
- Every executed query is recorded and returned as `Evidence(source_type="sql")`.

**Tests:** `tests/unit/test_sql_validator.py` — 8 tests (F7); template tests.
**Demo checkpoint:** Payments API incidents last quarter via the template, query text shown.

## Phase 9 — Ingestion and document management

**Exit criteria**
- `make ingest` (and startup) indexes documents into vector store + DB + graph with extracted entities and relationships.
- The vendor note is indexed as data and flagged, never obeyed.
- Upload: > 5 MB → 413, bad extension → 415, valid file ingested; analyst may upload, viewer may not.
- Delete creates an approval request; only admin approves; deletion happens only after a recorded approval.
- Graph API lists and expands nodes.
- `DocumentSource` protocol with mock adapters exists and is not needed by the demo.

**Tests:** `test_upload_validation_and_ingest` (F13, F17, N7), `test_graph_endpoints` (F14).
**Demo checkpoint:** upload a markdown file, find it via retrieval, request delete, approve as admin.

## Phase 10 — Memory

**Exit criteria**
- Four separated scopes (names confirmed — MEMORY.md Q2); organizational memory resolves "last quarter" from the fiscal calendar.
- Conversation memory lives in Redis (fakeredis offline).
- Analysts read and manage only their own memory.
- Memory is never fed into retrieval as evidence.

**Tests:** per-scope tests; ownership test; "last quarter" resolution test.
**Demo checkpoint:** a session lists all four scopes with content.

## Phase 11 — Research agents

**Exit criteria**
- `agents/rules.py` makes analysis, complexity, decomposition and routing deterministic under `LLM_PROVIDER=fake`.
- Canonical question → `complex`, 4 sub-questions with strategies graph / sql / graph / hybrid.
- Simple question → `simple`, 1 sub-question, vector only, no SQL, no Cypher.
- Relationship questions are never routed vector-only, whatever the LLM says.
- Corrective retrieval is bounded by `MAX_CORRECTIVE_ROUNDS`; verification and citation nodes are separate.
- A failed store records an error on its sub-question; the workflow continues.

**Tests:** node unit tests; `test_simple_question_single_subquestion` (F3);
`test_corrective_retrieval_triggers_for_unanswerable_part` (F9).
**Demo checkpoint:** run the nodes in sequence in a test and print the sub-question table.

## Phase 12 — Workflow graph and research API

**Exit criteria**
- `build_graph()` wires 13 nodes; `GRAPH_NODES` / `GRAPH_EDGES` match `docs/FRONTEND_ASSUMPTIONS.md`.
- `POST /api/v1/research` → 202; the run happens in a background task; state persisted after every node.
- `GET /api/v1/research/{id}` shows progress; `/events` lists every node transition, query and timing.
- `make demo` runs the canonical question offline in ≈ 7 s with 9 evidence items, 1 SQL query, 3 Cypher traversals,
  `strategies_used = graph, sql, vector`, all citations valid.

**Tests:** `test_research_lifecycle` (F1, F12, F15, F16), `test_canonical_question_end_to_end` (F2, F4, F10),
`test_graph_shape_matches_frontend_assumptions` (F5), `test_multi_hop_citations_and_grounding` (F11),
`test_auth_required_and_rbac` (final form).
**Demo checkpoint:** `make demo` and `make demo QUESTION="What is our data retention policy?"`.

## Phase 13 — Console shell

**Exit criteria**
- Next.js 15 app on :3001 with navigation; `npm run lint` and `npm run build` clean.
- Typed API client mirrors `docs/API_CONTRACT.md`; no service-role key in the frontend.
- Demo login; role-aware layout hides research, upload and Cypher from viewers.
- Customers, incidents and decisions pages render from the API.

**Tests:** client type checks; layout role tests.
**Demo checkpoint:** log in as viewer and analyst; compare the navigation.

## Phase 14 — Research and knowledge screens

**Exit criteria**
- `/search` starts research and routes to `/research/[id]`.
- `/research/[id]` polls every 2 s and shows analysis, sub-questions with strategy, SQL and Cypher, evidence,
  verification ratio, cited answer, memory scopes and the event timeline.
- `/knowledge-graph` browses and expands nodes; `/documents` uploads and requests deletion.
- Frontend unit tests pass.

**Tests:** frontend unit tests per page.
**Demo checkpoint:** ask the canonical question in the browser and watch the steps fill in.

## Phase 15 — Evaluation and delivery

**Exit criteria**
- `evaluate.py` scores `eval_cases.json`; all metrics meet the thresholds in `PLAN.md` §6; CI fails on regression.
- Backend and frontend Dockerfiles build; `docker compose up` runs Postgres, Qdrant, Neo4j and Redis, and
  `/health/ready` names the real stores.
- CI runs ruff, pytest, the eval gate and `npm run lint`.
- MCP server exposes read-only tools only.
- Deployment hygiene tests: no `.env` or keys in images or git; `.env.example` lists every variable.

**Tests:** `tests/evaluation/test_evaluation.py`, `tests/deployment/`.
**Demo checkpoint:** canonical question against the Compose stack.
**Needs credentials:** any cloud deploy. Record it in MEMORY.md only after a real apply.
