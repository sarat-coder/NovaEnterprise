# Phase 8 — SQL Retrieval: Plain-English Explanation

> Written for non-technical audiences: recruiters, interviewers, and business stakeholders.

---

## What we built in Phase 8

In Phase 8 we gave the platform the ability to **answer questions using the company's structured database** — the kind of data that lives in spreadsheet-like tables with rows and columns.

Before this phase, the platform could already search through written documents (Phase 6) and follow relationships in a knowledge graph (Phase 7). But some business questions need **exact numbers and records** — "Show me every incident that happened to the Payments API between July and September." That answer lives in a database table, not in a document and not in a graph.

Phase 8 adds a **safe, controlled SQL retrieval layer** to the platform. SQL (Structured Query Language) is the standard way to ask questions of a database. The key word is *safe*: we built a strict security gate that sits between the AI agent and the database, making sure the AI can only *read* data — never change, delete, or corrupt it.

---

## Why is safety such a big deal here?

Imagine giving an AI assistant the keys to a room full of financial records with no rules. It could accidentally — or through a malicious instruction — delete all the records, or leak confidential data.

We prevent this with three interlocking mechanisms:

1. **A SQL validator** — a gate that inspects every database query before it runs and blocks anything dangerous.
2. **Pre-written safe templates** — a set of approved, pre-tested query patterns that cover the most common questions.
3. **A query recorder** — every query that runs is logged with a unique ID, so there is a complete audit trail.

Together these three mechanisms ensure the platform can answer data questions without ever being a threat to the data it reads.

---

## The three things we built

### 1. The SQL Validator — The Security Gate

The validator is like a bouncer at a door. Before any database query is allowed to run, the bouncer checks it against a strict rulebook. If the query breaks any rule, it is blocked immediately with a clear error message.

**The seven rules:**

| Rule | What it blocks | Example of blocked query |
|---|---|---|
| Must not be empty | Blank or whitespace-only input | ` ` (empty) |
| No inline comments | A trick used to hide extra instructions | `SELECT * FROM incidents -- ignore this part` |
| No block comments | Another comment trick | `SELECT /* inject here */ * FROM incidents` |
| No semicolons | Separating two statements in one call | `SELECT 1; DROP TABLE incidents` |
| Must start with SELECT | Any non-read operation | `INSERT INTO incidents ...` |
| No forbidden keywords | DDL and DML (data-changing commands) | `DROP TABLE`, `DELETE`, `UPDATE`, `CREATE` |
| Only allowed tables | Prevents access to hidden or sensitive tables | `SELECT * FROM secret_credentials` |

If a query passes all seven rules, the validator returns it and execution proceeds. If it fails any rule, the query is immediately rejected — it never touches the database.

**Analogy:** Think of it like an airport security scanner. No matter what you are carrying, it has to go through the scanner. If the scanner flags something, you do not pass. The database is the secure area — only validated queries get through.

---

### 2. SQL Query Templates — The Pre-Approved Questions

Instead of letting the AI write any query it wants (which could be risky or just wrong), we wrote five **pre-approved query templates** that cover the most common research questions:

| Template name | What it answers |
|---|---|
| `incidents_by_service_and_date` | "Show me all incidents for the Payments API between two dates" |
| `incidents_by_service` | "Show me all incidents for a given service (no date filter)" |
| `decisions_for_incident` | "What decisions were made in response to incident INC-2031?" |
| `customers_impacted_by_incident` | "Which customers were affected by a specific incident?" |
| `services_owned_by_team` | "Which services does the Payments Platform team own?" |

Each template has named **slots** (like `{service_name}` or `{start_date}`) that the AI fills in at run time. The template SQL itself is fixed and was validated when the system started up — it is never changed by the AI.

**Analogy:** Think of a template as a form letter. The structure and the legal language are fixed; only the addressee's name and date change. You cannot accidentally introduce dangerous language by filling in the form.

---

### 3. The SQL Retriever — The Query Runner and Evidence Producer

The retriever is the component that ties everything together. When the AI agent needs to answer a data question, it calls the retriever with:
- the template name it wants to use, and
- the specific values to fill into the template (e.g. service name = "Payments API", start date = "2026-07-01").

The retriever then:

1. **Looks up** the template.
2. **Validates** the SQL (even though it was already validated at startup — a second check is a safety habit).
3. **Executes** the query against the database.
4. **Records** the query with a universally unique ID (UUID) and a timestamp — this is the audit trail.
5. **Returns** the results as a list of **Evidence** items — the same unified shape that document search and graph traversal also return.

This last point is crucial: by wrapping database rows in the same `Evidence` format as document chunks and graph paths, the AI agent can combine all three in one numbered citation list. A single answer can cite `[1]` from a document, `[2]` from a database row, and `[3]` from a graph traversal — all in one response.

---

## How the pieces connect for the canonical question

The platform's main test question is:

> "Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams own those services, and what decisions were taken to prevent recurrence?"

The SQL retrieval part answers the second sub-question: **"what incidents occurred?"**

```
Research agent receives question
     │
     ▼
Routing node decides → "this needs SQL"
     │
     ▼
SQL Retriever called with:
  template = "incidents_by_service_and_date"
  params   = { service_name: "Payments API",
               start_date:   "2026-07-01",
               end_date:     "2026-09-30" }
     │
     ▼
Validator checks the SQL → passes all 7 rules
     │
     ▼
Database executes: finds INC-2031 and INC-2044
     │
     ▼
Query recorded with UUID (e.g. "query-abc-123")
     │
     ▼
Two Evidence items returned:
  Evidence(id="sql-abc-123-0", source_type="sql",
           content="incident_id: INC-2031 | title: Payments API Outage | severity: SEV1 ...")
  Evidence(id="sql-abc-123-1", source_type="sql",
           content="incident_id: INC-2044 | title: Payment Processing Delay | severity: SEV2 ...")
     │
     ▼
Agent includes these as citations [2] and [3] in the final answer
```

The analyst looking at the answer can click through to see exactly which SQL query produced that result — the query text, the parameters, the timestamp. Full transparency.

---

## What stays the same no matter what

- The validator runs on **every** query, without exception — templates and analyst-written queries alike.
- The database is **read-only** from the AI's perspective. No write, delete, or structural change is possible through the research workflow.
- Every query result is wrapped in the **same Evidence shape** as documents and graph traversals — one unified citation list.
- All 210 tests pass with **no API key and no database server** — the system uses a lightweight SQLite file and an in-memory fake path for offline testing.
- Lint is clean (`ruff check` and `ruff format`).

---

## In one sentence

Phase 8 gives the platform a **safe, auditable SQL retrieval layer** that lets the AI read exact records from the company database — with a strict validator that blocks all data-modifying operations and a query recorder that keeps a full audit trail of every query that ran.
