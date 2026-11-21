# Phase 3 — Infrastructure Design Evolution: Identity and Request Guards

> **Purpose:** Explain how the infrastructure wiring changed in Phase 3 — new components, their connections, and how they are configured for local development vs. production.

---

## Infrastructure at the start of Phase 3

At the end of Phase 2, the running infrastructure looked like this:

```mermaid
graph LR
    Dev["Developer\nlaptop"]
    FastAPI["FastAPI process\n:8001\npython uvicorn"]
    SQLite["SQLite file\ndata/enterprise.db"]

    Dev -- "HTTP requests\ncurl / browser" --> FastAPI
    FastAPI -- "SQLAlchemy\nread/write" --> SQLite
```

One process, one file. No external services at all.

---

## New components added in Phase 3

Phase 3 adds two new infrastructure pieces:

| Component | Phase 3 version | Production version (Phase 15) |
|-----------|----------------|-------------------------------|
| **Redis** | `fakeredis` Python library (in-process, no server) | Redis container `:6379` |
| **JWT signing** | HS256 with `JWT_SECRET` from `.env` | Same algorithm; stronger secret |

---

## Component wiring: local development (offline mode)

In local development (and all tests), the full stack runs as a **single Python process**. There is no Docker, no network, no external servers.

```mermaid
graph TD
    subgraph "Single Python process (:8001)"
        FastAPI["FastAPI\nASGI app"]
        
        subgraph "Middleware stack"
            CORS["CORSMiddleware"]
            ReqCtx["RequestContextMiddleware"]
            RateLimit["RateLimitMiddleware"]
            Audit["AuditMiddleware"]
        end

        subgraph "Core modules"
            Security["core/security.py\nPyJWT HS256"]
            Redis_client["core/redis_client.py\nfakeredis (in-memory)"]
            Config["core/config.py\nget_settings()\nlru_cached"]
            DB["core/db.py\nSQLAlchemy\nSQLite"]
        end

        subgraph "Routers"
            Health["/health, /live, /ready"]
            Auth["/api/v1/auth/*"]
        end
    end

    subgraph "In-process data stores"
        FakeRedis["fakeredis\n(Python dict, same process)"]
        SQLiteFile["SQLite file\ndata/enterprise.db"]
    end

    CORS --> ReqCtx --> RateLimit --> Audit --> FastAPI
    FastAPI --> Health & Auth
    Auth --> Security
    RateLimit --> Redis_client
    Redis_client --> FakeRedis
    Health & Auth --> DB --> SQLiteFile
    Security --> Config
    Redis_client --> Config
    DB --> Config
```

**Key properties of the offline setup:**

- `fakeredis` is imported at runtime only when `REDIS_URL=""` (the default in `.env.example` and in tests)
- `fakeredis.FakeRedis()` stores all counters in a Python dict — zero latency, zero network, zero setup
- The JWT secret is `change-me-before-production` by default; tests override to `test-secret-do-not-use-in-prod-32ch`
- All of this runs with `make backend` or `uv run pytest tests/` — no Docker required

---

## Component wiring: production / Docker Compose (Phase 15 target)

When running against real services (Phase 15 Docker Compose), the topology changes:

```mermaid
graph TD
    subgraph "Docker network: nova_net"
        Browser["Browser\n:3001"]
        
        subgraph "backend container :8001"
            FastAPI["FastAPI\n(uvicorn)"]
            Security["JWT (HS256)"]
            RateLimitMW["RateLimitMiddleware"]
        end

        Redis["Redis container\nredis:7-alpine\n:6379"]
        Postgres["Postgres container\npostgres:16\n:5432"]
        Qdrant["Qdrant container\n:6333 (Phase 6+)"]
        Neo4j["Neo4j container\n:7687 (Phase 7+)"]
    end

    Browser --> FastAPI
    RateLimitMW --> Redis
    FastAPI --> Postgres
```

Env vars that switch from offline to production:

| Variable | Offline (default) | Production |
|----------|-------------------|------------|
| `REDIS_URL` | `""` → fakeredis | `redis://redis:6379/0` |
| `DATABASE_URL` | `sqlite:///data/enterprise.db` | `postgresql://user:pass@postgres:5432/nova` |
| `JWT_SECRET` | `change-me-before-production` | Strong random secret from secrets manager |

---

## Redis integration deep-dive

### How the client is obtained

```mermaid
flowchart TD
    Start["Application startup\nor first rate-limit request"]
    Check{REDIS_URL set?}
    Real["redis.Redis.from_url(REDIS_URL)\ndecode_responses=True\ndetail = 'real'"]
    Fake["fakeredis.FakeRedis()\ndecode_responses=True\ndetail = 'fakeredis'"]
    Cache["Stored in lru_cache\n_get_redis_and_detail()"]
    HealthCheck["Registered as:\nredis check → client.ping()"]

    Start --> Check
    Check -->|Yes| Real
    Check -->|No| Fake
    Real --> Cache
    Fake --> Cache
    Cache --> HealthCheck
```

### How the rate-limit counter works

```mermaid
sequenceDiagram
    participant MW as RateLimitMiddleware
    participant Redis

    Note over MW: Incoming request from IP=192.168.1.1\nMinute window = 1748

    MW->>Redis: INCR "rl:192.168.1.1:1748"
    Redis-->>MW: count = 5

    MW->>Redis: EXPIRE "rl:192.168.1.1:1748" 60
    Redis-->>MW: OK

    alt count (5) ≤ limit (120)
        MW->>MW: Allow request → call_next
    else count > limit
        MW-->>Client: 429 {"detail": "Rate limit exceeded..."}
    end
```

**Window key structure:** `rl:{client_ip}:{int(time.time() // 60)}`

- The window integer changes every 60 seconds, so old keys become unreachable and expire naturally.
- `EXPIRE 60` ensures Redis evicts the key within one minute of the last request, preventing memory accumulation.

### Test isolation

In tests, all requests share the same `fakeredis` instance (via `lru_cache`). The rate-limit test file flushes the instance before and after each test:

```python
get_redis_client().flushall()  # before: clear accumulated counts from prior tests
yield  # test runs
get_redis_client().flushall()  # after: clean up for the next test
```

---

## JWT flow across the middleware stack

The sequence below shows exactly when each middleware layer touches the request and response:

```mermaid
sequenceDiagram
    participant Client
    participant CORS as CORSMiddleware
    participant ReqCtx as RequestContextMiddleware
    participant RateLimit as RateLimitMiddleware
    participant Audit as AuditMiddleware
    participant Handler as Route Handler
    participant JWT as security.py

    Client->>CORS: POST /api/v1/auth/login\nOrigin: http://localhost:3001
    CORS->>ReqCtx: (adds CORS headers later on response)
    ReqCtx->>RateLimit: sets X-Request-ID in ContextVar + will add to response
    RateLimit->>Audit: checks Redis counter (5 < 120) ✅
    Audit->>Handler: call_next — no logic yet, waits for response
    Handler->>JWT: decode token from Authorization header
    JWT-->>Handler: UserContext(sub="analyst", role=2)
    Handler-->>Audit: Response(status=200, body={...})
    Audit->>Audit: log audit entry (POST, /login, 200, X-Request-ID from header)
    Audit-->>RateLimit: Response
    RateLimit-->>ReqCtx: Response
    ReqCtx->>ReqCtx: Response.headers["X-Request-ID"] = req_id
    ReqCtx-->>CORS: Response
    CORS-->>Client: Response + CORS headers + X-Request-ID
```

**Why AuditMiddleware reads X-Request-ID from the response header (not ContextVar):**

Starlette's `BaseHTTPMiddleware` calls `call_next` inside a new `anyio` task. ContextVars are not automatically inherited across task boundaries in Python. By the time Audit runs `call_next`, the ContextVar set by RequestContextMiddleware is no longer visible. However, the `X-Request-ID` response header is part of the HTTP response object — always visible regardless of async task boundaries.

---

## Readiness check expansion

After Phase 3, `GET /health/ready` reports three stores:

```mermaid
graph LR
    Ready["GET /health/ready"]
    App["app: ok (fastapi)"]
    DB["database: ok (sqlite|postgresql)"]
    Redis["redis: ok (fakeredis|real)"]

    Ready --> App
    Ready --> DB
    Ready --> Redis
```

Each check is registered at startup in `main.py`'s lifespan function. The check runs `client.ping()` for Redis and `SELECT 1` for the database.

---

## Environment variables for Phase 3

No new variables were added — all of these existed in `.env.example` from Phase 1:

| Variable | Phase 3 meaning |
|----------|----------------|
| `REDIS_URL` | Empty → fakeredis; set to `redis://...` for a real server |
| `RATE_LIMIT_PER_MINUTE` | Default 120; set low (e.g. 3) in rate-limit tests |
| `JWT_SECRET` | Signs all tokens; must be ≥32 bytes in production |
| `JWT_ALGORITHM` | `HS256` (default); can be changed to RS256 for public-key JWT |
| `JWT_EXPIRE_MINUTES` | Token lifetime in minutes (default 60) |

---

## Summary of infrastructure delta from Phase 2 to Phase 3

| Item | Phase 2 | Phase 3 |
|------|---------|---------|
| In-process Redis | No | Yes (fakeredis, lru_cached) |
| External Redis | No | Supported (switch via REDIS_URL) |
| Auth module | No | `core/security.py` (PyJWT HS256) |
| Middleware layers | 2 (CORS + RequestContext) | 4 (+ RateLimit + Audit) |
| Readiness checks | 2 (app + database) | 3 (+ redis) |
| New routes | 0 | 3 (login, /me, /analyst-only) |
| New packages | 0 | `pyjwt`, `redis`, `fakeredis` |
