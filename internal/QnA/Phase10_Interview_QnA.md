# Phase 10 — Memory: Interview Questions and Answers

---

## Conceptual questions

**Q1: Why does the platform need memory at all? Isn't the database enough?**

The database stores structured enterprise data — incidents, customers, decisions. Memory is different: it stores *context for reasoning*, not facts about the business domain. The four scopes serve different purposes:
- **Organizational memory** provides shared company conventions (like how the fiscal calendar defines "last quarter") that the AI needs to interpret queries correctly.
- **Conversation memory** lets the assistant remember what was established earlier in the same session, avoiding repetition.
- **Session memory** tracks what the AI discovered during the current research run.
- **Analyst memory** lets individual analysts personalise the assistant's behaviour.

None of these belongs in the incidents table or the customers table.

---

**Q2: Why are the four memory scopes kept completely separate? Why not one unified memory table?**

Three reasons:
1. **Lifetime**: organizational memory lasts forever; conversation memory lasts 24 hours; session memory lasts the duration of one run; analyst memory lasts until the analyst deletes it. One table with one schema cannot express these different lifetimes cleanly.
2. **Ownership**: organizational memory is shared; conversation memory belongs to a session; analyst memory belongs to one person. Mixing ownership models invites security bugs.
3. **Backend**: fast in-memory storage (Redis) is the right choice for ephemeral conversation turns; a persistent database is correct for analyst notes that must survive restarts. Using one backend for both would be a compromise.

---

**Q3: Why does memory never get cited as evidence?**

Evidence items are facts retrieved from verifiable sources — a document, a database row, a graph traversal. Each can be traced to a specific origin and deserves a citation number like `[3]`.

Memory is **context** — it shapes how the AI interprets a question, not what it cites in an answer. Citing "my personal preference for bullet points" or "the fiscal calendar says Q3 is July–September" as a source would be misleading. The fiscal calendar is used to *construct the query*, not to answer it.

The separation also makes the system auditable: every `[n]` in the answer resolves to retrieved evidence, and an auditor can verify every claim.

---

## Technical questions

**Q4: How does "last quarter" resolution work technically?**

The `organizational_memory.json` file defines the fiscal calendar:
```json
"Q3": {"start_month": 7, "end_month": 9, "label": "July – September"}
```

The `resolve_quarter()` function:
1. Reads today's date.
2. Computes the current quarter number (e.g. November → Q4).
3. Subtracts one to get Q3.
4. Looks up Q3 in the calendar and returns `{start_date: "2026-07-01", end_date: "2026-09-30"}`.

This date range is then passed directly to the SQL query as a date filter. If today were February 2027, "last quarter" would resolve to Q4 2026 (October–December) — the function handles the year wrap correctly.

---

**Q5: Why is conversation memory stored in Redis rather than the database?**

Redis is a key-value store optimised for:
- **Fast ordered lists**: each turn is appended to a list; the whole list is returned in insertion order with one command (`LRANGE`).
- **TTL (time-to-live)**: Redis natively expires keys after 24 hours. Implementing expiry in a relational database requires either a background job or partitioned tables.
- **In-memory speed**: conversation history is read on every request; latency matters more than durability.

A database would work but would add unnecessary complexity. The conversation history is ephemeral by design — losing it in a Redis restart is acceptable; losing analyst notes in a database crash is not.

---

**Q6: What is fakeredis and why does the project use it?**

`fakeredis` is a Python library that implements the Redis API in memory, with no actual Redis server. It supports the same commands (`RPUSH`, `LRANGE`, `EXPIRE`, `DELETE`, `PING`) as real Redis.

The project uses it because a core constraint (N1) is that everything must run with zero external services — `make test` and `make demo` must work on a laptop with no Docker. When `REDIS_URL` is empty, both the rate limiter (Phase 3) and the conversation scope (Phase 10) automatically fall back to fakeredis through the same `get_redis_client()` function.

---

**Q7: How is analyst ownership enforced? Could analyst A accidentally read analyst B's notes?**

Ownership is enforced at the SQL query level, not in Python after fetching. The `get_all()` function in `memory/scopes/analyst.py` always issues:

```sql
SELECT * FROM memory_records 
WHERE scope = 'analyst' AND owner_id = :analyst_id
```

The `analyst_id` comes from the JWT (`user.user_id or user.sub`). Even if a bug in the API layer passed the wrong ID, the SQL would return an empty result for a different analyst — not a 403, but definitely not analyst B's data.

For the delete operation, `get_one()` also filters on `owner_id`, so `delete(record_id, analyst_id)` returns `False` (not found) if `record_id` belongs to a different analyst. The API converts `False` to a 404.

---

**Q8: Why does `upsert` on analyst and session scopes overwrite by key rather than creating a new record?**

For notes and session facts, the key is the semantic identifier — `"preference.format"` or `"entity.service"`. Creating a new record every time you update "my format preference" would result in duplicate rows with no clear order. Upsert (update if exists, insert if not) keeps exactly one row per key per owner, making reads simple and preventing unbounded table growth.

---

**Q9: The `memory_records` table was created in Phase 2. Why wasn't it used until Phase 10?**

The table was added speculatively to avoid a schema migration later. The convention in this project is that all tables are created at startup from SQLAlchemy models — adding a table later means a migration, which is more disruptive. Phase 2 set up the schema; Phase 10 is the first phase that actually writes to it.

---

**Q10: How would the memory service be extended to support team-level memory?**

Team memory would be a fifth scope with `scope='team'` and `owner_id = team_slug`. The `memory_records` table already supports this — no schema change needed. A new scope module (`memory/scopes/team.py`) would be added, the memory service would expose `get_team_notes()` / `upsert_team_note()`, and the API would add endpoints with RBAC rules (e.g. any team member can read, only the team lead can write).

---

## Architecture questions

**Q11: Where does the memory layer sit in the system's dependency graph?**

The memory layer (`memory/`) sits at the same level as `rag/` and `agents/` — it imports from `app.core` (settings, database) and `app.models`, but nothing in `app.api` or `app.services` imports memory directly. The API layer (`app.api.memory`) is the only entry point from HTTP.

The research workflow (Phase 11/12) will import `memory_service` directly — this is fine because agents are allowed to import from the memory layer.

---

**Q12: What happens to memory if the system is restarted?**

| Scope | Survives restart? | Why |
|---|---|---|
| Organizational | Yes — always | It's a file on disk |
| Conversation | No | Redis/fakeredis is in-memory; TTL is 24h anyway |
| Session | Yes | SQLite/PostgreSQL persists rows |
| Analyst | Yes | SQLite/PostgreSQL persists rows |

This is the correct behaviour: short-lived context is ephemeral; personal and research-run data is durable.

---

**Q13: How does Phase 11 (research agents) use the memory service?**

Phase 11 will call `memory_service.get_session_memory_summary(db, redis, session_id, analyst_id)` at the start of a research run. This returns:
- The fiscal calendar and "last quarter" resolution (used by the query analysis node to interpret time expressions).
- Existing conversation turns (used to maintain multi-turn context).
- Any previously stored session facts (if the run is resuming).
- The analyst's personal notes (preferences fed into the synthesis node).

The workflow will also call `upsert_session_fact()` as it discovers entities and time ranges, building up the session memory incrementally.
