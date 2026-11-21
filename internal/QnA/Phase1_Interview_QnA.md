# Phase 1 — Interview Q&A

> All possible interview questions from Phase 1 (Runtime Skeleton), with thorough answers.
> Covers technical depth, design decisions, and "why" questions.

---

## Section 1 — Architecture and Design

**Q1. What is the purpose of Phase 1 and why did you build it before the AI features?**

> Phase 1 is the "runtime skeleton" — it establishes the foundational infrastructure on which every later feature is built. Without reliable configuration management, structured logging, health checks, and an automated test harness, any AI feature added on top would be built on sand. Problems in production would be nearly impossible to diagnose (no structured logs, no request IDs), and regressions would go undetected (no test harness, no CI).
>
> More practically: a production API that lacks `/health/ready` cannot be safely deployed to Kubernetes. Skipping Phase 1 would mean retrofitting all of this later under time pressure, which is expensive.

---

**Q2. Why use FastAPI instead of Django or Flask?**

> FastAPI was chosen because:
> - It is built on ASGI (async from the ground up), which matters for LangGraph agent runs and streaming responses in later phases
> - Pydantic v2 for automatic request/response validation is a first-class feature, not an add-on
> - It generates OpenAPI docs (`/docs`) automatically
> - Dependency injection (`Depends(get_settings)`) is clean and testable
>
> Django is better for large monoliths with ORM-heavy admin interfaces. Flask lacks native async support and Pydantic integration. FastAPI fits an API-first AI platform.

---

**Q3. What is the layering rule and why does it matter?**

> The rule (from CLAUDE.md §4.2): `api → services → repositories → models`. Each layer may only import from the layer below it. The `core/` module is the bottom and may never import from `agents/`, `rag/`, or `memory/`.
>
> This matters because:
> - **Circular imports** crash Python at startup and are very hard to debug
> - **Testability**: if `api/` talks directly to the database, you can't test routing logic without a live database
> - **Separation of concerns**: an HTTP shape change (rename a JSON field) should not require touching the database query
>
> Phase 1 establishes `core/` as the foundation. Everything built later imports from `core/`, not the other way around.

---

**Q4. Why is `get_settings()` wrapped in `lru_cache`?**

> `pydantic-settings` reads the `.env` file and validates environment variables. This is cheap, but it touches the file system and builds a full Python object. If called on every request, it becomes unnecessary overhead.
>
> `@functools.lru_cache(maxsize=1)` caches the single `Settings` instance. All callers share the same object — there is exactly one source of truth at runtime.
>
> The companion `reset_settings_cache()` function exists solely for tests: a test that needs to change `LLM_PROVIDER=openai` calls `reset_settings_cache()`, sets the env var, then calls `get_settings()` to get a fresh object. This is the standard pattern for testing settings in Python.

---

**Q5. What is the "check registry" pattern used in `/health/ready`?**

> The check registry is a global dictionary `{name: callable}`. Each subsystem (database, Redis, vector store, etc.) registers a function that returns `{"status": "ok/degraded/error", "detail": "..."}`.
>
> When `/health/ready` is called, it iterates the dict, calls every function, and returns the aggregate result. If any check returns `error`, the HTTP status code is 503; otherwise 200.
>
> This is a classic **observer** or **plugin** pattern. The health router knows nothing about databases or caches — it just runs whatever is in the registry. This means Phase 7 can add a Neo4j check by calling `register_check("graph_store", neo4j_check_fn)` during lifespan without modifying the health router.

---

**Q6. Why is the lifespan function used instead of `@app.on_event("startup")`?**

> `@app.on_event("startup")` and `@app.on_event("shutdown")` are deprecated in FastAPI 0.93+. The modern replacement is an `asynccontextmanager` passed as `lifespan` to the `FastAPI()` constructor. It:
> - Groups startup and shutdown in one function (easier to review)
> - Supports `async with` for proper resource cleanup (database pools, etc.)
> - Is used by the `TestClient` context manager, so tests can run lifespan hooks just like production

---

## Section 2 — Middleware and Request Handling

**Q7. How does the X-Request-ID middleware work, and why use a ContextVar?**

> The middleware intercepts every request:
> 1. If `X-Request-ID` header is present → use that value
> 2. Otherwise → generate `str(uuid.uuid4())`
> 3. Set the value into `request_id_var` (a `contextvars.ContextVar`)
> 4. Call the next handler
> 5. Add the ID to the response header
> 6. Reset the ContextVar
>
> `ContextVar` is essential for async applications. Python's `threading.local` is not safe in an async context because multiple async tasks run in the same thread. `ContextVar` is designed specifically for this: each async "context" (each request task) gets its own value, isolated from other concurrent requests.
>
> Every JSON log line reads `request_id_var.get()`, so logs from different requests never get mixed up even under high concurrency.

---

**Q8. Why is the middleware order important? What happens if it is reversed?**

> The declared order:
> ```
> app.add_middleware(CORSMiddleware)             # outermost (Starlette reverses)
> app.add_middleware(RequestContextMiddleware)   # innermost
> ```
> Starlette reverses middleware order: the last added runs first. So `RequestContext` runs before `CORS`.
>
> If reversed, `CORS` would run before the request ID is set. Cross-origin requests would fail before getting a request ID in the response — making CORS errors invisible in logs.
>
> When Phase 3 adds rate limiting and audit middleware, they must be inserted between `RequestContext` (must run first to set the ID) and the route handler. The order is: `request-id → rate-limit → audit → route`.

---

**Q9. What does the `conftest.py` autouse fixture do, and why is it needed?**

> ```python
> @pytest.fixture(autouse=True)
> def _reset_settings():
>     reset_settings_cache()
>     yield
>     reset_settings_cache()
> ```
> `autouse=True` means this fixture runs automatically for every test, without being explicitly requested.
>
> It clears the `get_settings()` lru_cache before the test (so env changes from a previous test don't leak) and after (so this test's env changes don't leak to the next test). Without this, test ordering would matter — a test that sets `LLM_PROVIDER=openai` would corrupt all subsequent tests.

---

## Section 3 — Testing

**Q10. What does "offline testing" mean and why is it a design goal?**

> Offline testing means the full test suite runs with:
> - `LLM_PROVIDER=fake` — no real AI API calls, no cost, no flakiness from network
> - `VECTOR_STORE=memory` — no Qdrant server or Docker required
> - `GRAPH_STORE=memory` — no Neo4j server or Docker required
> - `DATABASE_URL=sqlite:///` — no PostgreSQL required
> - `REDIS_URL=""` — uses fakeredis, an in-process Redis mock
>
> The goal: any developer can run `make test` on a laptop with no internet, and it completes in under 10 seconds. This is also required for CI — a CI runner should not make paid API calls.

---

**Q11. Why does the test for 404 check for X-Request-ID?**

> This tests that the middleware runs even when the route does not exist. If the middleware only ran for known routes, error responses would lack the ID — making production debugging of 404 or 500 errors harder.
>
> `FastAPI` returns a 404 from its internal routing layer, but the middleware stack is still traversed, so the ID is still added.

---

**Q12. What is the difference between `app` (session scope) and `client` (function scope) fixtures?**

> - `app` is session-scoped: the FastAPI application object is created once per test session. This is cheap and correct because the app object has no mutable per-test state.
> - `client` is function-scoped (default): a new `TestClient` context is opened for each test. This runs the lifespan (startup + shutdown) on each test, which resets the check registry to a clean state.
>
> If `client` were session-scoped, the check registry could accumulate stale entries across tests.

---

## Section 4 — DevOps and Tooling

**Q13. What is `uv` and why was it chosen over pip?**

> `uv` is a next-generation Python package manager written in Rust. Advantages over pip:
> - 10–100× faster installs (cached wheels, parallel downloads)
> - Deterministic installs via `uv.lock` (similar to Cargo.lock or package-lock.json)
> - `uv sync` installs exactly what is in the lock file — no "it works on my machine" issues
> - Single tool replaces: pip, virtualenv, pip-tools, pipenv, poetry (for most use cases)
>
> `uv.lock` is committed to git so every CI run installs the identical dependency versions as the developer.

---

**Q14. What does `ruff` check for, and what were the issues found and fixed in Phase 1?**

> Ruff is a Python linter and formatter, 10–100× faster than flake8 + black + isort combined.
>
> Issues fixed during Phase 1:
> - `E401` — multiple imports on one line (`import datetime, json, os, sys` → split)
> - `I001` — unsorted imports → sorted by isort rules
> - `E501` — line longer than 100 chars in `config.py` → wrapped the `Literal` type
> - `UP035` — deprecated `typing.Callable` → replaced with `collections.abc.Callable`
> - `UP017` — deprecated `timezone.utc` → replaced with `datetime.UTC`
>
> All five issues were either auto-fixed by `ruff check --fix` or reformatted by `ruff format`.

---

**Q15. How does the GitHub Actions CI pipeline trigger and what does it check?**

> Triggers:
> - Push to `development`, `testing`, or `main`
> - Pull request targeting `development`
>
> Steps:
> 1. Checkout code
> 2. Install Python 3.12
> 3. Install `uv`
> 4. `uv sync --all-groups` (installs all dependencies including dev)
> 5. `ruff check .` — if any lint error, the job fails
> 6. `ruff format --check .` — if any file needs formatting, the job fails
> 7. `pytest tests/ -v` with offline env vars set
>
> The pipeline uses official Actions from `actions/` and `astral-sh/setup-uv`. All env vars for offline testing are set in the `env:` block of the pytest step.

---

## Section 5 — Production Readiness Concepts

**Q16. What is ASGI and why does it matter for this project?**

> ASGI (Asynchronous Server Gateway Interface) is the Python standard for async web servers. It is to async Python what WSGI is to synchronous Python.
>
> It matters because:
> - The LangGraph research workflow (Phase 12) runs for 7+ seconds per request. With ASGI, the server can handle other requests while waiting for the AI pipeline to complete — no thread blocking.
> - Server-Sent Events (for real-time progress streaming) require ASGI.
> - `BackgroundTasks` (which runs the research graph after returning 202) requires ASGI.

---

**Q17. What is the difference between `/health/live` and `/health/ready`?**

> These are Kubernetes probe patterns:
>
> | Probe | Question | Failure action |
> |-------|----------|----------------|
> | Liveness (`/health/live`) | Is the process still running / not deadlocked? | Kubernetes restarts the container |
> | Readiness (`/health/ready`) | Is the app ready to receive traffic? | Kubernetes removes the pod from load balancer |
>
> A container can be live (not deadlocked) but not ready (database still connecting). Kubernetes should not send traffic to it yet, but should not restart it either. The two probes handle this correctly.
>
> `/health/ready` returns `degraded` (not `error`) when the graph store (Neo4j) is down — the app can still answer non-graph questions, so it stays in the load balancer rotation.

---

**Q18. What is `PYTHONIOENCODING=utf-8` and why is it set in the Makefile?**

> On Windows, the default console code page is often CP1252 (Western European). Python's stdout in a Windows terminal would then try to encode output in CP1252, which fails on Unicode characters like box-drawing characters (┌─┐) used in demo output.
>
> `PYTHONIOENCODING=utf-8` forces stdout/stderr to use UTF-8 encoding, matching what the application writes. This is a Windows-only quirk; on Linux/macOS the default is already UTF-8.

---

**Q19. Why does `.env` get committed to git when `.env.example` does not?**

> This is the opposite: `.env` is **NOT** committed. `.env.example` IS committed.
>
> `.env` contains real values (API keys, database passwords). It must never be in git.
> `.env.example` contains placeholder values (`LLM_API_KEY=`). It is the documentation for what variables exist and must be in git.
>
> The `.gitignore` rule is: `.env` and `.env.*` are ignored, with the exception `!.env.example` (the `!` prefix means "do not ignore this one").

---

**Q20. If you had to add a new environment variable for Phase 2, what are the steps?**

> 1. Add a field to the `Settings` class in `backend/app/core/config.py`
> 2. Add a placeholder line in `.env.example` with a comment explaining the variable
> 3. If needed, add a default to `.env` on each developer machine
> 4. Document it in `CLAUDE.md §9.1`
>
> The `get_settings()` function and `lru_cache` require no changes — `pydantic-settings` picks up the new field automatically. Restarting the backend applies the new setting (the `lru_cache` is per-process).
