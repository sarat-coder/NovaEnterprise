# Frontend Assumptions — NovaEnterprise

> Guarantees the backend makes to the frontend beyond the basic API contract.
> If any of these change, update the frontend types **and** this file in the same commit.
> Source of truth: `docs/API_CONTRACT.md` · Graph shape test: `test_graph_shape_matches_frontend_assumptions`

---

## 1. Research workflow — node IDs

The 13 LangGraph nodes are identified by these exact string IDs. The frontend uses them to label
the event timeline and render the step-by-step progress view.

| Order | Node ID | Display label |
|-------|---------|---------------|
| 1  | `analyze_query`          | Analysing question |
| 2  | `assess_complexity`      | Assessing complexity |
| 3  | `decompose`              | Decomposing into sub-questions |
| 4  | `route_retrieval`        | Routing retrieval |
| 5  | `vector_retrieval`       | Vector / semantic search |
| 6  | `sql_retrieval`          | SQL records lookup |
| 7  | `graph_retrieval`        | Graph traversal |
| 8  | `hybrid_retrieval`       | Hybrid retrieval |
| 9  | `collect_evidence`       | Collecting evidence |
| 10 | `check_missing_evidence` | Checking for gaps |
| 11 | `corrective_retrieval`   | Corrective retrieval |
| 12 | `verify_evidence`        | Verifying evidence |
| 13 | `synthesize_answer`      | Synthesising answer |
| 14 | `verify_citations`       | Verifying citations |

> Node IDs 5–8 may appear multiple times (once per sub-question). The frontend should
> group events by their `node` field and render them in `occurred_at` order.

---

## 2. Polling guarantees

- `POST /api/v1/research` always returns **202** immediately (never waits for the run).
- The session `status` field transitions: `running` → `completed` | `error`. It never goes backwards.
- `GET /api/v1/research/{id}` returns the most recent persisted state; partial results are valid
  (sub-questions may be completed before the answer is ready).
- The frontend polls every **2 seconds**. The backend guarantees state is persisted **after every
  node transition**, so the frontend never misses a step.
- When `status == "completed"` or `status == "error"`, the frontend stops polling.

---

## 3. Sub-question strategies

Each sub-question carries a `strategy` field. Valid values:

| Value    | Meaning |
|----------|---------|
| `vector` | Semantic + BM25 retrieval from the document store |
| `sql`    | Structured records from the SQL database |
| `graph`  | Graph traversal (Cypher) |
| `hybrid` | Combination of vector + graph (or all three) |

---

## 4. Evidence — unified shape

All evidence items in `GET /api/v1/research/{id}` share the same schema regardless of origin:

```json
{
  "id":          "e1",
  "source_type": "document|sql|graph",
  "locator":     "<chunk_id|query_id|traversal_id>",
  "content":     "Human-readable fragment",
  "score":       0.95,
  "metadata":    {}
}
```

Citation markers in the answer (`[1]`, `[2]`, …) resolve to these `id` values.
Every `[n]` in the answer **must** match an `id` in the evidence array — the backend guarantees this.

---

## 5. Memory scopes

The four memory scopes surfaced per session are always present in `GET /api/v1/research/{id}`:

| Key | Scope |
|-----|-------|
| `organizational` | Shared company facts (fiscal calendar, policies) |
| `conversation`   | Redis-backed conversation context |
| `session`        | Ephemeral facts from this research run |
| `user`           | Analyst-owned personal notes |

Scopes may be empty objects `{}` before memory is populated.

---

## 6. Graph node types

Nodes returned by `GET /api/v1/graph/nodes` have one of these `type` values:

`Service` | `Team` | `Incident` | `Customer` | `Decision` | `Employee` | `Project`

---

## 7. Health degraded behaviour

When `/health/ready` returns `"status": "degraded"` (typically because Neo4j or Qdrant is
unavailable), the frontend should:
- Show a subtle warning banner, not a full error page.
- Still allow research on sub-questions routed to available stores.
- Sub-questions routed to the degraded store will complete with `status: "error"` and an
  `error_detail` field; the rest of the answer is still valid.

---

## 8. Rate limit

When the backend returns **429**, the frontend should back off for 60 seconds before retrying.
The `X-Request-ID` on the 429 response can be shown in the error UI for support tracing.

---

## 9. Request ID tracing

Every request the frontend makes should include an `X-Request-ID` header when it already has one
(e.g., from a previous response). The backend echoes it back unchanged. If the frontend does not
send one, the backend generates a UUID and returns it. The frontend should log this id alongside
any error it shows the user.
