# Phase 7 — Graph RAG: Plain-English Explanation

> Written for non-technical audiences: recruiters, interviewers, and business stakeholders.

---

## What we built in Phase 7

In Phase 7 we gave the platform the ability to **answer questions using relationships between things** — not just documents or database rows.

Before this phase, the platform could search through written documents (Phase 6) and query structured database tables. But some of the most important questions in an enterprise are about *connections*: "Which customers were affected by this outage?" or "Who owns that service?" Those answers live in the **relationships** between things — not in a single row or a single document.

Phase 7 adds a **Knowledge Graph** to the platform. A knowledge graph is like a mind-map of your entire organisation: every team, service, incident, customer, decision, and employee becomes a **dot** (node), and every connection between them becomes a **line** (edge) labelled with what that connection means — like "OWNED_BY" or "IMPACTED".

---

## Why a knowledge graph? The classic example

The canonical question this platform answers is:

> "Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams own those services, and what decisions were taken to prevent recurrence?"

Let's trace how that is impossible to answer from a single data source:

| Part of the question | How the graph answers it |
|---|---|
| Which customers were impacted? | Follow the line: Incident → IMPACTED → Customer |
| What incidents occurred? | Find all Incidents that have an AFFECTED line to the Payments API service |
| Which team owns the Payments API? | Follow the line: Payments API → OWNED_BY → Payments Platform team |
| What decisions prevent recurrence? | Follow the line: Decision → ADDRESSES → Incident |

A graph makes multi-hop questions like this **simple, fast, and reliable**.

---

## The four things we built

### 1. The GraphStoreService Protocol (The Blueprint)

Just like in Phase 6 we defined what a "document search engine" must be able to do, in Phase 7 we defined what a "graph database" must be able to do.

This blueprint lists the operations every graph store must support:
- Add a node (a thing) or an edge (a connection)
- Find a node by its id
- Find the neighbours of a node (what is connected to it)
- Run the three key traversals: find impacted customers, find the owning team, find related decisions
- Execute a user-entered graph query (safely)

**Why this matters:** The platform can swap between an in-memory graph (for demos and tests) and a full Neo4j database (for production) without changing any other code. This is the same "plug-and-play" principle used for the vector store in Phase 6.

---

### 2. The In-Memory Graph (Works With Zero Setup)

We built a **pure-Python graph engine** that runs entirely in RAM — no database needed.

It stores all nodes in a dictionary and all edges in a list, with two index tables to look up connections quickly. The entire graph for the NovaEnterprise demo — 85 nodes and over 260 edges — lives comfortably in memory and answers traversal queries in milliseconds.

This is what powers `make test` and the offline demo. No internet, no cloud service, no Docker.

**Analogy:** Think of it as a hand-drawn map. You can still answer "how do I get from A to B?" by following the lines. It's not as fast or as powerful as a GPS system, but for demos and tests it is more than enough.

---

### 3. Typed Traversals — The Three Smart Queries

Instead of letting users write any graph query they want (which could be unsafe or wrong), we built **three named traversals** that are correct by construction:

#### Traversal 1: "Who was impacted by this service's incidents?"

```
(Service) ← [:AFFECTED] ← (Incident) → [:IMPACTED] → (Customer)
```

You say: "Show me customers impacted by the Payments API last quarter."
The system follows two hops: finds every incident that affected the Payments API, then finds every customer that incident impacted.

Result for the canonical question: 5 enterprise customers — Meridian Financial Group, Apex Retail Corp, NovaTech Solutions, Sunrise Healthcare, and Coastal Logistics.

#### Traversal 2: "Which team owns this service?"

```
(Service) → [:OWNED_BY] → (Team)
```

You say: "Who owns the Payments API?"
One hop: the Payments Platform team.

#### Traversal 3: "What decisions were made about this incident?"

```
(Decision) → [:ADDRESSES] → (Incident)
```

You say: "What decisions came out of INC-2031?"
Result: ADR-001 (adopt circuit-breaker) and ADR-002 (require contract testing).

**What makes these special:** Every traversal also returns its **Cypher** — the graph query language statement that represents the path it followed. This is the "show your work" feature. Analysts and engineers can see exactly what graph query produced the answer, just like a person showing their working in maths.

---

### 4. The Neo4j Adapter (Production-Ready)

For production deployments, we built a connector to **Neo4j** — the world's most popular graph database. When a real Neo4j instance is configured (via `GRAPH_STORE=neo4j` in the settings), the platform uses Neo4j's full power for terabyte-scale graphs.

**Fail gracefully:** If Neo4j is unreachable (network issue, not yet started), the platform does not crash. Instead:
- The health check endpoint (`/health/ready`) reports `graph_store: degraded` instead of `ok`
- Graph sub-questions in the research workflow record an error on that sub-question only
- The rest of the workflow (document search, SQL retrieval) continues normally
- The final answer is still produced, with a note that graph results were unavailable

This is the "degrade, don't crash" principle.

---

### 5. The Read-Only Cypher Guard

Analysts can submit their own graph queries. But graph databases can delete data — a rogue or mistaken query could destroy the entire knowledge graph.

We built a **read-only guard** that checks every user-submitted query before it runs:

| Blocked keywords | What they do |
|---|---|
| `CREATE` | Create new nodes |
| `MERGE` | Create if not exists |
| `DELETE` / `DETACH DELETE` | Delete nodes or relationships |
| `SET` | Modify properties |
| `REMOVE` | Remove properties or labels |
| `DROP` | Drop indexes or constraints |

If any of these appear in a query, it is **immediately rejected** with a clear error message. Analysts can only read the graph — they can never modify it.

---

### 6. The Graph Seeder (`make seed-graph`)

We built a script that reads all the sample data JSON files and builds the full NovaEnterprise knowledge graph:

| Node type | Count | Examples |
|---|---|---|
| Teams | 6 | Payments Platform, SRE, Identity |
| Services | 8 | Payments API, Billing Engine |
| Customers | 10 | Meridian Financial, Apex Retail |
| Incidents | 12 | INC-2031 (the SEV1) |
| Decisions | 8 | ADR-001 through ADR-008 |
| Employees | 20 | Alice Chen, Eva Kowalski |
| Projects | 6 | Payments API v4 Migration |
| Tickets | 15 | PAY-101 through SRE-602 |

**Total: 85 nodes, ≈260 edges**

The edges include all the required relationship types plus many more natural connections (employees working on projects, customers using services, services depending on other services).

---

## How the pieces connect

```
Your question: "Which customers were impacted by Payments API last quarter?"
     │
     ▼
Research Agent  →  chooses "graph" strategy
     │
     ▼
Typed Traversal: traverse_impacted_customers("Payments API", start="2026-07-01", end="2026-09-30")
     │
     ▼
MemoryGraphStore  (or Neo4j in production)
     │
     ├── Service(Payments API) ← AFFECTED ← Incident(INC-2031) → IMPACTED → Customer(Meridian)
     ├── Service(Payments API) ← AFFECTED ← Incident(INC-2031) → IMPACTED → Customer(Apex Retail)
     ├── ... (5 customers in total)
     │
     ▼
Evidence list  →  with Cypher shown:
  "MATCH (svc:Service {name: 'Payments API'})<-[:AFFECTED]-(inc:Incident)
   -[:IMPACTED]->(c:Customer)
   WHERE inc.started_at >= '2026-07-01' AND inc.started_at <= '2026-09-30'
   RETURN svc, inc, c"
```

---

## What stays the same no matter what

- The store can be swapped (in-memory ↔ Neo4j) without changing any other code.
- Every traversal returns the same `Evidence` shape as SQL and document retrieval — one numbered citation list.
- Analysts can explore the graph freely, but write operations are always blocked.
- If Neo4j is unavailable, the system degrades gracefully rather than crashing.
- All 202 tests pass offline — no internet, no API key, no cloud service needed.
- Lint is clean (`ruff check` and `ruff format`).

---

## In one sentence

Phase 7 gives the platform a **knowledge graph engine** that maps relationships between every team, service, incident, customer, and decision in the company — and can answer multi-hop questions like "who was impacted, who owns it, and what did we decide?" in a single traversal, with the graph query shown as evidence.
