# Phase 3 — Identity and Request Guards: Plain-English Explanation

> **Audience:** Non-technical readers — recruiters, interviewers, managers, stakeholders.
> **Goal:** Explain what was built in Phase 3 so anyone can understand it after a single read.

---

## What did Phase 3 accomplish?

Phases 1 and 2 gave us a working server with a fully seeded database. But anyone on the internet could send any request to it. Phase 3 adds the **security layer**: the bouncer at the door, the speed-limiter on the front desk, and the pen-and-paper log on the security desk.

Phase 3 has four pieces:

| # | Piece | What it does in plain words |
|---|-------|-----------------------------|
| P3-1 | JWT + Role Checks | Unforgeable identity badges and role-based door access |
| P3-2 | Demo Login Routes | A front desk that hands out those badges |
| P3-3 | Redis Rate Limiter | A throttle that stops any single visitor from flooding the front desk |
| P3-4 | Audit Middleware | A security log that records every change made in the system |

---

## P3-1 — JWT and Role Checks (the identity badge system)

### What is a JWT?

JWT stands for **JSON Web Token**. Think of it as a tamper-proof plastic badge. When a staff member logs in, the system prints them a badge that says:

> *"This badge belongs to Sarah. She is an Analyst. This badge is valid until 10:00 PM."*

The badge is **digitally signed** — if anyone tampers with the text (say, to change "Analyst" to "Admin"), the signature breaks and the badge is rejected at the door. This is done with a secret key that only the server knows.

### Three roles — one clear ladder

The platform has three roles, in ascending order of privilege:

| Role | What they can do |
|------|-----------------|
| `viewer` | Browse customers, incidents, decisions, and documents. Read-only. |
| `analyst` | Everything viewer can do, plus: start research, upload documents, run graph queries. |
| `admin` | Everything analyst can do, plus: delete documents, approve/reject others' requests. |

The rule is simple: **a higher number wins**. Viewer = 1, Analyst = 2, Admin = 3. Any door that requires Analyst (level 2) will let an Admin (level 3) through — because 3 ≥ 2.

This is enforced by a function called `require_role`. Every protected API endpoint in the system uses it, like a stamp on the door:

```
"This door requires Analyst (level 2) or above."
```

If a Viewer (level 1) tries to open it, they get back the response: **403 Forbidden**.

---

## P3-2 — Demo Login Routes (the front desk)

Three demo accounts exist so the system can be tested without any external login service:

| Username | Password | Role |
|----------|----------|------|
| `viewer` | `viewer123` | Viewer |
| `analyst` | `analyst123` | Analyst |
| `admin` | `admin123` | Admin |

When someone calls `POST /api/v1/auth/login` with these credentials, the server prints them a JWT badge and sends it back. Every subsequent request attaches this badge in the HTTP header, and the server uses it to identify the caller without looking up a database.

**Why is this useful?** For demonstration and testing, we can quickly switch between roles and prove that:
- A viewer genuinely cannot trigger research
- An analyst can
- An admin can do everything an analyst can, plus approve deletions

---

## P3-3 — Redis Rate Limiter (the throttle)

### The problem without a rate limiter

Without any throttle, a single script could flood the server with 10,000 requests per second — either accidentally (a buggy retry loop) or maliciously (a denial-of-service attack). This would slow the system down for everyone.

### How the rate limiter works

The rate limiter uses a simple but effective pattern called a **sliding window counter**:

1. Every incoming request is tagged with the caller's IP address and the current minute (like "visitor 192.168.1.1, minute 47").
2. A fast in-memory counter (stored in Redis) counts how many requests that visitor has made this minute.
3. If the count exceeds the allowed rate (default: 120 requests per minute), the server returns **429 Too Many Requests**.
4. The counter automatically resets every minute.

**Real-world analogy:** Think of a deli counter where each customer gets 120 ticket-pulls per minute. The 121st pull is politely refused until the next minute. No single customer can monopolise the service.

### Redis and fakeredis

The counter lives in **Redis** — a very fast in-memory database designed for exactly this kind of real-time counting.

For offline development and testing, the system automatically falls back to **fakeredis** — a Python library that behaves exactly like Redis but runs entirely in memory, with no server needed. This means `make test` works with zero external services, exactly as the project requires.

The `/health/ready` endpoint now also reports `"redis": {"status": "ok", "detail": "fakeredis"}` (or `"real"` when a live Redis is configured).

---

## P3-4 — Audit Middleware (the security desk log)

### What is middleware?

Middleware is code that **wraps every single request** as it passes through the server. Think of it as a security guard who stands in the hallway. Every person (request) passes through, and the guard decides what to do — let them through, block them, or write in a logbook.

The audit middleware specifically does the **logbook** part.

### What it records

For every request that **changes something** (creates, updates, or deletes — not simple views), the audit middleware writes a structured log entry like:

```json
{
  "msg": "audit",
  "method": "POST",
  "path": "/api/v1/documents",
  "status_code": 201,
  "request_id": "abc-123-xyz"
}
```

Notice the `request_id` — it is the same unique ID that the Phase 1 middleware attached. This means: if something goes wrong, an engineer can type the request ID into the monitoring dashboard and find the audit entry, the error log, and every other log line related to that specific action — all linked together.

### The middleware stack order

This is an important design detail. Middleware executes in a specific order, and that order matters:

```
Incoming request
       ↓
1. CORS check (is this request from an allowed website?)
2. Request-ID middleware (assign the unique tracking ID)
3. Rate-limit middleware (is this caller over their quota?)
4. Audit middleware (write the logbook entry AFTER the request completes)
       ↓
Route handler (the actual work)
       ↑
(response travels back up through the same layers in reverse)
```

Audit comes **last** (innermost layer, closest to the route) because it needs to know the final HTTP status code (200, 201, 403, etc.) — which is only known after the route handler runs.

---

## How it all fits together

After Phase 3, the full request lifecycle for an analyst starting a research job looks like this:

```
1. Analyst opens the web UI
2. UI calls POST /api/v1/auth/login → receives JWT badge
3. Analyst types a question; UI calls POST /api/v1/research
   with the JWT in the Authorization header

4. CORS middleware: origin is allowed ✅
5. Request-ID middleware: assigns "req-abc-123" ✅
6. Rate-limit middleware: analyst has made 5 requests this minute (< 120) ✅
7. Auth check (require_role): JWT decoded → Analyst (level 2) ≥ required Analyst (level 2) ✅
8. Research handler: starts research job → returns 202 Accepted
9. Audit middleware: logs POST /api/v1/research status=202 req=req-abc-123
10. Response returns with X-Request-ID: req-abc-123
```

If the same person had a Viewer role and tried step 7, they would have received **403 Forbidden** at step 7 — and that 403 would still be logged by the audit middleware.

---

## What is NOT in Phase 3 yet?

- No real external authentication (Supabase integration comes later)
- No persistent audit table in the database (Phase 3 audit writes to structured JSON logs only)
- The research endpoint itself does not exist yet (comes in Phase 12)

---

## Summary for the interview board

**What did Phase 3 accomplish?**

We added the security layer that every production web application needs:

1. **Identity** — JWT tokens signed with a secret key prove who is making each request, without hitting a database on every call
2. **Role hierarchy** — viewer < analyst < admin; a single `require_role(analyst)` call on any route is all the protection it needs
3. **Demo accounts** — three pre-built logins let us demo and test all three permission levels instantly
4. **Rate limiting** — a Redis-backed sliding window stops any single client from flooding the server; falls back to fakeredis offline
5. **Audit logging** — every state-changing request (POST, PUT, PATCH, DELETE) produces a structured log entry with the correlation ID, so engineers can trace any change

**Why does this matter?**

Security is not a feature you can bolt on after the fact. By building it in Phase 3 — before any research logic or user-facing screens — every future endpoint automatically inherits the protection. There is no "we'll add auth later" debt here.
