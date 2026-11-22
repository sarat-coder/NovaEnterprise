# MEMORY.md — NovaEnterprise locked decisions and honest status

> The project's long-term memory. Read it at the start of every task; update it when a decision is locked,
> a status changes, or an open question is answered.
> Spec: `CLAUDE.md` · Requirements: `PLAN.md` · Exit criteria: `PLAN_PHASE.md` · Tasks: `TASKS.md`

**Rules for this file**
- Status columns are separate on purpose: **implemented ≠ validated locally ≠ needs credentials ≠ deployed**
  (CLAUDE.md §14 "Honest status rule"). Never mark a column ✅ until it is true.
- A decision enters "Locked decisions" only when it is agreed. Reversing one needs an ADR in `docs/adr/` and a
  CLAUDE.md update first.
- Append to the change log; do not rewrite history.

---

## 1. Honest status

Legend: ✅ done · ❌ not done · ➖ not applicable

| Phase | Name | Implemented | Validated locally | Needs credentials | Deployed |
|-------|------|-------------|-------------------|-------------------|----------|
| 0 | Specification and repo setup | ✅ | ➖ | ➖ | ➖ |
| 1 | Runtime skeleton | ✅ | ✅ | ➖ | ❌ |
| 2 | Persistence and sample data | ❌ | ❌ | Postgres / Supabase for RLS | ❌ |
| 3 | Identity and request guards | ❌ | ❌ | Supabase Auth (optional), real Redis | ❌ |
| 4 | AI providers and guardrails | ❌ | ❌ | LLM API key for non-fake providers | ❌ |
| 5 | API contract and browse API | ❌ | ❌ | ➖ | ❌ |
| 6 | Vector RAG | ✅ | ✅ | Qdrant (Docker or Cloud) | ❌ |
| 7 | Graph RAG | ❌ | ❌ | Neo4j (Docker or Aura) | ❌ |
| 8 | SQL retrieval | ❌ | ❌ | ➖ | ❌ |
| 9 | Ingestion and document management | ❌ | ❌ | ➖ | ❌ |
| 10 | Memory | ❌ | ❌ | real Redis (optional) | ❌ |
| 11 | Research agents | ❌ | ❌ | ➖ | ❌ |
| 12 | Workflow graph and research API | ❌ | ❌ | ➖ | ❌ |
| 13 | Console shell | ❌ | ❌ | ➖ | ❌ |
| 14 | Research and knowledge screens | ❌ | ❌ | ➖ | ❌ |
| 15 | Evaluation and delivery | ❌ | ❌ | container registry / cloud account | ❌ |

**Repository state**
- GitHub remote: `origin` → `github.com/sarat-coder/NovaEnterprise`. `main` has one commit (empty README).
- Specification and setup files are staged on `main`, not yet committed.
- Long-lived branches `development` and `testing` do **not** exist yet.
- Phase 1 complete: `backend/app/` skeleton, health routes, X-Request-ID middleware, pytest harness, Makefile, ruff config, `.env.example`, CI workflow. 8/8 tests pass offline.

---

## 2. Locked decisions

### 2.1 Architecture (from CLAUDE.md §4.4 — do not reverse without an ADR)

| # | Decision | Instead of |
|---|----------|------------|
| D1 | Retrieval strategy chosen at run time by a router node | one fixed retriever |
| D2 | Deterministic `agents/rules.py` corrects LLM output | trusting the model |
| D3 | In-memory vector and graph stores for tests and demo | requiring Docker |
| D4 | Typed graph traversals that also return their Cypher | free-form generated Cypher |
| D5 | SQL templates + `validate_sql()`; LLM generation only as an addition | free-form generated SQL |
| D6 | Bounded corrective loop (`MAX_CORRECTIVE_ROUNDS=1`) | retry until satisfied |
| D7 | Evidence verification and citation verification as separate nodes | one "check the answer" step |
| D8 | 202 + background task + polling | long blocking request |
| D9 | One `Evidence` shape for document, SQL and graph results | store-specific evidence |
| D10 | Graph runs in-process for v1 | worker + Postgres checkpointer (production extension) |

### 2.2 Project and tooling

| # | Decision | Date |
|---|----------|------|
| T1 | Python 3.12, package manager **uv** (`pyproject.toml` + `uv.lock` committed) | 2026-11-21 |
| T2 | Lint with ruff (`ruff check` + `ruff format --check`) before every PR; CI runs it from P1-5 | 2026-11-21 |
| T3 | Git flow `feature/<name>` → `development` → `testing` → `main`; one TASKS.md sub-task = one branch = one PR | 2026-11-21 |
| T4 | Execution order is TASKS.md (15 phases, 67 sub-tasks), arranged to minimise cross-phase waits | 2026-11-21 |
| T5 | Claude Code config in `.claude/`: 8 agents, project skills, path-scoped rules, 1 h prompt cache, `agent_guard.py` hook | 2026-11-21 |
| T6 | Haiku model pin left out of `.claude/settings.json`: `claude-haiku-4-5@20251001` is not available on this account | 2026-11-21 |
| T7 | After each phase, four docs under `internal/` (explained, system design evolution, infra evolution, interview Q&A) | 2026-11-21 |

---

## 3. Open questions

| # | Question | Blocks | Owner / next step |
|---|----------|--------|-------------------|
| Q1 | ~~Package layout resolved~~: `src/novaenterprise/` retained as stub; real app lives in `backend/app/` with `PYTHONPATH=backend`. pytest config sets `pythonpath = ["backend"]`. | ~~P1-1~~ | Resolved in Phase 1 |
| Q2 | Names of the 4 memory scopes (CLAUDE.md §16) | P10-3 | Confirm before Phase 10 |
| Q3 | Exact names of the per-strategy retrieval nodes that make up the 13 | P11-3, P12-2 | Confirm before P11-3 |
| Q4 | Upload extension allowlist (md, txt, pdf?) | P9-4 | Fix in code and record here |
| Q5 | SQL allowlist (tables / columns) | P8-1 | Fix in code and record here |
| Q6 | `requirements.txt` is empty; uv uses `pyproject.toml`. Delete, or generate with `uv export`? | none | Decide at P1-4 |
| Q7 | Course docs `05-rag.md`, `06-tools.md`, `16-observability.md` are not in the repo; sections derived from them are inferred | Phases 6–12 | Add them or confirm the inferred sections |
| Q8 | `Git_GitHub_Workflow_Guide.md` still uses CloudDesk examples | none | Update to NovaEnterprise branch names |

---

## 4. Known gotchas

- `get_settings()` is `lru_cache`d — restart the backend after editing `.env`; clear the cache in tests that change env vars.
- Windows: use `.venv/Scripts/python.exe`; `PYTHONPATH` uses `;`; set `PYTHONIOENCODING=utf-8` for box-drawing output.
- Core must never import from `agents/` (circular import).
- Never call the graph from a router directly; schedule a background task.
- Two servers on :8001 (container + local uvicorn) give different answers — check `docker ps`.
- `MAX_SUBQUESTIONS=1` under-answers the canonical question; the corrective loop cannot fix it.
- Claude Code settings apply only in a new session.

---

## 5. Change log

| Date | Change |
|------|--------|
| 2026-11-21 | Spec files written (`Docs/`, `CLAUDE.md`), `TASKS.md` created, uv project initialised, `.gitignore`, README, GitHub remote, `.claude/` setup, `PLAN.md`, `PLAN_PHASE.md`, this file |
| 2026-11-21 | Phase 1 complete — `backend/app/` skeleton, `core/config.py`, `core/logging.py`, `core/health.py`, `middleware/request_context.py`, `api/health.py`, `app/main.py`, `tests/conftest.py`, 8 tests, Makefile, ruff config, `.env.example`, CI workflow. 8/8 pass. Phase docs written. |
| 2026-11-22 | Phase 6 complete — `rag/chunking.py` (parse + chunk md/txt/pdf), `rag/vector_store.py` (VectorStoreService protocol + MemoryVectorStore + BM25), `rag/qdrant_adapter.py`, `rag/retriever.py` (semantic + BM25 + RRF + rerank → Evidence). `pypdf` added to deps. Health check: `vector_store: ok (memory)`. 162/162 pass offline. Phase docs written. |
