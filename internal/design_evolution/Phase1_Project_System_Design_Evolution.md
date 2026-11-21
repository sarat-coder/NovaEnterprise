# Phase 1 — System Design Evolution

> This document tracks how the system design grew during Phase 1 — from a single file to a layered FastAPI skeleton.
> Each section shows the state at the end of the named sub-task.

---

## Starting point (before Phase 1)

The repository contained only specification and configuration files: `CLAUDE.md`, `TASKS.md`, `PLAN.md`, and a `pyproject.toml` from `uv init`. No application code existed.

```mermaid
graph TD
    A[Empty repo] --> B[CLAUDE.md spec]
    A --> C[TASKS.md task list]
    A --> D[pyproject.toml]
```

---

## After P1-1 — Settings and JSON Logging

The first task introduced the concept of **application configuration as a typed object**. The key design decision: settings are read once at startup via `get_settings()`, which is `lru_cache`d. Tests can reset the cache to test different configurations.

```mermaid
graph TD
    subgraph backend/app/core
        C[config.py\nSettings class\nget_settings lru_cache]
        L[logging.py\nJSONFormatter\nrequest_id_var ContextVar]
    end

    E[.env file] -->|read once| C
    C -->|provides settings| APP[Application]
    L -->|structured JSON logs| STDOUT[stdout / log aggregator]
```

**Key design choices made here:**
- `pydantic-settings` validates every env var at startup; a missing required value fails fast with a clear message
- `request_id_var` is a `ContextVar` — it is local to each async request handler automatically, with no threading bugs
- `configure_logging()` replaces all root handlers so third-party libraries also emit JSON

---

## After P1-2 — Health Routes and X-Request-ID Middleware

The second task introduced **middleware** (code that wraps every request) and the **check registry** pattern (a global dict that any later component can register a readiness check into).

```mermaid
graph LR
    CLIENT[Client Browser / curl] -->|HTTP request| MW[RequestContextMiddleware\nX-Request-ID]
    MW --> FASTAPI[FastAPI app]
    FASTAPI --> HR[/health router]
    HR --> HC[health_check_registry\nrun_all_checks]
    HC -->|app check| OK[status: ok]
    FASTAPI -->|every response| MW
    MW -->|adds X-Request-ID header| CLIENT
```

**Middleware order established here** (enforced by CLAUDE.md §4):
```
Request enters:   CORS → RequestContext → (rate-limit P3) → (audit P3) → route handler
Response leaves:  route handler → (audit P3) → (rate-limit P3) → RequestContext → CORS → Client
```

The `register_check()` / `run_all_checks()` pattern was chosen because later phases (database, Redis, vector store, graph store, LLM) each own their own check. Each phase calls `register_check("database", ...)` during lifespan, and `/health/ready` aggregates them all automatically.

---

## After P1-3 — Offline Test Harness

Adding tests did not change the application design, but it locked in the **test isolation strategy**:

```mermaid
graph TD
    subgraph tests/
        CF[conftest.py\noffline env vars\nTestClient fixture]
        TH[test_health.py\n4 tests]
        TR[test_request_id.py\n4 tests]
    end

    CF -->|injects fake settings| TH
    CF -->|injects fake settings| TR
    CF -.->|lru_cache reset\nbefore+after each test| SETTINGS[get_settings]
```

**Isolation contract:** `conftest.py` forces all offline values before any application module is imported. The `_reset_settings` autouse fixture clears the cache before and after every single test, so no test can pollute the next one's settings.

---

## After P1-4 — Makefile, Ruff, .env.example

No new code was introduced; this task established **developer workflow conventions**:

```mermaid
graph LR
    DEV[Developer] -->|make setup| UV[uv sync\ninstalls deps]
    DEV -->|make backend| UVICORN[uvicorn app.main:app\nPYTHONPATH=backend\nport 8001]
    DEV -->|make test| PYTEST[pytest tests/\noffline env]
    DEV -->|make lint| RUFF[ruff check .\nruff format --check .]
```

---

## After P1-5 — CI Pipeline (final Phase 1 design)

The CI pipeline runs the same commands as the developer, but on a clean Ubuntu server on every push or pull request to `development`.

```mermaid
graph TD
    PR[Developer opens PR to development] --> CI[GitHub Actions CI]

    subgraph CI Pipeline
        direction LR
        S1[Checkout code] --> S2[Python 3.12 + uv]
        S2 --> S3[uv sync --all-groups]
        S3 --> S4[ruff check .]
        S4 --> S5[ruff format --check .]
        S5 --> S6[pytest tests/\noffline env vars]
    end

    CI --> PASS{All pass?}
    PASS -->|✅ yes| MERGE[PR can merge]
    PASS -->|❌ no| BLOCK[PR blocked]
```

---

## Final Phase 1 Architecture — Complete Picture

```mermaid
graph TD
    subgraph External
        CLIENT[Browser / curl]
        GH[GitHub Actions CI]
    end

    subgraph Project Root
        ENV[.env / .env.example]
        MF[Makefile]
        PJ[pyproject.toml\nruff config\npytest config\ndependencies]
        GWCI[.github/workflows/ci.yml]
    end

    subgraph backend/app
        MAIN[main.py\nFastAPI app\nlifespan\nCORS middleware]

        subgraph core/
            CFG[config.py\nSettings, get_settings]
            LOG[logging.py\nJSONFormatter, request_id_var]
            HLT[health.py\nregister_check, run_all_checks]
        end

        subgraph middleware/
            RCM[request_context.py\nX-Request-ID]
        end

        subgraph api/
            HR[health.py\n/health /live /ready]
        end
    end

    subgraph tests/
        CONF[conftest.py\noffline fixtures]
        TH[test_health.py]
        TR[test_request_id.py]
    end

    CLIENT -->|HTTP| MAIN
    MAIN -->|reads once| CFG
    MAIN -->|wraps every req| RCM
    MAIN -->|routes| HR
    HR -->|runs checks| HLT
    LOG -->|ContextVar| RCM
    ENV -->|loaded by| CFG
    MF -->|runs| MAIN
    MF -->|runs| CONF
    GH -->|runs| PJ
    CONF -->|TestClient| MAIN
    TH -->|uses| CONF
    TR -->|uses| CONF
```

---

## Design decisions locked in Phase 1

| Decision | Chosen approach | Why |
|----------|----------------|-----|
| Configuration | `pydantic-settings` with `lru_cache` | Validates all vars at startup; cheap to read; testable |
| Logging | JSON to stdout | Works with any log aggregator; `request_id` ties requests to logs |
| Request tracing | `ContextVar` + header | Thread-safe; works with async; zero overhead |
| Health checks | Registry pattern | Decoupled: each subsystem registers its own check |
| Offline testing | Fake provider, memory stores, SQLite | Zero external dependencies; CI runs on any machine |
| Code style | `ruff` with strict rules | Fast; covers both linting and formatting in one tool |
| Dependency management | `uv` with `pyproject.toml` | Modern Python packaging; reproducible with `uv.lock` |
