# NovaEnterprise — Enterprise Knowledge & Decision Intelligence Platform

A research platform for a fictional technology company, **NovaEnterprise**. An analyst asks one enterprise
question in plain English and gets back a **cited, verified answer** built from documents, database records
and a knowledge graph. Every step of the retrieval process is open to inspection.

```text
Vector RAG  +  Graph RAG  +  SQL  +  Agents  +  Memory
```

> **Status: planning and project setup.** The specification, development plan and repository scaffolding
> are in place. Application code starts with Phase 1 in [TASKS.md](TASKS.md).

---

## The question this project is built around

> Which customers were impacted by the Payments API last quarter, what incidents occurred,
> which teams own those services, and what decisions were taken to prevent recurrence?

No single search can answer it. It needs four lookups in three different stores, merged into one cited answer:

| Part of the question | Answered from |
|---|---|
| Which customers were impacted | Knowledge graph (incident → impacted customer) |
| What incidents occurred | SQL (incidents in a date range) |
| Which teams own those services | Knowledge graph (service → owning team) |
| What decisions prevent recurrence | Hybrid document search over postmortems and ADRs |

The core idea is that **the retrieval strategy is decided at run time by a router**, not hard-coded.

---

## Planned architecture

```text
Browser (:3001) ─JWT─▶ Next.js 15 ─REST /api/v1─▶ FastAPI (:8001)
                                                    │  middleware: request id, rate limit, audit
                                                    ▼
                                     LangGraph research workflow (13 nodes)
                                                    │
     ┌──────────────────┬───────────────────┬───────┴──────────┬───────────────────┐
     ▼                  ▼                   ▼                  ▼                   ▼
PostgreSQL / SQLite  Qdrant / in-memory  Neo4j / in-memory  Redis / fakeredis  LLM provider (fake by default)
```

- **Offline first:** the full test suite and demo run with no API key and no external services
  (fake LLM, in-memory vector and graph stores, SQLite, fakeredis).
- **Read-only retrieval:** every SQL statement is validated, and every graph query is a typed traversal.
- **Safe by default:** document text is treated as data, never as instructions. A deliberately hostile
  document in the sample data checks this.
- **Verified answers:** each claim is checked against evidence, and every `[n]` citation must resolve.

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, LangChain / LangGraph |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind |
| Data stores | PostgreSQL / SQLite, Qdrant, Neo4j, Redis |
| Tooling | uv, ruff, pytest, GitHub Actions, Docker Compose |

The full specification is in [CLAUDE.md](CLAUDE.md).

---

## Progress so far

| # | Step | Result |
|---|------|--------|
| 1 | Wrote the problem statement, PRD and high-level design | [Docs/00-problem.md](Docs/00-problem.md), [Docs/01-prd.md](Docs/01-prd.md), [Docs/02-hld.md](Docs/02-hld.md) |
| 2 | Wrote the project specification (the single source of truth for building the platform) | [CLAUDE.md](CLAUDE.md): requirements F1–F17 and N1–N9, architecture, layering rules, guardrails, testing thresholds |
| 3 | Created the phased development plan | [TASKS.md](TASKS.md): 15 phases, 67 sub-tasks, one `feature/<name>` branch each, ordered to reduce dependencies between phases |
| 4 | Added the Git and GitHub workflow guide | [Git_GitHub_Workflow_Guide.md](Git_GitHub_Workflow_Guide.md): `feature/*` → `development` → `testing` → `main` |
| 5 | Initialised the Python project with uv | [pyproject.toml](pyproject.toml), [uv.lock](uv.lock), [.python-version](.python-version) (3.12), [src/novaenterprise/](src/novaenterprise/) package stub |
| 6 | Wrote `.gitignore` | [.gitignore](.gitignore): secrets, `data/` and `*.db`, Python and Node caches, store volumes, Terraform state; `.env.example` and `uv.lock` stay tracked |
| 7 | Created the GitHub repository and pushed the first commit to `main` | Remote `origin` → `github.com/sarat-coder/NovaEnterprise` |

### Up next

- [ ] Commit the specification and setup files to `main`
- [ ] Create the long-lived `development` and `testing` branches (see the workflow guide)
- [ ] Start Phase 1: **P1-1 · Settings and JSON logging** on `feature/backend-config-logging`

---

## Repository layout (current)

```text
NovaEnterprise/
├── CLAUDE.md                     # project specification (source of truth)
├── TASKS.md                      # phased task tracker
├── Git_GitHub_Workflow_Guide.md  # branching and PR workflow
├── Docs/
│   ├── 00-problem.md             # problem statement
│   ├── 01-prd.md                 # product requirements
│   └── 02-hld.md                 # high-level design
├── src/novaenterprise/           # Python package (uv scaffold)
├── pyproject.toml · uv.lock · .python-version
├── requirements.txt              # placeholder, empty for now
└── .gitignore
```

The planned application layout (`backend/`, `agents/`, `rag/`, `memory/`, `frontend/`, `database/`,
`sample_data/`, `tests/`) is described in [CLAUDE.md §4.3](CLAUDE.md). Each folder is created by the
task that needs it.

---

## Getting started

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sarat-coder/NovaEnterprise.git
cd NovaEnterprise
uv sync                  # creates .venv and installs dependencies
uv run novaenterprise    # runs the package stub
```

`make setup`, `make backend`, `make test`, `make demo` and the other commands listed in
[CLAUDE.md §13](CLAUDE.md) are added by the tasks that implement them, starting with P1-4.

---

## Development workflow

1. Pick the next `Pending ❌` sub-task in [TASKS.md](TASKS.md) whose predecessors have merged.
2. Branch from `development` using the exact branch name in the task row.
3. Build the change with a test. It must pass offline, and `ruff check` and `ruff format --check` must be clean.
4. Update `.gitignore` if the task adds new generated files.
5. Open a PR into `development`. After it merges, set the task to `Completed ✅`.
6. At the end of each phase, write the phase notes under `internal/` (plain-language explanation,
   system design evolution, infrastructure evolution, interview Q&A).

---

## Roadmap

| Phase | Name | Tasks | Status |
|-------|------|-------|--------|
| 1 | Runtime skeleton | 5 | Pending ❌ |
| 2 | Persistence and sample data | 5 | Pending ❌ |
| 3 | Identity and request guards | 4 | Pending ❌ |
| 4 | AI providers and guardrails | 4 | Pending ❌ |
| 5 | API contract and browse API | 3 | Pending ❌ |
| 6 | Vector RAG | 4 | Pending ❌ |
| 7 | Graph RAG | 4 | Pending ❌ |
| 8 | SQL retrieval | 3 | Pending ❌ |
| 9 | Ingestion and document management | 6 | Pending ❌ |
| 10 | Memory | 4 | Pending ❌ |
| 11 | Research agents | 5 | Pending ❌ |
| 12 | Workflow graph and research API | 5 | Pending ❌ |
| 13 | Console shell | 4 | Pending ❌ |
| 14 | Research and knowledge screens | 5 | Pending ❌ |
| 15 | Evaluation and delivery | 6 | Pending ❌ |

Task-level detail and merge order are in [TASKS.md](TASKS.md).
