# PLAN.md — NovaEnterprise requirement catalog

> Every requirement, how it is accepted, which test proves it, and which TASKS.md sub-task delivers it.
> Source: `Docs/01-prd.md` and `CLAUDE.md` §3. If this file and CLAUDE.md disagree, CLAUDE.md wins.
> Execution order: `TASKS.md` · Phase exit criteria: `PLAN_PHASE.md` · Status: `MEMORY.md`

Rule: a requirement is **done** only when its test exists and passes offline (`make test`).

---

## 1. Goal

An analyst asks one question in natural language and gets a **cited, verified answer** built from documents
(vector RAG), records (SQL) and relationships (graph RAG), with every step visible.

The canonical question — every stage is tested against it:

> Which customers were impacted by the Payments API last quarter, what incidents occurred,
> which teams own those services, and what decisions were taken to prevent recurrence?

Expected offline result: complexity `complex`; entity `Payments API`; time range `last quarter`;
4 sub-questions (`sq1 graph`, `sq2 sql`, `sq3 graph`, `sq4 hybrid`); 1 SQL query; 3 Cypher traversals;
9 evidence items; `strategies_used = graph, sql, vector`; 0 corrective rounds; ≈ 7 s.

---

## 2. Functional requirements

| # | Requirement | Acceptance criteria | Test | Task |
|---|-------------|---------------------|------|------|
| F1 | Accept a question, return a session id immediately | `POST /api/v1/research` → **202** `{session_id, status:"running"}`; question 5..2000 chars else 422 | `test_research_lifecycle` | P12-4 |
| F2 | Analyse intent, entities, time range, relationship / aggregation needs | canonical → entity `Payments API`, time `last quarter`, `needs_relationships=true` | `test_canonical_question_end_to_end` | P11-2 |
| F3 | Classify complexity | canonical → `complex`; "What is our data retention policy?" → `simple` | `test_simple_question_single_subquestion` | P11-2 |
| F4 | Decompose into ≤ `MAX_SUBQUESTIONS` | canonical → 4; simple → 1; never more than the setting | `test_canonical_question_end_to_end` | P11-2 |
| F5 | Route each sub-question | strategy ∈ {vector, sql, graph, hybrid}; relationship questions never vector-only | `test_graph_shape_matches_frontend_assumptions` | P11-3 |
| F6 | Hybrid document retrieval | semantic ∪ BM25 → RRF → rerank; INC-2031 postmortem ranks top for the outage query | `tests/rag/test_retrieval_graph.py` | P6-4 |
| F7 | Read-only SQL | single `SELECT` on allowlisted tables/columns; DDL, DML, multi-statement and comment tricks rejected | `tests/unit/test_sql_validator.py` (8 tests) | P8-1 |
| F8 | Typed graph traversals that expose Cypher | impacted customers, owning teams, related decisions return results **and** their Cypher | `test_graph_traversals` | P7-2 |
| F9 | Detect missing evidence; bounded correction | missing part triggers ≤ `MAX_CORRECTIVE_ROUNDS` rounds, then continues | `test_corrective_retrieval_triggers_for_unanswerable_part` | P11-4 |
| F10 | Verify claims against evidence | each claim marked supported / unsupported; ratio exposed | `test_canonical_question_end_to_end` | P11-5 |
| F11 | `[n]` citation markers | every claim in the answer carries ≥ 1 marker that maps to an evidence id | `test_multi_hop_citations_and_grounding` | P11-5 |
| F12 | Verify citations | unresolved markers listed as invalid; none in the canonical answer | `test_research_lifecycle` | P11-5 |
| F13 | Ingest md / txt / PDF | parse → chunk → extract → index into vector + DB + graph; ≈ 70 chunks, ≈ 85 nodes / 260 edges | `test_upload_validation_and_ingest` | P9-2 |
| F14 | Browse and expand the knowledge graph | list nodes, expand neighbours by id | `test_graph_endpoints` | P9-6 |
| F15 | Four separated memory scopes per session | session response lists 4 scopes; memory never mixed into retrieval | `test_research_lifecycle` | P10-4 |
| F16 | Expose node transitions, tool calls, queries, timings | `GET /api/v1/research/{id}/events` lists one event per node with timing | `test_research_lifecycle` | P12-1 |
| F17 | Approval gate on document delete | delete creates an approval request; only `admin` approves; no delete without a recorded approval | `test_upload_validation_and_ingest` | P9-5 |

## 3. Non-functional requirements

| # | Requirement | Acceptance criteria | Test / evidence | Task |
|---|-------------|---------------------|-----------------|------|
| N1 | Runs with no API key and no external service | `make test` and `make demo` pass with fake LLM, memory stores, SQLite, fakeredis | CI job without secrets | P1-3 |
| N2 | Provider-agnostic AI | `get_llm()` / `get_embedding_model()` select 8 providers by env; fake is default | `tests/unit/test_providers.py` | P4-1, P4-2 |
| N3 | Replaceable stores | `VectorStoreService` and `GraphStoreService` protocols; nothing outside `rag/` knows the backend | `/health/ready` detail names the store | P6-2, P7-1 |
| N4 | Canonical question offline ≈ 7 s | measured by `make demo` | demo output timing | P12-5 |
| N5 | `X-Request-ID` on every response | echoed if sent, generated if not; present on errors too | `tests/api/test_request_id.py` | P1-2 |
| N6 | Rate limiting | token bucket, `RATE_LIMIT_PER_MINUTE` (120); 429 when exceeded | `tests/api/test_rate_limit.py` | P3-3 |
| N7 | Uploads validated | > `MAX_UPLOAD_MB` (5) → 413; extension outside allowlist → 415 | `test_upload_validation_and_ingest` | P9-4 |
| N8 | Untrusted content never becomes instructions | chunks wrapped + scanned + flagged; vendor note retrievable but cannot change routing, queries or answer | `tests/unit/test_guardrails.py` | P4-3 |
| N9 | No hidden reasoning exposed | events, logs and responses carry decisions, queries, evidence, timings only; secrets scrubbed | `tests/unit/test_output_scrub.py` | P4-4 |

## 4. Roles (RBAC)

| Role | Allowed | Must get 403 on |
|------|---------|-----------------|
| `viewer` | read dashboards, browse records, read sessions | start research, upload, run Cypher |
| `analyst` | viewer + research, upload, read-only Cypher, own memory | delete, reindex, approve |
| `admin` | everything | — |

Proven by `tests/api/test_api.py::test_auth_required_and_rbac` (P3-1, extended in P12-4).

## 5. Must-never list → guard

| Must never happen | Guard | Task |
|-------------------|-------|------|
| Write / DDL reaching the DB from the workflow | `validate_sql()` on every statement | P8-1 |
| Vendor note changing routing, queries or answer | injection wrap + scan + flag; rules override LLM | P4-3, P11-1 |
| Answer with an unresolved `[n]` | `verify_citations` node | P11-5 |
| Viewer starting research, uploading, running Cypher | `require_role` | P3-1 |
| Document deleted without admin approval | approval service | P9-5 |
| Unbounded agent loop | `MAX_CORRECTIVE_ROUNDS` | P11-4 |
| Chain-of-thought or secrets in events, logs, responses | output scrub | P4-4 |

## 6. Evaluation (fails the build)

| Metric | CI threshold | Observed offline |
|--------|--------------|------------------|
| retrieval relevance | ≥ 0.80 | 1.00 |
| SQL correctness | = 1.00 | 1.00 |
| graph correctness | = 1.00 | 1.00 |
| multi-hop coverage | ≥ 0.66 | 1.00 |
| citation support | = 1.00 | 1.00 |
| answer grounding | ≥ 0.50 | 1.00 |

Dataset `tests/evaluation/datasets/eval_cases.json`, runner `tests/evaluation/evaluate.py` — P15-1.

## 7. Non-goals (v1)

No writes to systems of record · no autonomous action · no fine-tuning · not a general BI tool.
