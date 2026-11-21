# Phase 1 — Infrastructure Design Evolution

> This document explains the infrastructure wiring, component routing, and networking used in Phase 1.
> No Docker or cloud services are needed in Phase 1 — the entire infrastructure runs as a single local process.

---

## Overview

Phase 1 is a **single-process setup**. Everything runs on one machine, one Python process, one port. There are no containers, no cloud services, no databases yet.

```mermaid
graph LR
    DEV[Developer\nlocalhost] -->|HTTP :8001| UVICORN[Uvicorn\nASGI server\nport 8001]
    UVICORN -->|ASGI protocol| FASTAPI[FastAPI application]
    FASTAPI -->|stdout| LOGS[JSON log stream]
```

This simplicity is intentional. The infrastructure will grow in later phases; starting minimal means less to debug.

---

## P1-1 — Python Process and Package Layout

The Python process is started by **uvicorn**, which is an ASGI (Asynchronous Server Gateway Interface) server. It loads the FastAPI app object from `backend/app/main.py`.

```mermaid
graph TD
    subgraph Host Machine
        SHELL[Shell / Terminal]
        subgraph Python Process
            UVICORN[Uvicorn ASGI server\nport 0.0.0.0:8001]
            FASTAPI[FastAPI app\nbackend/app/main.py]
            SETTINGS[get_settings\nlru_cache]
            ENV[.env file]
        end
        LOGS[stdout → terminal]
    end

    SHELL -->|uvicorn app.main:app\n--app-dir backend| UVICORN
    UVICORN -->|imports| FASTAPI
    FASTAPI -->|calls| SETTINGS
    ENV -->|reads| SETTINGS
    FASTAPI -->|emits| LOGS
```

**Package routing — why `PYTHONPATH=backend`:**

Python needs to know where to find the `app` package. By adding `backend` to `PYTHONPATH`, the import `from app.core.config import get_settings` resolves correctly regardless of the current working directory.

```
PYTHONPATH=backend uvicorn app.main:app
                             ↑
                    Python looks for `app` in `backend/`
                    finds `backend/app/main.py`  ✅
```

---

## P1-2 — Request Routing and Middleware Wiring

When a request arrives at port 8001, it passes through a **middleware stack** before reaching the route handler. Middleware runs in reverse declaration order (outermost wraps innermost).

```mermaid
sequenceDiagram
    participant C as Client
    participant CORS as CORS Middleware
    participant RCM as RequestContext\nMiddleware
    participant ROUTE as Route Handler\n(/health etc.)

    C->>CORS: HTTP Request
    CORS->>RCM: passes through (adds CORS headers on response)
    RCM->>RCM: read X-Request-ID header\nor generate UUID
    RCM->>RCM: set request_id_var ContextVar
    RCM->>ROUTE: forward request
    ROUTE->>ROUTE: runs check registry\nbuilds response body
    ROUTE-->>RCM: response
    RCM->>RCM: add X-Request-ID to response headers
    RCM->>RCM: reset ContextVar
    RCM-->>CORS: response with X-Request-ID
    CORS-->>C: response with CORS + X-Request-ID headers
```

**Declaration order in `main.py` → execution order:**

```python
app.add_middleware(CORSMiddleware)       # added first → executes last (outermost)
app.add_middleware(RequestContextMiddleware)  # added second → executes first (innermost)
```

Starlette (FastAPI's underlying framework) reverses the declaration order. The middleware added last is the outermost wrapper.

---

## P1-3 — Test Infrastructure Routing

The test suite uses `starlette.testclient.TestClient`, which speaks directly to the ASGI app object without opening a real TCP socket. This means no port conflict and no network overhead.

```mermaid
graph TD
    subgraph Test Process
        PT[pytest runner]
        CF[conftest.py\noffline env vars]
        TC[TestClient\nASGI transport]
        FASTAPI[FastAPI app\nin-memory]
    end

    PT -->|imports conftest| CF
    CF -->|sets env vars\nbefore import| FASTAPI
    CF -->|creates| TC
    TC -->|ASGI call\nno TCP socket| FASTAPI
    FASTAPI -->|response object| TC
    TC -->|httpx Response| PT
```

**Why no real socket:**
- `TestClient` wraps the app in an in-process transport layer
- Tests run at ~300 tests/second instead of network-limited ~50/second
- No port conflicts when running tests in parallel

---

## P1-4 — Developer Workflow Infrastructure

```mermaid
graph LR
    subgraph Developer Machine
        MAKE[make command]
        UV[uv tool]
        VENV[.venv\nPython 3.12]
        RUFF[ruff\nin .venv]
        PYTEST[pytest\nin .venv]
        UVICORN_BIN[uvicorn\nin .venv]
    end

    MAKE -->|make setup| UV
    UV -->|uv sync| VENV
    MAKE -->|make lint| RUFF
    MAKE -->|make test| PYTEST
    MAKE -->|make backend| UVICORN_BIN
    VENV -->|provides| RUFF
    VENV -->|provides| PYTEST
    VENV -->|provides| UVICORN_BIN
```

**`uv` replaces pip + virtualenv:**
- `uv sync` reads `pyproject.toml` and installs exact versions from `uv.lock`
- Reproducible: every developer and every CI run installs exactly the same versions
- Fast: `uv` is 10–100× faster than pip for large dependency trees

---

## P1-5 — CI/CD Pipeline Infrastructure

```mermaid
graph TD
    DEV[Developer pushes to GitHub] -->|triggers| GHA[GitHub Actions runner\nubuntu-latest]

    subgraph GitHub Actions runner
        CHECKOUT[actions/checkout@v4\nclone repo]
        PY[actions/setup-python@v5\nPython 3.12]
        UV_SETUP[astral-sh/setup-uv@v4\ninstall uv]
        SYNC[uv sync --all-groups\ninstall deps]
        RUFF_CHECK[ruff check .\nlint]
        RUFF_FMT[ruff format --check .\nformat]
        PYTEST_RUN[pytest tests/ -v\noffline env vars]
    end

    CHECKOUT --> PY --> UV_SETUP --> SYNC
    SYNC --> RUFF_CHECK --> RUFF_FMT --> PYTEST_RUN

    PYTEST_RUN -->|all pass| GREEN[✅ PR mergeable]
    PYTEST_RUN -->|any fail| RED[❌ PR blocked]
    RUFF_CHECK -->|fail| RED
    RUFF_FMT -->|fail| RED
```

---

## Complete Phase 1 Infrastructure Picture

```mermaid
graph TD
    subgraph Cloud / GitHub
        REPO[GitHub Repository]
        GHA_RUNNER[GitHub Actions runner]
        GHA_RUNNER -->|on PR to development| LINTTEST[ruff + pytest\nCI checks]
    end

    subgraph Developer Machine
        subgraph Terminal
            MAKE_CMD[make commands]
        end

        subgraph Python .venv
            UV_BIN[uv]
            UVICORN_SRV[uvicorn :8001]
            RUFF_BIN[ruff linter]
            PYTEST_BIN[pytest runner]
        end

        subgraph FastAPI Application Process
            MW_CORS[CORS Middleware]
            MW_RID[X-Request-ID Middleware\nContextVar]
            ROUTER[Health Router]
            HEALTH_REG[Check Registry]
            CFG_OBJ[Settings object\nlru_cache]
            LOG_FMT[JSON Formatter]
        end

        subgraph File System
            DOTENV[.env]
            DOTENV_EX[.env.example]
            PY_PROJ[pyproject.toml]
            ULOCK[uv.lock]
        end
    end

    MAKE_CMD -->|make setup| UV_BIN
    MAKE_CMD -->|make backend| UVICORN_SRV
    MAKE_CMD -->|make lint| RUFF_BIN
    MAKE_CMD -->|make test| PYTEST_BIN

    UVICORN_SRV -->|loads| MW_CORS
    MW_CORS --> MW_RID
    MW_RID --> ROUTER
    ROUTER --> HEALTH_REG
    DOTENV -->|read by| CFG_OBJ
    MW_RID -->|writes to| LOG_FMT

    REPO -->|on push| GHA_RUNNER
    PY_PROJ -->|dependency spec| UV_BIN
    ULOCK -->|pinned versions| UV_BIN
```

---

## Ports and addresses

| Component | Host | Port | Protocol |
|-----------|------|------|----------|
| FastAPI / uvicorn | 0.0.0.0 | 8001 | HTTP |
| Test client | in-process | — | ASGI (no socket) |
| CI runner | GitHub cloud | — | HTTPS to GitHub API |

No other ports, services, or containers are used in Phase 1.

---

## What infrastructure is NOT here yet

| Component | Added in phase |
|-----------|---------------|
| PostgreSQL / SQLite (data) | Phase 2 |
| Redis / fakeredis | Phase 3 |
| Qdrant (vector store) | Phase 6 |
| Neo4j (graph store) | Phase 7 |
| Docker Compose stack | Phase 15 |
| Frontend Next.js :3001 | Phase 13 |

---

## Summary

Phase 1 infrastructure is intentionally minimal:

- **One process** (uvicorn + FastAPI)
- **One port** (8001)
- **No external services** (fake everything for tests)
- **One CI pipeline** (GitHub Actions, runs on every PR)

The middleware stack is wired in a specific order that all future middleware must respect:
`CORS → RequestContext → (rate-limit P3) → (audit P3) → route handler`

The check registry is global and extensible — later phases register their own readiness checks without touching the health router.
