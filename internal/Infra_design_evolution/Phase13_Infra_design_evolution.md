# Phase 13 — Infrastructure and Component Wiring Design Evolution

## Overview

Phase 13 introduces the first user-facing component: a Next.js 15 web application running on port 3001. This document explains how the new frontend process wires into the existing backend infrastructure, how traffic flows between components, and how the development setup is structured.

---

## Infrastructure before Phase 13

Before Phase 13, the entire system ran as a single Python process. There was no browser component.

```mermaid
graph LR
    Dev[Developer terminal] -->|curl / Postman| FastAPI[FastAPI\n:8001]
    FastAPI --> SQLite[(SQLite\ndata/enterprise.db)]
    FastAPI --> MemVS[(Memory\nVector Store)]
    FastAPI --> MemGS[(Memory\nGraph Store)]
    FastAPI --> FakeRedis[(fakeredis\nin-process)]
    FastAPI --> FakeLLM[(Fake LLM\nin-process)]
```

All infrastructure was in-process or file-based. Zero external services required. This was the N1 requirement (run with no API key and no external service).

---

## What Phase 13 adds: a second process

Phase 13 introduces a **second process** — the Next.js development server — running on port 3001. The two processes are independent: each can be started, stopped, and restarted without affecting the other.

```mermaid
graph TD
    Browser[Browser] -->|HTTP :3001| NextJS[Next.js Dev Server\n:3001\nnpm run dev]
    NextJS -->|Next.js rewrite proxy| FastAPI[FastAPI\n:8001\nuvicorn]
    FastAPI --> SQLite[(SQLite)]
    FastAPI --> MemVS[(Vector Store\nin-memory)]
    FastAPI --> MemGS[(Graph Store\nin-memory)]
    FastAPI --> FakeRedis[(Redis\nfakeredis)]
    FastAPI --> FakeLLM[(Fake LLM)]
```

**Key insight:** The browser never talks directly to port 8001. All API calls go to the Next.js server first, which proxies them to FastAPI via Next.js rewrites. From the browser's perspective, there is only one server.

---

## Next.js rewrites — how the proxy works

The `next.config.ts` file defines URL rewrite rules:

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js :3001
    participant F as FastAPI :8001

    B->>N: GET /api/v1/customers
    Note over N: Rewrite rule matches /api/v1/*
    N->>F: GET /api/v1/customers (proxied)
    F-->>N: JSON response + X-Request-ID header
    N-->>B: Same JSON response (headers forwarded)
```

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js :3001
    participant F as FastAPI :8001

    B->>N: GET /health/ready
    Note over N: Rewrite rule matches /health/*
    N->>F: GET /health/ready (proxied)
    F-->>N: {status: "ok", checks: {...}}
    N-->>B: Forwarded response
```

**Why this matters:**
- No CORS headers needed on the FastAPI side during development.
- The browser bundle never contains the backend's internal address.
- In production, a real reverse proxy (Nginx, Caddy, or a cloud load balancer) would replace the Next.js rewrites.

---

## Port assignment and process map

```mermaid
graph TD
    subgraph Host machine
        subgraph Process 1 [Python process — uvicorn]
            FastAPI[FastAPI app\n:8001]
        end

        subgraph Process 2 [Node.js process — Next.js]
            NextDev[Next.js dev server\n:3001]
        end

        subgraph In-process stores [loaded into Python process]
            VS[Memory Vector Store]
            GS[Memory Graph Store]
            FR[fakeredis]
            FL[Fake LLM]
        end

        subgraph File system
            DB[(SQLite\ndata/enterprise.db)]
            SD[(sample_data/\n*.json + documents/*.md)]
        end
    end

    Browser -->|:3001| NextDev
    NextDev -->|:8001 proxy| FastAPI
    FastAPI --- VS & GS & FR & FL
    FastAPI --- DB & SD
```

---

## Make targets for the two-process setup

```mermaid
graph LR
    Dev[Developer] -->|make backend| P1[uvicorn on :8001]
    Dev -->|make frontend| P2[npm run dev on :3001]
    Dev -->|make test| Tests[pytest offline\nno browser required]
    Dev -->|make demo| Demo[CLI demo\nno browser required]
```

The two servers must run in **separate terminal windows** simultaneously during full-stack development. The test suite (`make test`) does not require the frontend process — it tests the backend directly.

---

## Browser session management

```mermaid
graph TD
    Login[/login page] -->|POST /api/v1/auth/login| Token[Receive JWT]
    Token -->|sessionStorage.setItem| SS[Browser sessionStorage\ntoken + role]
    SS -->|read on each request| Client[api-client.ts\nAdds Authorization header]
    Client -->|Bearer token| FastAPI

    TabClose[User closes tab] -->|sessionStorage cleared| Logout[Auto logout]
    SignOut[Sign out button] -->|clearToken| SS2[sessionStorage cleared]
    SS2 -->|router.push /login| Login
```

**Why sessionStorage and not localStorage?**
- `sessionStorage` is cleared when the browser tab is closed. The JWT cannot accidentally persist to a shared computer.
- `localStorage` persists across browser restarts — suitable for user preferences, not authentication tokens.

---

## Request tracing across the two layers

Every response from FastAPI includes an `X-Request-ID` header (from Phase 1's middleware). The frontend's API client captures this ID and includes it in `ApiError` objects so it can be shown in the UI alongside error messages.

```mermaid
sequenceDiagram
    participant B as Browser
    participant N as Next.js
    participant F as FastAPI

    B->>N: POST /api/v1/research
    N->>F: POST /api/v1/research
    Note over F: request_context middleware\nassigns X-Request-ID: abc-123
    F-->>N: 202 + X-Request-ID: abc-123
    N-->>B: 202 + X-Request-ID: abc-123
    Note over B: api-client captures requestId\nshown in ApiError if something fails
```

---

## Rate limit handling at the client layer

```mermaid
graph TD
    Call[api-client makes a request] -->|check| RLCheck{Date.now &lt;\n_rateLimitUntil?}
    RLCheck -->|Yes — blocked| Throw[throw ApiError 429\n"Retry in Ns"]
    RLCheck -->|No| Fetch[fetch to backend]
    Fetch -->|status 429| SetRL[_rateLimitUntil = now + 60s]
    SetRL --> Throw
    Fetch -->|status ok| Return[Return parsed JSON]
```

The client-side rate limit guard prevents the browser from hammering the backend with retry loops after a 429. This is a client-side courtesy to the backend — the backend still enforces its own Redis token-bucket limit from Phase 3.

---

## Health check wiring

```mermaid
graph TD
    HealthBanner[HealthBanner component\nmounts on app layout] -->|GET /health/ready| NextProxy[Next.js proxy]
    NextProxy --> FastAPI

    FastAPI -->|check each store| DB2[(database)]
    FastAPI -->|check| Redis2[(redis)]
    FastAPI -->|check| VS2[(vector_store)]
    FastAPI -->|check| GS2[(graph_store)]
    FastAPI -->|check| LLM2[(llm)]

    FastAPI -->|aggregate| Status{Overall status}
    Status -->|all ok| OK[status: ok\nBanner hidden]
    Status -->|any degraded| Degraded[status: degraded\nAmber banner shown]
    Status -->|any error| Error[status: error\nAmber banner shown]
```

The health banner runs once on mount and does not poll. It is a startup indicator, not a live monitor. Polling the health endpoint on every page would create unnecessary load.

---

## Development environment summary

| Component | Technology | Port | Restart trigger |
|-----------|-----------|------|----------------|
| FastAPI backend | Python / uvicorn | 8001 | Python file change (--reload) |
| Next.js frontend | Node.js / Next.js 15 | 3001 | TypeScript file change (HMR) |
| Vector store | Python in-memory | — | Restart backend |
| Graph store | Python in-memory | — | Restart backend |
| Redis | fakeredis in-process | — | Restart backend |
| Database | SQLite file | — | Persists across restarts |

**Hot reload:** both servers support hot reload in development. The FastAPI uvicorn process reloads on Python file changes. The Next.js dev server uses Hot Module Replacement (HMR) for instant TypeScript/CSS updates in the browser.

---

## Production topology (Phase 15 preview)

Phase 15 will introduce Docker Compose with real external services. The topology will grow:

```mermaid
graph TD
    subgraph Cloud / Docker Compose
        NginxLB[Nginx\nreverse proxy\n:80 / :443]
        NginxLB -->|/| NextProd[Next.js\nproduction build\n:3001]
        NginxLB -->|/api| FastAPIProd[FastAPI\n:8001]

        FastAPIProd --> PG[(PostgreSQL\nSupabase)]
        FastAPIProd --> QD[(Qdrant\nvector store)]
        FastAPIProd --> Neo4j[(Neo4j Aura\ngraph store)]
        FastAPIProd --> RealRedis[(Redis)]
        FastAPIProd --> RealLLM[(OpenAI / Anthropic)]
    end

    Browser -->|HTTPS| NginxLB
```

The separation of the two processes that Phase 13 establishes is exactly what makes this future topology straightforward — each process just points to a different backend URL.
