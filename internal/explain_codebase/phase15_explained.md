# Phase 15 — Evaluation and Delivery: Plain-Language Explanation

## What problem are we solving?

By Phase 14 we had a fully working platform: analysts could ask questions, watch the AI think step by step, explore the knowledge graph, and manage documents — all in the browser. But there was one final problem: **how do we know the AI is actually giving good answers?** And **how would someone deploy this to a real company's server?**

Phase 15 answers both questions. It is the platform's "graduation" phase — turning a working prototype into something you could actually hand to a company and say "this is production-ready."

---

## Analogy: passing a vehicle's roadworthiness test

Phases 1–14 built the car. Phase 15 is the **final inspection and delivery package**:

- **Evaluation suite** (the MOT test) — automated checks that the AI's answers actually contain the right information and cite their sources correctly. If anything regresses, the build fails automatically.
- **Dockerfiles** (the owner's manual) — instructions for packaging the backend and frontend into self-contained boxes that anyone can run on any server.
- **Docker Compose** (the fleet deployment guide) — a single file that starts the whole stack: database, vector store, graph database, cache, backend API, and frontend — with one command.
- **CI pipeline** (the safety certificate) — automated checks that run on every code change, covering code style, all tests, the evaluation gate, and the frontend.
- **MCP server** (the external API port) — a standard plug that lets other AI tools connect to and query this platform without going through the web browser.
- **Hygiene tests** (the security audit) — automated checks that no passwords, API keys, or sensitive data could accidentally end up in the Docker images or the git repository.

---

## The six deliverables in detail

### 1. Evaluation dataset and scoring (`datasets/eval_cases.json`, `tests/evaluation/evaluate.py`)

The platform is only as good as the answers it gives. We need an objective way to measure quality.

**What we built**: a dataset of five carefully chosen questions, each with known correct answers that we can check automatically. For each question, we know:
- Which documents should appear in the evidence
- Whether SQL or graph queries are needed
- Whether the final answer should cite its sources

The evaluation script runs all five questions through the AI, then scores the results on six metrics:

| Metric | What it measures | Minimum score |
|--------|-----------------|---------------|
| Retrieval relevance | Did we find the right documents? | 80% |
| SQL correctness | Did the SQL query hit the right tables? | 100% |
| Graph correctness | Did the graph traversal follow the right relationships? | 100% |
| Multi-hop coverage | Did we use the right combination of search strategies? | 66% |
| Citation support | Did the answer include numbered `[1]`, `[2]` markers? | 100% |
| Answer grounding | Does the answer mention the expected topics? | 50% |

If any score falls below its threshold, the CI build **automatically fails** — just like a car failing its MOT test for a bald tyre.

```
Analyst question → AI workflow runs → Answer produced
                                      ↓
                      Score six metrics → Compare to thresholds
                                          → PASS or FAIL build
```

### 2. Backend and frontend Dockerfiles (`backend/Dockerfile`, `frontend/Dockerfile`)

A Dockerfile is a recipe for packaging an application so it can run on any computer with Docker installed — a laptop, a cloud server, a university computer — without worrying about which Python version or Node.js version is installed.

**Backend Dockerfile**: three stages
1. *Builder* — installs all Python dependencies in an isolated environment
2. *Runner* — takes only the runtime files (not the build tools), creates a non-root user for security, and starts the FastAPI server

**Frontend Dockerfile**: also three stages
1. *Deps* — installs Node.js packages
2. *Builder* — compiles the Next.js application into optimised files
3. *Runner* — takes only the compiled output and starts the web server

**Security principle**: neither Dockerfile bakes in any secret or `.env` file. All configuration is injected as environment variables when the container starts.

### 3. Docker Compose stack (`docker-compose.yml`)

Docker Compose is like an orchestra conductor — it tells every instrument (service) when to start and how to connect to the others.

**What starts when you run `docker compose up`:**

```
PostgreSQL   ← the main database (customers, incidents, decisions, sessions)
Redis        ← the cache and rate limiter
Qdrant       ← the vector store (semantic search)
Neo4j        ← the graph database (relationships)
Backend API  ← FastAPI, starts AFTER all four stores are healthy
Frontend     ← Next.js, starts AFTER the backend is healthy
```

Each service declares a **health check** — a small test that tells Compose whether the service is actually ready. The backend only starts after Postgres confirms it can accept queries. The frontend only starts after the backend confirms it is accepting requests.

**Result**: running one command starts a complete, production-like stack with all the right databases wired together.

### 4. CI pipeline update (`.github/workflows/ci.yml`)

Every time a developer pushes code to the repository, four automated jobs now run in parallel:

| Job | What it checks |
|-----|---------------|
| `lint-and-test` | Python code style + all 293 offline tests |
| `eval-gate` | All six evaluation metrics meet their thresholds |
| `deployment-hygiene` | No secrets in Dockerfiles; Compose file is well-formed |
| `frontend-lint-test` | Frontend code style + Jest unit tests |

If any job fails, the pull request is blocked until it is fixed. This means no regression can reach the main branch undetected.

### 5. MCP server (`integrations/mcp_server.py`)

MCP stands for **Model Context Protocol** — a standard way for AI tools to talk to each other. Think of it as a universal plug socket: any AI assistant that speaks MCP can plug in and query the NovaEnterprise knowledge base, just as it would query a web search or a calculator.

**What tools are exposed:**
- `search_knowledge` — find relevant document chunks by natural language
- `query_graph` — traverse the knowledge graph (impacted customers, owning teams, etc.)
- `run_sql_query` — run a read-only SQL query against the database
- `list_incidents` — browse incidents with optional filters
- `list_customers` — browse customers with optional filters
- `get_research_session` — retrieve the result of a previous research session

**Safety**: only read-only operations are exposed. The MCP server cannot upload documents, delete anything, or trigger research sessions. It is strictly a query interface.

### 6. Deployment hygiene tests (`tests/deployment/test_deployment.py`)

These 16 automated tests check that the platform is **safe to ship**. They do not start any application — they simply inspect the repository's files:

- Is `.env` in `.gitignore`? (If not, a developer could accidentally commit their API keys)
- Is `data/` in `.gitignore`? (If not, the SQLite database could be committed)
- Does `.env.example` list every variable? (So new team members know what to set)
- Does the backend Dockerfile avoid copying `.env`? (Secrets must not be baked into images)
- Does the frontend Dockerfile avoid the Supabase service-role key?
- Does the Compose file have health checks for all four stores?
- Does the MCP server only expose read-only tools?

---

## What "one command to run everything" means

Before Phase 15, running NovaEnterprise locally meant:
1. Set up Python
2. Install dependencies with `uv`
3. Configure `.env`
4. Start the backend
5. Set up Node.js
6. Start the frontend

After Phase 15, with Docker:
```
docker compose up
```
Everything — Postgres, Redis, Qdrant, Neo4j, Backend, Frontend — starts in the right order. The browser is ready at `http://localhost:3001`.

---

## Summary

Phase 15 is the final phase for a reason: it validates everything that came before it. The evaluation suite proves the AI gives good answers. The Docker stack proves the platform can run on any server. The hygiene tests prove no sensitive data can leak. The CI pipeline ties it all together — every code change must pass all four gates before it can reach production.

**Engineering principles demonstrated:**
- **Measure quality, don't assume it** — evaluation metrics with hard thresholds
- **Package once, run anywhere** — multi-stage Dockerfiles with no baked-in secrets
- **Health over hope** — every service declares a health check
- **Defense in depth** — secrets are excluded at the gitignore level, the Dockerfile level, and by automated tests
- **Open standards** — MCP lets any AI tool query the platform without a custom integration
