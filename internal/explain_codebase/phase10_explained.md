# Phase 10 — Memory: Plain-Language Explanation

## What problem are we solving?

Imagine you are a research analyst at a company. Every time you start a new conversation with a colleague, you bring different kinds of knowledge to the table:

1. **Company-wide facts** — things like "our fiscal year runs January to December" or "a Severity-1 incident requires a 5-minute response." Everyone in the company knows these; they don't change per conversation.
2. **Conversation history** — what you said to that colleague earlier in the same meeting. If you already established "we're talking about last quarter," you don't need to explain it again.
3. **Notes from this research session** — things you discovered during this specific investigation, like "the Payments API was the affected service" or "the incident started in Q3."
4. **Your personal notes** — shortcuts, preferences, or reminders that only you use, like "I prefer concise bullet-point answers."

Phase 10 gives our AI research assistant exactly these four kinds of memory. Without them, the assistant would forget everything between turns and couldn't personalise its behaviour for different analysts.

---

## The four memory scopes — explained simply

| Scope | Think of it as | Lives where | Who can change it |
|---|---|---|---|
| **Organizational** | The company handbook (read-only) | A JSON file on disk | Nobody at runtime — it's fixed |
| **Conversation** | The notepad for this meeting | Redis (an in-memory store) | Automatically, as turns happen |
| **Session** | The whiteboard for this research run | The database | The research workflow |
| **Analyst** | Your personal sticky notes | The database | Only you |

---

## Scope 1 — Organizational memory

This scope loads a file called `organizational_memory.json` that contains company-wide facts:

- **Fiscal calendar** — "Q1 is January–March, Q2 is April–June, …" This is crucial for answering questions like "What happened last quarter?" The system automatically resolves "last quarter" to concrete start and end dates.
- **SLA definitions** — what does Tier-1 availability mean? What is the response time for a Severity-2 incident?
- **Severity definitions** — what qualifies as a SEV1 vs SEV3 incident?
- **Data retention policy** — how long do we keep audit logs, research sessions, uploaded documents?
- **On-call contacts** — who to email in an emergency.

**Example**: If today is November 2026, the system resolves "last quarter" → Q3 2026 → July 1 to September 30. This exact date range is then used to query the database for incidents.

This scope is **read-only** — no one can change it without editing the file. It's like a company handbook that is published once and consulted frequently.

---

## Scope 2 — Conversation memory

Every research session has a unique ID. As the user and the assistant exchange messages, those turns are stored in **Redis** — a very fast in-memory store (think of it like a whiteboard that's easy to erase).

- When the user asks a question → stored as `{role: "user", content: "What happened?", timestamp: "..."}`
- When the assistant answers → stored as `{role: "assistant", content: "Here is the summary...", timestamp: "..."}`

This lets the assistant remember context from earlier in the same session. The turns automatically expire after 24 hours so old sessions don't clog up the system.

**Offline mode**: When no Redis server is running (the default for development), the system uses `fakeredis` — a Python library that behaves exactly like Redis but runs entirely in memory. No external service needed.

---

## Scope 3 — Session memory

While the research workflow runs (the AI is thinking, querying databases, traversing the graph), it discovers useful facts:

- "The service being asked about is **Payments API**"
- "The time range is **Q3 2026**"
- "The affected customers are **Acme Corp, Globex**"

These facts are stored in the database (in the `memory_records` table, tagged with `scope='session'` and the session's ID). They're separate from the evidence the assistant collects — they're more like **working notes** that help the workflow stay consistent across multiple steps.

When the session ends, these notes remain in the database for transparency but are no longer used.

---

## Scope 4 — Analyst memory

Each analyst (a logged-in user with the "analyst" role) has their own private notebook. They can:

- **Store** a personal note: "I prefer concise bullet-point answers"
- **Read** their own notes: they always appear in their research sessions
- **Delete** a note when it's no longer useful

**Ownership is strictly enforced**: Alice cannot see Bob's notes, and Bob cannot delete Alice's notes. The system checks ownership on every read and write operation.

---

## Why is memory never mixed with retrieval?

The research assistant answers questions by collecting **evidence** — quotes from documents, rows from the database, paths through the knowledge graph. Each evidence item gets a citation number like `[3]`.

Memory facts are **context** (things that help the assistant reason) but they are **not sources** that can be cited in an answer. Mixing them would be like citing "my personal preference for bullet points" as a source for a factual claim — it doesn't belong there.

The system enforces this separation: memory never enters the evidence collection pipeline and never gets a citation number.

---

## What does the analyst see?

When an analyst starts a research session, they can see a **memory panel** that shows all four scopes at once:

```
Organizational memory:
  Fiscal calendar: Q4 (Oct–Dec), last quarter = Q3 (Jul–Sep 2026)
  Data retention: audit logs 5 years, research sessions 90 days

Conversation (this session):
  [user]      "Which customers were impacted by the Payments API last quarter?"
  [assistant] "Let me look that up..."

Session facts:
  entity.service  → Payments API
  time_range      → 2026-07-01 to 2026-09-30

My notes (analyst personal):
  preference.format → bullet_points
```

---

## API endpoints added in Phase 10

| Endpoint | Who can use it | What it does |
|---|---|---|
| `GET /api/v1/memory/organizational` | Anyone logged in | Returns the full company handbook |
| `GET /api/v1/memory/organizational/quarter` | Anyone logged in | Returns "last quarter" as concrete start/end dates |
| `GET /api/v1/memory/notes` | Analysts and admins | Lists the calling analyst's personal notes |
| `POST /api/v1/memory/notes` | Analysts and admins | Adds or updates a personal note (upsert by key) |
| `DELETE /api/v1/memory/notes/{id}` | Analysts and admins | Deletes one of the calling analyst's notes |

A **viewer** trying to access analyst notes gets a **403 Forbidden** error.

---

## End-to-end example: "What happened last quarter?"

1. Analyst asks the question.
2. The system calls `resolve_last_quarter()` → returns `{quarter: "Q3", start_date: "2026-07-01", end_date: "2026-09-30"}`.
3. This date range is passed to the SQL retriever, which queries for incidents between those dates.
4. The result is real data — not a vague "Q3" string — because the fiscal calendar defined it precisely.
5. The analyst also sees their personal note "preference.format → bullet_points" and the assistant uses it to format the answer.

---

## Summary of files created in Phase 10

| File | What it does |
|---|---|
| `memory/scopes/organizational.py` | Loads `organizational_memory.json`; resolves quarter labels to dates |
| `memory/scopes/conversation.py` | Stores/reads per-session turns in Redis (fakeredis offline) |
| `memory/scopes/session.py` | Stores/reads per-research-run working notes in the database |
| `memory/scopes/analyst.py` | Stores/reads/deletes personal analyst notes with ownership enforcement |
| `memory/memory_service.py` | Unified interface combining all four scopes; provides `get_session_memory_summary()` |
| `backend/app/api/memory.py` | HTTP endpoints for organizational memory and analyst notes |
| `backend/app/schemas/memory.py` | Pydantic data shapes for the memory API responses |
| `tests/unit/test_memory_scopes.py` | 19 unit tests covering all scope logic and ownership rules |
| `tests/api/test_memory_api.py` | 10 API tests covering auth, RBAC, CRUD |
