# Phase 3 — Interview Q&A: Identity and Request Guards

> **Audience:** Technical and semi-technical interviewers
> **Covers:** JWT, RBAC, rate limiting, middleware, Redis, audit logging

---

## Section 1: JWT Authentication

**Q1: What is a JWT and why did you choose it over session-based auth?**

A JWT (JSON Web Token) is a self-contained, digitally signed token that carries claims (user id, role, expiry) inside itself. The server does not need to look up a session table on every request — it just verifies the signature.

We chose JWT for three reasons:
1. **Stateless** — the backend can scale horizontally without sharing session storage
2. **Offline-first** — no external auth service needed; the secret key lives in `.env`
3. **Easy role embedding** — the role integer is baked into the token, so `require_role` is a single comparison

The trade-off: once issued, a JWT cannot be revoked before expiry without maintaining a blocklist (which is essentially a session store again). For this platform the token lifetime is 60 minutes, which is an acceptable window.

---

**Q2: What algorithm does the platform use and how does it prevent tampering?**

HS256 — HMAC with SHA-256. The server signs the token with a secret key stored in `JWT_SECRET`. Anyone with the token can read the claims (they are base64-encoded, not encrypted), but cannot change them without invalidating the signature. If the payload is modified, `jwt.decode()` raises `InvalidTokenError` and the request gets 401.

For higher-security deployments, RS256 (asymmetric key pair) could be used so that any service can verify tokens without knowing the signing key. For v1, HS256 is sufficient.

---

**Q3: How does `require_role` work as a FastAPI dependency?**

```python
def require_role(minimum: Role):
    async def _check(user: Annotated[UserContext, Depends(get_current_user)]) -> UserContext:
        if user.role < minimum:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check
```

`require_role(Role.ANALYST)` is a **dependency factory** — it returns an async function that FastAPI injects into the route handler. FastAPI's dependency injection chains `get_current_user` (which decodes the JWT) automatically. The route never needs to touch tokens directly.

Annotating a route with `Depends(require_role(Role.ANALYST))` means:
1. No token → 401 (from `get_current_user`)
2. Token present, role < ANALYST → 403 (from `require_role`)
3. Token present, role ≥ ANALYST → handler runs

---

**Q4: What is the role hierarchy and how is it enforced?**

```
Role.VIEWER  = 1
Role.ANALYST = 2
Role.ADMIN   = 3
```

Using `IntEnum` means `Role.ADMIN > Role.ANALYST > Role.VIEWER` with standard integer comparison. `require_role(minimum)` does `if user.role < minimum: raise 403`. This means:
- Admin passes every Analyst check automatically
- Analyst does not pass Admin checks
- Viewer passes no protected checks at all

The hierarchy is defined once and never duplicated — no long `if role in ("analyst", "admin"):` checks scattered across the codebase.

---

## Section 2: Rate Limiting

**Q5: Explain the token-bucket / sliding-window rate limiter you implemented.**

The implementation uses a **sliding-window counter** (not strictly a token bucket, but the effect is equivalent at this granularity):

- Key: `rl:{client_ip}:{int(time.time() // 60)}` — unique per client per minute window
- On each request: `INCR key` returns the new count; if the key is new, `EXPIRE key 60` is also called
- If count > `RATE_LIMIT_PER_MINUTE` (default 120) → return 429
- The key expires naturally after 60 seconds

This approach is O(1) per request (two Redis commands) and uses O(clients) memory in Redis.

Limitation: requests at the boundary of two minutes get a fresh window immediately (a client could fire 120 requests at 11:59 and 120 more at 12:00, for 240 in 2 seconds). A true sliding window (storing per-request timestamps) would prevent this but is more expensive. For this platform the simpler approach is sufficient.

---

**Q6: Why use Redis for rate limiting instead of a local counter?**

Local (in-process) counters don't work when the application runs on multiple servers — each instance would have its own counter, allowing a client to bypass the limit by routing requests to different instances. Redis is shared across all instances and handles atomic increments natively.

For offline development and tests, `fakeredis` provides identical behaviour with zero infrastructure.

---

**Q7: What happens if Redis is down?**

```python
try:
    redis = get_redis_client()
    count = redis.incr(key)
    ...
except Exception:
    pass  # allow request through
```

The middleware catches all exceptions silently and lets the request proceed. This is a **fail-open** design: a Redis outage degrades rate limiting but does not take down the entire API. The alternative (fail-closed, return 503 when Redis is unavailable) would make a Redis downtime into a full service outage, which is a worse trade-off for most applications.

---

**Q8: How did you test the rate limiter without a real Redis?**

We used `fakeredis` — a Python library that implements the Redis wire protocol entirely in memory. The same `get_redis_client()` call returns a `fakeredis.FakeRedis()` instance when `REDIS_URL=""`. The rate limit middleware code is identical whether it talks to real Redis or fakeredis.

The test fixture:
1. Sets `RATE_LIMIT_PER_MINUTE=3` (a low limit to avoid making many requests)
2. Flushes the fakeredis instance before and after each test (to avoid counter bleed from other tests)
3. Makes 4 requests and asserts the 4th returns 429

---

## Section 3: Middleware

**Q9: What is middleware and how does the middleware stack work in this application?**

Middleware is code that wraps every HTTP request/response. In FastAPI/Starlette, `add_middleware()` stacks middlewares — each one calls `call_next(request)` to pass the request to the next layer, then processes the response on the way back.

The middleware execution order in Phase 3:

```
Request → CORS → RequestContext → RateLimit → Audit → Route Handler
Response ← CORS ← RequestContext ← RateLimit ← Audit ← Route Handler
```

**Important Starlette detail:** `add_middleware(A)` then `add_middleware(B)` stores them as `[B, A]` (insert at 0). Starlette reverses the list when building the stack, making the first-added middleware the outermost. So "first added = executes first on request, last on response."

---

**Q10: Why does AuditMiddleware read `X-Request-ID` from the response header instead of the ContextVar?**

`BaseHTTPMiddleware` runs `call_next` in a new `anyio` task. Python's `ContextVar` changes do not automatically propagate across task boundaries. When `RequestContextMiddleware` sets `request_id_var` in its context, that value is not visible in the task created by `call_next` further down the stack.

The solution: `RequestContextMiddleware` writes the ID to `response.headers["X-Request-ID"]` before returning. The response object is passed back through the middleware chain as a regular Python object — no task boundaries involved. `AuditMiddleware` reads from the header reliably regardless of asyncio task structure.

---

**Q11: Why is audit placed innermost (last added) rather than outermost?**

Audit needs the **HTTP response status code** (200, 201, 403, 500, etc.) to log whether the operation succeeded. The status code only exists after the route handler runs. If audit were placed outermost, it would call `call_next` and wait for the inner layers to complete before logging — which is exactly what it does, but as the innermost middleware, it gets the response back first and can log before the response travels back through rate-limit and request-context. The functional result is the same either way; innermost simply means the audit entry is written slightly earlier in the response journey.

---

## Section 4: Security Design

**Q12: How is the RBAC pattern used consistently across the codebase?**

Every protected endpoint uses one of:

```python
Depends(get_current_user)           # any authenticated user (viewer+)
Depends(require_role(Role.ANALYST)) # analyst or above
Depends(require_role(Role.ADMIN))   # admin only
```

The `require_role` function is defined once in `core/security.py` and injected via FastAPI's dependency system. There is no "check the role in the handler body" anti-pattern — the access check happens before the handler runs. If `require_role` raises 403, the handler never executes.

---

**Q13: Why are there only three demo users and not a real user management system?**

Three reasons:
1. **Offline-first requirement (N1):** a real user store (Supabase Auth, Auth0) needs credentials and network access. The platform must work with zero external services.
2. **Testing clarity:** three distinct roles make it trivial to write parametrised tests that prove the entire permission matrix.
3. **Phase scope:** real user CRUD is a Phase 3-equivalent but separate concern from the RBAC mechanism. The demo accounts prove the JWT and role system work; swapping the credential check for Supabase JWT verification is a one-function change.

---

**Q14: What would you change if this were going to production?**

1. **Stronger JWT secret management:** rotate via a secrets manager (AWS Secrets Manager, Vault), not a `.env` file.
2. **Token refresh endpoint:** issue short-lived access tokens (15 min) and long-lived refresh tokens (7 days).
3. **JWT revocation list:** for logout and security incidents, maintain a Redis blocklist of revoked JIDs.
4. **Real user accounts:** replace the hardcoded `_DEMO_USERS` dict with a database table or Supabase Auth integration.
5. **Asymmetric JWT signing (RS256):** so microservices can verify tokens without the signing key.
6. **Fail-closed rate limiting option:** for production APIs where availability guarantees justify it.

---

## Section 5: Testing

**Q15: How did you test the RBAC without a live research endpoint?**

The auth router includes a minimal `GET /api/v1/auth/analyst-only` endpoint that requires `Role.ANALYST`. The test proves:
- No token → 401
- Viewer token → 403
- Analyst token → 200
- Admin token → 200 (admin satisfies analyst requirement)

This is intentional: Phase 3's "initial form" of the RBAC test covers the mechanism cleanly. When the research endpoint is built in Phase 12, the full `test_auth_required_and_rbac` test will assert `viewer → 403 on POST /api/v1/research` using the same `require_role` function already proven here.

---

**Q16: How do tests ensure rate-limit counters don't bleed between test cases?**

The test file uses an `autouse` fixture that calls `get_redis_client().flushall()` both before and after each test. Because all tests share the same `fakeredis` instance (via `lru_cache`), without flushing, counters accumulated by prior tests (22+ requests from auth and audit tests) would already exceed the limit of 3 when the rate limit test starts.

Flushing before the test resets the counter to zero, ensuring clean isolation without resetting the `lru_cache` or creating a new fakeredis instance.

---

**Q17: How does `_reset_settings` in conftest.py help the rate limit test?**

`get_settings()` is `lru_cache`d. Without resetting it, changing `RATE_LIMIT_PER_MINUTE` in `os.environ` would have no effect — the cached settings object would still return 120. The `_reset_settings` autouse fixture clears the cache before and after every test. The `low_limit_client` fixture sets `RATE_LIMIT_PER_MINUTE=3` in the environment, then calls `reset_settings_cache()` manually so the new value takes effect immediately.

---

## Quick reference

| Concept | Location | Key point |
|---------|----------|-----------|
| JWT encode/decode | `backend/app/core/security.py` | HS256, `lru_cache` on settings |
| Role definition | `security.py::Role(IntEnum)` | 1=viewer, 2=analyst, 3=admin |
| `require_role` | `security.py::require_role()` | Dependency factory, raises 403 |
| Demo login | `backend/app/api/auth.py` | 3 hardcoded demo accounts |
| Redis client | `backend/app/core/redis_client.py` | fakeredis when `REDIS_URL=""` |
| Rate limiter | `backend/app/middleware/rate_limit.py` | sliding-window, 429 on exceed |
| Audit logger | `backend/app/middleware/audit.py` | POST/PUT/PATCH/DELETE only |
| Middleware order | `backend/app/main.py` | CORS→ReqCtx→RateLimit→Audit |
| Tests | `tests/api/test_auth_rbac.py` | 14 tests |
| Tests | `tests/api/test_rate_limit.py` | 3 tests |
| Tests | `tests/api/test_audit_log.py` | 5 tests |
