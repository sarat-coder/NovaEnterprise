# Phase 3 — System Design Evolution: Identity and Request Guards

> This document traces how the system design grew during Phase 3 — from the unsealed skeleton at the start of the phase to the fully guarded API by the end.

---

## Where we started (end of Phase 2)

At the end of Phase 2 we had:

```mermaid
graph TD
    Browser["Browser / API Client"]
    FastAPI["FastAPI :8001"]
    Mw1["CORS Middleware"]
    Mw2["RequestContext Middleware\n(X-Request-ID)"]
    Health["GET /health, /live, /ready"]
    DB[(SQLite\nseeded with 6 teams,\n20 employees, 10 customers,\n12 incidents, 8 ADRs, 15 docs)]

    Browser --> Mw1 --> Mw2 --> FastAPI
    FastAPI --> Health
    FastAPI --> DB
```

**Problem:** Any caller could reach any route. There was no concept of who you are, what you are allowed to do, or how many requests you can fire per minute.

---

## P3-1 — Adding JWT + Role Checks

The first step was to define the identity and permission model.

### Role model

```mermaid
graph LR
    V["Viewer\nlevel = 1"]
    A["Analyst\nlevel = 2"]
    Ad["Admin\nlevel = 3"]

    V -->|inherits| A -->|inherits| Ad
```

Role enforcement uses a simple integer comparison: a route that requires `Analyst (2)` accepts any caller with `role ≥ 2`. This means Admin automatically passes Analyst checks.

### JWT flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant SecurityModule as security.py

    Client->>API: POST /api/v1/auth/login {username, password}
    API->>SecurityModule: create_access_token(sub, role)
    SecurityModule-->>API: JWT (signed with jwt_secret)
    API-->>Client: {access_token, token_type, role}

    Note over Client,API: Every subsequent request:
    Client->>API: GET /protected-route\nAuthorization: Bearer <JWT>
    API->>SecurityModule: get_current_user(token)
    SecurityModule-->>API: UserContext(sub, role)
    API->>SecurityModule: require_role(ANALYST)
    alt role < ANALYST
        SecurityModule-->>Client: 403 Forbidden
    else role ≥ ANALYST
        SecurityModule-->>API: UserContext (passed through)
        API-->>Client: 200 OK + response
    end
```

### Design after P3-1

```mermaid
graph TD
    Browser["Browser / API Client"]
    FastAPI["FastAPI :8001"]
    Mw1["CORS"]
    Mw2["RequestContext\n(X-Request-ID)"]
    Security["core/security.py\nJWT decode\nrequire_role()"]
    Routes["Protected Routes\n(require_role dependency)"]
    DB[(SQLite)]

    Browser --> Mw1 --> Mw2 --> FastAPI
    FastAPI --> Security
    Security --> Routes
    Routes --> DB
```

---

## P3-2 — Demo Login Routes

We added three demo user accounts and two convenience endpoints to the auth router:

```mermaid
graph LR
    Login["POST /api/v1/auth/login"]
    Me["GET /api/v1/auth/me\n(requires VIEWER)"]
    AnalystOnly["GET /api/v1/auth/analyst-only\n(requires ANALYST)"]
    DemoUsers["Demo users dict\nviewer / analyst / admin"]
    SecurityMod["security.py\ncreate_access_token()"]

    Login --> DemoUsers
    Login --> SecurityMod
    Me --> SecurityMod
    AnalystOnly --> SecurityMod
```

### Design after P3-2

The API now has an auth router alongside the health router:

```mermaid
graph TD
    Client["Client"]
    CORS["CORS Middleware"]
    ReqCtx["RequestContext\n(X-Request-ID)"]
    FastAPI["FastAPI :8001"]
    Health["Health Router\n/health  /live  /ready"]
    Auth["Auth Router\n/api/v1/auth/login\n/api/v1/auth/me\n/api/v1/auth/analyst-only"]
    Security["security.py\nJWT + require_role"]
    DB[(SQLite)]

    Client --> CORS --> ReqCtx --> FastAPI
    FastAPI --> Health
    FastAPI --> Auth --> Security
    Health --> DB
    Auth --> DB
```

---

## P3-3 — Redis Client + Rate Limiter

A new middleware layer and a Redis (or fakeredis) backing store were introduced.

### Token-bucket rate limit design

```mermaid
graph TD
    Req["Incoming Request"]
    Key["Key = rl:{client_ip}:{minute_window}"]
    Incr["INCR key\nEXPIRE key 60s"]
    Check{count > limit?}
    Pass["Allow request → next middleware"]
    Block["Return 429 Too Many Requests"]
    Redis[("Redis / fakeredis\nin-memory counter")]

    Req --> Key --> Incr --> Redis
    Redis --> Check
    Check -->|Yes| Block
    Check -->|No| Pass
```

### Redis client bootstrap

```mermaid
flowchart LR
    Env{REDIS_URL set?}
    Real["redis.Redis.from_url()\ndetail = 'real'"]
    Fake["fakeredis.FakeRedis()\ndetail = 'fakeredis'"]
    Health["/health/ready\nredis: ok (fakeredis|real)"]

    Env -->|Yes| Real
    Env -->|No| Fake
    Real --> Health
    Fake --> Health
```

### Design after P3-3

```mermaid
graph TD
    Client["Client"]
    CORS["CORS"]
    ReqCtx["RequestContext"]
    RateLimit["RateLimitMiddleware\ntoken-bucket per IP"]
    FastAPI["FastAPI :8001"]
    Redis[("Redis / fakeredis")]
    Health["Health Router"]
    Auth["Auth Router"]
    Security["security.py"]
    DB[(SQLite)]

    Client --> CORS --> ReqCtx --> RateLimit --> FastAPI
    RateLimit --> Redis
    FastAPI --> Health
    FastAPI --> Auth --> Security
    Health --> DB
```

---

## P3-4 — Audit Middleware and Final Middleware Order

The final piece was an audit middleware that logs every state-changing request.

### Audit middleware design

```mermaid
sequenceDiagram
    participant Client
    participant AuditMW as AuditMiddleware
    participant Handler as Route Handler

    Client->>AuditMW: POST /api/v1/auth/login
    AuditMW->>Handler: call_next(request)
    Handler-->>AuditMW: Response (status=200)
    AuditMW->>AuditMW: if method in {POST,PUT,PATCH,DELETE}:\n  logger.info("audit", method, path, status, request_id)
    AuditMW-->>Client: Response (unchanged)
```

**Key design note:** The audit middleware reads `X-Request-ID` from the **response header** (not from a ContextVar). This is because Starlette's `BaseHTTPMiddleware` runs `call_next` in a separate asyncio task, which breaks ContextVar propagation. The RequestContextMiddleware stamps the ID onto the response before it bubbles back up, so reading from the header is reliable.

### Final middleware stack (Phase 3 complete)

```mermaid
graph TD
    Client["HTTP Client"]

    subgraph "Middleware Stack (outermost → innermost)"
        CORS["1. CORSMiddleware\nOrigin check, CORS headers"]
        ReqCtx["2. RequestContextMiddleware\nAssign X-Request-ID"]
        RateLimit["3. RateLimitMiddleware\nToken-bucket per IP via Redis"]
        Audit["4. AuditMiddleware\nLog POST/PUT/PATCH/DELETE"]
    end

    FastAPI["FastAPI Route Handlers"]

    Client --> CORS --> ReqCtx --> RateLimit --> Audit --> FastAPI
    FastAPI -.->|response propagates back| Audit -.-> RateLimit -.-> ReqCtx -.-> CORS -.-> Client
```

> **Starlette note:** With `add_middleware(A)` then `add_middleware(B)`, Starlette inserts at list position 0 and reverses the list when building the stack. Result: **first added = outermost = executes first** on the incoming request path.

---

## Full system design at end of Phase 3

```mermaid
graph TD
    Browser["Browser / API client\n(Next.js :3001 — Phase 13)"]

    subgraph "FastAPI Backend :8001"
        CORS["CORS Middleware"]
        ReqCtx["RequestContext Middleware\nX-Request-ID assignment"]
        RateLimit["RateLimit Middleware\n429 after RATE_LIMIT_PER_MINUTE"]
        Audit["Audit Middleware\nStructured JSON log entry"]

        subgraph "Routers"
            HealthR["Health Router\n/health  /live  /ready"]
            AuthR["Auth Router\n/api/v1/auth/login\n/api/v1/auth/me\n/api/v1/auth/analyst-only"]
        end

        Security["core/security.py\nJWT encode/decode\nrequire_role(min_role)"]
    end

    subgraph "Data stores"
        SQLite[(SQLite\ndata/enterprise.db)]
        Redis[("Redis / fakeredis\nrate-limit counters")]
    end

    Browser --> CORS --> ReqCtx --> RateLimit --> Audit
    Audit --> HealthR
    Audit --> AuthR
    AuthR --> Security
    HealthR --> SQLite
    Security --> SQLite
    RateLimit --> Redis
```

---

## What changes in future phases

| Phase | What it adds to this picture |
|-------|------------------------------|
| Phase 5 | Browse API routers (customers, incidents, decisions) — all protected by `require_role(VIEWER)` |
| Phase 9 | Documents API with upload — protected by `require_role(ANALYST)` |
| Phase 12 | Research API — protected by `require_role(ANALYST)`; this is where the full RBAC test (`viewer → 403`) runs |
| Phase 15 | Real Redis in Docker Compose; `/health/ready` reports `redis: ok (real)` |
