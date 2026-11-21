# CLAUDE.md – Project 2: Enterprise Knowledge & Decision Intelligence Platform (NovaEnterprise)

This file is the single source of truth for building the "Enterprise Knowledge & Decision Intelligence
Platform". Read it before writing any code. It is derived from `00-problem.md`, `01-prd.md` and
`02-hld.md`. When this file and a phase plan disagree, this file wins; update it first, then the code.

---

## 1. What we are building

A research platform for a fictional technology company, **NovaEnterprise**. An analyst asks one
enterprise question in natural language and receives a **cited, verified answer** assembled from
documents, database records and a knowledge graph – with the whole retrieval process open to inspection.

```text
Vector RAG  +  Graph RAG  +  SQL  +  Agents  +  Memory
```

**The canonical question** – every stage is built and tested around it:

> Which customers were impacted by the Payments API last quarter, what incidents occurred,
> which teams own those services, and what decisions were taken to prevent recurrence?

No single retrieval call answers it. It needs four lookups in different stores, merged into one cited
answer:

| Part of the question | Answered from | Why not the others |
|---|---|---|
| which customers were impacted | **graph** `(Service)<-[:AFFECTED]-(Incident)-[:IMPACTED]->(Customer)` | the link lives in relationships, not prose |
| what incidents occurred | **SQL** `incidents JOIN services` filtered by date | needs exact records in a date range |
| which teams own those services | **graph** `(Service)-[:OWNED_BY]->(Team)` | one hop, no document says it plainly |
| what decisions prevent recurrence | **hybrid** postmortems + ADR documents (+ graph) | the rationale is narrative text |

**Core teaching concept:** retrieval strategy is a **routing decision made at run time**, not a library
choice. Never hard-code one retriever.

### Non-goals (v1)

- No write access to enterprise systems of record. Every SQL statement and Cypher query is **read-only**.
- No autonomous action. The only mutations are document management; destructive ones need approval.
- No fine-tuning or model training.
- Not a general BI tool: SQL is limited to an allowlisted schema.

---

## 2. Users and roles

| Role | Can | Cannot |
|---|---|---|
| `viewer` | read dashboards; browse customers / incidents / decisions / documents; read research sessions | start research, upload, run Cypher |
| `analyst` | everything viewer can + start research, upload documents, run read-only Cypher, manage own memory | delete documents, reindex, approve |
| `admin` | everything + reindex, approve/reject approval requests, delete documents | – |

Enforced by `require_role` in `backend/app/core/security.py` (`viewer 1 < analyst 2 < admin 3`).
`tests/api/test_api.py::test_auth_required_and_rbac` proves a viewer gets **403** on `POST /api/v1/research`.
Auth: JWT (demo login or Supabase).

---

## 3. Requirements

### 3.1 Functional (F1–F17)

| # | Requirement | Where it lives | Proven by |
|---|---|---|---|
| F1 | Accept a question, return session id immediately (**202**) | `backend/app/api/research.py` | `test_research_lifecycle` |
| F2 | Analyse intent, entities, time range, relationship / aggregation needs | `agents/nodes/analyze_query.py` | `test_canonical_question_end_to_end` |
| F3 | Classify complexity `simple / moderate / complex` | `agents/nodes/assess_complexity.py`, `agents/rules.py` | `test_simple_question_single_subquestion` |
| F4 | Decompose into ≤ `MAX_SUBQUESTIONS` (default 4) sub-questions | `agents/nodes/decompose.py` | `test_canonical_question_end_to_end` |
| F5 | Route each sub-question to `vector`, `sql`, `graph` or `hybrid` | `agents/nodes/route_retrieval.py` | `test_graph_shape_matches_frontend_assumptions` |
| F6 | Hybrid document retrieval: semantic + BM25 + RRF + rerank | `rag/retriever.py` | `tests/rag/test_retrieval_graph.py` |
| F7 | SQL retrieval restricted to a read-only allowlist | `rag/sql_retrieval.py` | `tests/unit/test_sql_validator.py` (8 tests) |
| F8 | Graph retrieval via typed traversals that also expose their Cypher | `rag/graph_store.py` | `test_graph_traversals` |
| F9 | Detect missing evidence; ≤ `MAX_CORRECTIVE_ROUNDS` corrective retrievals | `agents/nodes/check_missing_evidence.py`, `corrective_retrieval.py` | `test_corrective_retrieval_triggers_for_unanswerable_part` |
| F10 | Verify each claim against collected evidence before answering | `agents/nodes/verify_evidence.py` | `test_canonical_question_end_to_end` |
| F11 | Answer carries `[n]` citation markers resolvable to evidence | `agents/nodes/synthesize_answer.py` | `test_multi_hop_citations_and_grounding` |
| F12 | Verify every citation resolves; report invalid ones | `agents/nodes/verify_citations.py` | `test_research_lifecycle` |
| F13 | Ingest md / txt / PDF: chunk, extract entities + relationships, index into vector + DB + graph | `rag/ingest.py` | `test_upload_validation_and_ingest` |
| F14 | Browse the knowledge graph and expand nodes | `backend/app/api/graph.py` | `test_graph_endpoints` |
| F15 | Four separated memory scopes surfaced per session | `memory/memory_service.py` | `test_research_lifecycle` |
| F16 | Expose every node transition, tool call, query and timing | `backend/app/core/observability.py` | `GET /api/v1/research/{id}/events` |
| F17 | Approval gate on destructive admin actions (document delete) | `backend/app/api/documents.py`, `services/approval_service.py` | `test_upload_validation_and_ingest` |

### 3.2 Non-functional (N1–N9)

| # | Requirement | Target / mechanism |
|---|---|---|
| N1 | Runs with **no API key and no external service** | `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`, SQLite, fakeredis |
| N2 | Provider-agnostic AI | 8 providers via `get_llm()` / `get_embedding_model()` in `backend/app/core/llm.py` |
| N3 | Replaceable stores | `VectorStoreService` and `GraphStoreService` protocols |
| N4 | Canonical question completes offline | ~7 s (fake provider, memory stores), measured by `make demo` |
| N5 | Every response carries `X-Request-ID` | `backend/app/middleware/request_context.py` |
| N6 | Rate limiting | Redis token bucket, `RATE_LIMIT_PER_MINUTE` (default 120) |
| N7 | Uploads validated | ≤ `MAX_UPLOAD_MB` (5), extension allowlist |
| N8 | Untrusted content never becomes instructions | wrapped + scanned + flagged (`backend/app/core/guardrails.py`) |
| N9 | No hidden reasoning exposed | only decisions, queries, evidence, timings |

---

## 4. Architecture

Next.js 15 research UI → FastAPI backend → LangGraph research workflow (13 nodes) → **four** data stores
behind replaceable interfaces.

```text
Browser (:3001) ─JWT─▶ Next.js 15 ─REST /api/v1 + X-Request-ID─▶ FastAPI (:8001)
                                                                   │ routers · services · repos
                                                                   │ middleware: req-id, rate limit, audit
                                           ┌───────────────────────┴───────────────┐
                                           ▼                                       ▼
                                  LangGraph research workflow            Read paths (browse pages)
                                           │
     ┌─────────────────────┬───────────────┼──────────────────┬──────────────────────┐
     ▼                     ▼               ▼                  ▼                      ▼
PostgreSQL / SQLite   Qdrant / memory   Neo4j / memory    Redis / fakeredis     LLM provider (get_llm)
records, chunks,      chunk vectors     entities +        cache, conversation
sessions, audit                         relationships     memory, rate limit
```

Managed production forms: **Supabase** (Postgres + Auth + Storage + RLS), **Qdrant Cloud**, **Neo4j Aura**.

### 4.1 Request flow – one research question

1. UI `POST /api/v1/research {question}` → Pydantic validation (5..2000 chars) in `api/research.py`
2. `research_service.create_session()` writes a `research_sessions` row → responds **202** `{session_id, status: "running"}`
3. `BackgroundTasks` → `research_service.start_research()` runs `agents/graph.py` `StateGraph(ResearchState)`
4. Every node wrapped in `tracer.node(...)`; state persisted after **every** node (`research_service._persist`);
   every transition written to `workflow_events`
5. UI polls `GET /api/v1/research/{id}` every 2 s and `GET /api/v1/research/{id}/events`

The frontend never waits on a long request. **The state in the database is the progress bar.**

### 4.2 Layering rules (enforced by review and tests)

| Layer | Folder | Responsibility | MUST NOT |
|---|---|---|---|
| API | `backend/app/api/` | HTTP shape, auth, validation, status codes | contain business logic |
| Services | `backend/app/services/` | run the graph, persist state, approvals, seeding | know about HTTP |
| Repositories | `backend/app/repositories/` | all SQL via SQLAlchemy | be imported by agents directly |
| Core | `backend/app/core/` | config, llm, db, redis, security, logging, guardrails, observability | import from `agents/` (cycle) |
| Agents | `agents/` | graph, nodes, specialists, deterministic rules | talk to HTTP or the browser |
| RAG | `rag/` | parsing, chunking, extraction, vector store, graph store, retrievers, SQL retrieval | know about FastAPI |
| Memory | `memory/` | the four memory scopes | be mixed with retrieval |
| Integrations | `integrations/` | protocols + mock adapters + MCP server | be required for the demo |
| Frontend | `frontend/` | pages, components, typed API client | hold the service-role key |

Import direction is one-way: `api → services → repositories → models`, and `agents / rag / memory → app.core`.
**Core is the bottom layer.**

### 4.3 Folder layout (`project-02-enterprise-intelligence/`)

```text
backend/app/   main.py · api/ · core/ · middleware/ · models/ · schemas/ · repositories/ · services/
agents/        state.py · graph.py · rules.py · prompts.py · nodes/ · specialists/
rag/           ingest.py · chunking · extraction · vector_store.py · graph_store.py · retriever.py · sql_retrieval.py
memory/        memory_service.py (+ one module per scope)
integrations/  protocols.py (DocumentSource, …) · mock adapters · MCP server
frontend/      app/ (/search, /research/[id], /knowledge-graph, /documents, …) · components/ · lib/
database/      schema.sql · rls_policies.sql · seed.sql · migrations/
sample_data/   teams · employees · services · customers · incidents · decisions · projects · tickets
               · organizational_memory (.json) · documents/*.md (15)
tests/         unit/ · api/ · rag/ · agents/ · workflow/ · evaluation/ · deployment/
data/          (git-ignored) enterprise.db
docs/          API_CONTRACT.md · FRONTEND_ASSUMPTIONS.md
```

### 4.4 Key design decisions (do not reverse without updating this file)

| Decision | Instead of | Why |
|---|---|---|
| Strategy chosen at run time by a router node | one fixed retriever | canonical question needs three at once |
| Deterministic `agents/rules.py` on top of LLM output | trust the model | works with `LLM_PROVIDER=fake`; stops relationship questions going vector-only |
| In-memory vector and graph stores | require Docker | `make test` and `make demo` run with zero services |
| Typed graph traversals that also return their Cypher | free-form generated Cypher | safe by construction; students still see the query |
| SQL templates + validator; LLM generation only as an addition | free-form generated SQL | injection and destructive statements become impossible |
| Bounded corrective loop (`MAX_CORRECTIVE_ROUNDS=1`) | retry until satisfied | agent loops must terminate |
| Evidence verification and citation verification as separate nodes | one "check the answer" step | each guarantee is testable alone |
| 202 + background task + polling | long blocking request | AI workflows outlive HTTP timeouts |

---

## 5. Domain data (`sample_data/`)

| File | Contents |
|---|---|
| `teams.json` | 6 teams: Payments Platform, Identity, Data Platform, Customer Success, SRE, Analytics |
| `employees.json` | 20 employees with titles and team membership |
| `services.json` | 8 services: Payments API, Identity Service, Data Pipeline, Analytics Dashboard, Notification Service, Billing Engine, Customer Portal, Search Service |
| `customers.json` | 10 customers across enterprise / mid-market / SMB |
| `incidents.json` | 12 incidents across three quarters, with root causes and impacted customers |
| `decisions.json` | 8 ADRs addressing those incidents |
| `projects.json`, `tickets.json` | 6 projects, 15 tickets |
| `organizational_memory.json` | curated shared facts (e.g. the fiscal calendar – drives "last quarter") |
| `documents/*.md` | 15 docs: 4 postmortems, 3 ADRs, 3 policies, 2 meeting notes, 1 runbook, 1 quarterly reliability summary, 1 **hostile vendor note** |

- The SEV1 the canonical question is about: `documents/postmortem-inc-2031-payments-api-outage.md`.
- `documents/vendor-note-processor-update.md` contains a deliberate **prompt-injection attempt**. It must be
  **indexed as data and flagged, never obeyed**.
- Graph relationships at minimum: `(Incident)-[:AFFECTED]->(Service)`, `(Incident)-[:IMPACTED]->(Customer)`,
  `(Service)-[:OWNED_BY]->(Team)`, plus decision ↔ incident links. Offline graph size ≈ 85 nodes / 260 edges;
  vector store ≈ 70 chunks.

---

## 6. Agents and workflow

### 6.1 LangGraph (`agents/graph.py`)

`GRAPH_NODES`, `GRAPH_EDGES`, `build_graph()`. 13 nodes, each wrapped in `tracer.node(...)`:

```text
analyze_query → assess_complexity → decompose → route_retrieval
   → {vector | sql | graph | hybrid} retrieval per sub-question
   → collect_evidence (merge + dedupe + assign ids)
   → check_missing_evidence ─missing & rounds < MAX─▶ corrective_retrieval ─▶ collect_evidence
                            └─ complete ─▶ verify_evidence → synthesize_answer → verify_citations → END
```

Node ids are what the frontend renders; the graph shape is guarded by
`test_graph_shape_matches_frontend_assumptions` and `docs/FRONTEND_ASSUMPTIONS.md`.

### 6.2 The rules-plus-LLM pattern (non-negotiable)

`agents/rules.py` holds deterministic analysis, decomposition and routing rules. The LLM proposes; rules
correct. A question that needs relationships must never be routed vector-only, regardless of what the
model says. Everything must work with `LLM_PROVIDER=fake`.

Expected behaviour:
- **Canonical question** → complexity `complex`, entity `Payments API`, time range `last quarter`, 4 sub-questions
  (`sq1 graph`, `sq2 sql`, `sq3 graph`, `sq4 hybrid`), 1 SQL query, 3 Cypher traversals, 9 evidence items,
  `strategies_used = graph, sql, vector`, corrective rounds 0.
- **Simple question** ("What is our data retention policy?") → complexity `simple`, exactly 1 sub-question,
  no SQL, no Cypher, `strategies_used = [vector]`.

### 6.3 Evidence – one shape for all stores

All three retrieval paths return the same `Evidence` model (`backend/app/schemas/common.py`), differing only in
`source_type` (`document` / `sql` / `graph`) and `locator`. That is what makes one numbered citation list
possible. Never introduce a store-specific evidence shape.

### 6.4 Memory (`memory/`)

Four **separated** memory scopes, surfaced per session via `memory_service.py` (F15). Shared organizational
facts come from `organizational_memory.json`; conversation memory lives in Redis. Memory is never mixed with
retrieval. Analysts manage only their own memory.

---

## 7. Retrieval

### 7.1 Vector / hybrid (`rag/retriever.py`)
Semantic ∪ BM25 → reciprocal rank fusion → rerank. Protocol `VectorStoreService`; `memory` or `qdrant` chosen by
`VECTOR_STORE`. Nothing outside `rag/` knows which.

### 7.2 SQL (`rag/sql_retrieval.py`)
Templates first; `validate_sql()` on **every** statement, LLM-generated or not:
single `SELECT` only, allowlisted tables/columns, no DDL/DML, no multiple statements, no comments tricks.
Every query that runs is recorded and shown.

### 7.3 Graph (`rag/graph_store.py`)
Protocol `GraphStoreService`; `memory` or `neo4j` chosen by `GRAPH_STORE`. Typed traversals (e.g. impacted
customers, owning teams, related decisions) that **also return the Cypher** they represent. User-entered Cypher
(analyst) is read-only. If Neo4j is down, `/health/ready` reports `degraded` and graph sub-questions record an
error instead of crashing the workflow.

### 7.4 Ingestion (`rag/ingest.py`)
md / txt / PDF → parse → chunk → extract entities and relationships → index into vector store + DB + graph.
Real sources plug in via `integrations/protocols.py` `DocumentSource` (Confluence, SharePoint, Drive, ticketing).

---

## 8. Guardrails and security

- **Prompt injection (N8):** every document chunk is untrusted. Wrap it, scan it, flag it. The vendor note must
  be retrievable as evidence but its instructions must never change routing, queries or the answer.
- **Read-only data access:** SQL validator + typed Cypher. No write path from the research workflow.
- **Approvals (F17):** document delete creates an approval request; only `admin` approves.
- **Uploads (N7):** size ≤ `MAX_UPLOAD_MB`, extension allowlist.
- **Secrets:** only in `.env` (git-ignored); `.env.example` lists every variable with placeholders.
- **Request IDs (N5), rate limiting (N6), audit log** on state-changing requests – via middleware.
- **No hidden reasoning (N9):** expose decisions, queries, evidence, timings – never raw chain-of-thought.

---

## 9. Backend conventions

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, LangChain/LangGraph, pytest. Package manager: **uv**.
- `main.py` lifespan: create tables → seed → build graph → ingest documents.
- Routers under `/api/v1`; health unprefixed: `/health`, `/health/live`, `/health/ready`
  (database, redis, vector_store, graph_store, llm – each with a `detail` naming the real backing store).
- `get_settings()` is `lru_cache`d – **restart the backend after editing `.env`**.
- Errors: `{ "detail": string }` with correct status codes.
- Graph execution runs in-process for v1 (production extension: worker + `langgraph-checkpoint-postgres`).

### 9.1 Environment variables (`.env.example` must list every one)

```text
LLM_PROVIDER            fake (default) | openai | anthropic | …   (+ LLM_API_KEY, LLM_MODEL)
EMBEDDING_PROVIDER, EMBEDDING_MODEL
VECTOR_STORE            memory | qdrant      (QDRANT_URL, QDRANT_API_KEY)
GRAPH_STORE             memory | neo4j       (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
DATABASE_URL            sqlite (data/enterprise.db) | postgresql
REDIS_URL               empty → fakeredis
MAX_SUBQUESTIONS=4, MAX_CORRECTIVE_ROUNDS=1
RATE_LIMIT_PER_MINUTE=120, MAX_UPLOAD_MB=5
JWT_SECRET, SUPABASE_* , CORS_ORIGINS
```

---

## 10. Frontend conventions

- Next.js 15 App Router, TypeScript, Tailwind, port **3001**.
- Pages: `/search`, `/research/[id]`, `/knowledge-graph`, `/documents`, plus browse pages for customers,
  incidents, decisions.
- Backend reached only through a typed API client mirroring `docs/API_CONTRACT.md`.
- `/research/[id]` polls every 2 s and shows: analysis, sub-questions with strategy, SQL + Cypher that ran,
  evidence list, verification ratio, cited answer, memory scopes, event timeline.
- Role-aware UI: viewers cannot start research, upload, or run Cypher.

---

## 11. API contract

`docs/API_CONTRACT.md` is the source of truth; `docs/FRONTEND_ASSUMPTIONS.md` lists extra guarantees the UI
depends on. If an endpoint changes, update the contract, `backend/app/schemas/`, and the frontend types **in
the same change**.

---

## 12. Testing and evaluation

Tests run **fully offline** (no API key, no Docker): fake LLM, memory vector + graph stores, SQLite, fakeredis.

| Folder | Proves |
|---|---|
| `tests/unit/` | SQL validator (8 tests), rules, guardrails, provider selection |
| `tests/api/` | auth + RBAC, research lifecycle, upload validation + ingest + approval, graph endpoints, request id |
| `tests/rag/` | hybrid retrieval, graph traversals |
| `tests/workflow/` | canonical question e2e, simple question, corrective retrieval, multi-hop citations, graph shape |
| `tests/evaluation/` | metrics over `datasets/eval_cases.json` (`evaluate.py`) |

**Evaluation thresholds (fail the build):**

| Metric | CI threshold | Observed offline |
|---|---|---|
| retrieval relevance | ≥ 0.80 | 1.00 |
| SQL correctness | = 1.00 | 1.00 |
| graph correctness | = 1.00 | 1.00 |
| multi-hop coverage | ≥ 0.66 | 1.00 |
| citation support | = 1.00 | 1.00 |
| answer grounding | ≥ 0.50 | 1.00 |

Thresholds stay below observed scores on purpose: fail on regression, not noise. Every PRD row (F/N) must map
to at least one test; add the mapping when you add a feature.

---

## 13. Commands

```bash
cd project-02-enterprise-intelligence
make setup            # .venv + deps (uv) + .env
make backend          # FastAPI on :8001
make demo             # canonical question, prints every stage
make demo QUESTION="What is our data retention policy?"
make ingest           # (re)index documents
make seed-graph       # build the graph when running scripts directly
make test             # offline pytest
make lint             # ruff
.venv/Scripts/python.exe -m tests.evaluation.evaluate    # metrics table
curl -s localhost:8001/health/ready | python -m json.tool
```

Windows: use `.venv/Scripts/python.exe`; `PYTHONPATH` must include `backend` (`;` separator); set
`PYTHONIOENCODING=utf-8` for CLI output with box-drawing characters.

Make targets are added alongside the task that implements them – do not reference a target before it exists.

### Common errors
- Seeded DB but documents missing → `make ingest`, or delete `data/enterprise.db` and re-run `make demo`.
- Empty graph results → `make seed-graph`.
- Two servers on :8001 (container + local uvicorn) → check `docker ps`.
- `MAX_SUBQUESTIONS=1` under-answers the canonical question – the corrective loop cannot fix missing decomposition.

---

## 14. Delivery workflow

- Development is driven by `TASKS.md` (phases → sub-tasks, each on a `feature/<name>` branch). Status is
  `Pending ❌` or `Completed ✅`.
- Git flow: see `Git_GitHub_Workflow_Guide.md`. Feature branches → `development` → `testing` → `main`.
- At the end of each task: update `.gitignore` if needed, and provide a short PR description.
- After each phase, produce under `internal/`: `explain_codebase/phase#_explained.md` (non-technical),
  `design_evolution/Phase#_Project_System_Design_Evolution.md`, `Infra_design_evolution/Phase#_Infra_design_evolution.md`,
  `QnA/Phase#_Interview_QnA.md` – with mermaid diagrams where relevant.
- Lint must be clean before finishing any task: `ruff check` + `ruff format --check` (Python), `npm run lint` (frontend).

### Honest status rule
Track **implemented**, **validated locally**, **needs credentials**, **deployed** separately. Never claim
something passes in CI or is deployed until it has.

---

## 15. Coding rules

1. **Read before you write.** Check the PRD row, `API_CONTRACT.md` and the existing test first.
2. **Keep the layers clean** (§4.2). Core never imports agents.
3. **Rules first, LLM second.** Routing, complexity and decomposition must be deterministic and tested.
4. **One Evidence shape.** Every retriever returns `Evidence`; every claim cites an evidence id.
5. **Read-only retrieval.** All SQL through `validate_sql()`; all Cypher through typed traversals or a read-only check.
6. **Untrusted by default.** Document text is data, never instruction.
7. **Offline first.** New behaviour must pass `make test` with `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`.
8. **Bounded loops.** Corrective retrieval respects `MAX_CORRECTIVE_ROUNDS`.
9. **Degrade, don't crash.** A failed store records an error on the sub-question; the workflow continues.
10. **Persist after every node.** The DB state is the UI's progress bar.
11. **Never commit** `.env`, `data/`, `*.db`, or any real key.
12. **One change, one test.** Each feature maps to a PRD row and a test.
13. **`make demo` must still work** at the end of every phase.

### 15.1 Things that must never happen
- A write / DDL statement reaching the database from the research workflow.
- The vendor note's instructions changing routing, queries or the answer.
- An answer shipped with a `[n]` citation that does not resolve to evidence.
- A `viewer` starting research, uploading, or running Cypher (must be 403).
- A document deleted without a recorded admin approval.
- An unbounded agent loop.
- Hidden chain-of-thought or secrets in events, logs or API responses.

---

## 16. Known gaps and open questions

- Course documents referenced but not in this repo: `05-rag.md`, `06-tools.md`, `16-observability.md`,
  `README.md`, `docs/API_CONTRACT.md`, `docs/FRONTEND_ASSUMPTIONS.md`. Sections above derived from them are
  inferred and must be checked once available.
- The exact names of the per-strategy retrieval nodes (to make up the 13) and of the four memory scopes are
  not specified – confirm before implementing `agents/graph.py` and `memory/`.
- Exact `MAX_UPLOAD_MB` extension allowlist and SQL allowlist (tables/columns) to be fixed in code and recorded here.
- Git remote URL not yet defined.
- `CLAUDE_v1.md` is the Project 1 (CloudDesk) reference and is not authoritative for this project.

---

## 17. Project files and Claude Code routing

| File | Purpose |
|---|---|
| `TASKS.md` | execution order: phases → sub-tasks → `feature/<name>` branches |
| `PLAN.md` | requirement catalog: acceptance criteria, test and task per F/N row |
| `PLAN_PHASE.md` | exit criteria, tests and demo checkpoint per phase |
| `MEMORY.md` | locked decisions, honest status, open questions, change log – update when status changes |
| `.claude/rules/*.md` | path-scoped conventions (backend, agents, rag, memory, data, frontend, tests) |

Routing: start a task → `/start-task <id>` · plan → `/plan` · routine change → `/implement` · tests → `/test` ·
diff → `/review` · finish a task + PR text → `/finish-task <id>` · end of phase → `/close-phase <n>` ·
design doubt → `/consult-opus` · long logs → log-triage agent.
