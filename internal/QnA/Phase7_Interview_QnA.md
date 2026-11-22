# Phase 7 — Interview Q&A: Graph RAG

> All possible interview questions from Phase 7 with detailed answers. Covers system design, graph databases, Cypher, security, and testing.

---

## Conceptual / Non-Technical Questions

**Q1: Why does the platform need a knowledge graph? Can't you just use the database or the document search?**

A: The relational database (SQL) stores records in tables and is excellent for exact queries: "give me all incidents in Q3 2026." The document search finds relevant text passages. But neither of these answers relationship questions efficiently.

Consider the question: "Which customers were impacted by the Payments API last quarter?" To answer this from SQL alone, you would need to join the incidents table to the services table, then join to an incident-customer mapping table, then filter by service name and date. That's a multi-table join that becomes complicated quickly.

A knowledge graph makes relationship questions trivially simple: you follow the edges. The path is literally drawn on the graph — Incident → IMPACTED → Customer. This is the core advantage of graph databases: they store relationships as first-class citizens, not as foreign-key joins.

---

**Q2: What is a knowledge graph in simple terms?**

A: A knowledge graph is a mind-map of your enterprise. Every important thing — a team, a service, a customer, an incident, a decision — becomes a dot (node). Every meaningful connection between two things becomes a line (edge) with a label describing what that connection means ("OWNED_BY", "IMPACTED", "ADDRESSES").

You can then answer questions by following the lines: "Start at Payments API, follow the AFFECTED lines to find incidents, then follow the IMPACTED lines from those incidents to find customers."

---

**Q3: What is Cypher and why do we show it to users?**

A: Cypher is the query language for graph databases, specifically Neo4j. It is designed to look like ASCII-art drawings of graph patterns. For example:

```
MATCH (svc:Service {name: 'Payments API'})<-[:AFFECTED]-(inc:Incident)-[:IMPACTED]->(c:Customer)
RETURN svc, inc, c
```

The `<-[:AFFECTED]-` syntax literally represents an arrow pointing from the incident to the service.

We show Cypher to users because one of the platform's core requirements is **transparency** — users should be able to see exactly how an answer was produced. When a question is answered using a graph traversal, showing the Cypher is the equivalent of showing your working in maths. An engineer can look at the Cypher, understand the path that was followed, and verify that it is correct.

---

**Q4: What is the difference between a typed traversal and a free-form Cypher query?**

A: A **typed traversal** is a named, pre-programmed graph walk. We define three of them:
1. `traverse_impacted_customers` — finds customers via Service → Incident → Customer
2. `traverse_owning_teams` — finds teams via Service → Team
3. `traverse_related_decisions` — finds decisions via Decision → Incident

These are **safe by construction**: they cannot go wrong because the path is hardcoded. The LLM never generates the traversal path — it only decides which traversal to call.

A **free-form Cypher query** is submitted by an analyst (a human expert) who wants to explore the graph directly. This is more powerful but potentially dangerous — a user could accidentally (or maliciously) write a query that modifies or deletes data.

We use typed traversals for the AI research workflow and allow free-form Cypher for analyst exploration (with a strict read-only guard).

---

## Technical / System Design Questions

**Q5: How does the GraphStoreService protocol work, and why is it important?**

A: `GraphStoreService` is a Python `Protocol` class (from the `typing` module). A Protocol defines a set of methods that any conforming class must implement, without requiring inheritance. It is Python's way of doing duck typing formally.

```python
@runtime_checkable
class GraphStoreService(Protocol):
    def add_node(self, node: GraphNode) -> None: ...
    def traverse_impacted_customers(self, service_name: str, ...) -> list[Evidence]: ...
    # ... etc.
```

Both `MemoryGraphStore` and `Neo4jGraphStore` implement these methods. The factory function `get_graph_store()` returns whichever one is configured. All callers work with the protocol type — they never import the concrete adapter directly.

**Why important:** You can swap the backing store (from in-memory to Neo4j) with a single change to the `.env` file. No code changes required anywhere else. This satisfies the N3 requirement (replaceable stores) from the PRD.

---

**Q6: How does the in-memory graph store work internally?**

A: It uses three data structures:

1. `_nodes: dict[str, GraphNode]` — maps node_id to the node. O(1) lookup.
2. `_edges: list[GraphEdge]` — ordered list of all edges.
3. `_out: dict[str, list[int]]` — maps source node_id to indices into `_edges`. Used when following out-edges (e.g. Service → Team).
4. `_in: dict[str, list[int]]` — maps target node_id to indices into `_edges`. Used when following in-edges (e.g. find all Incidents that AFFECTED a Service).

Both index tables are maintained on every `add_edge` call. The traversals use `get_neighbors()` which looks up the appropriate index and dereferences into the edge list, then into the node dict.

**Time complexity:** `get_neighbors()` is O(degree) — proportional to the number of edges from/to a node, not the total number of edges.

---

**Q7: Why does the graph traversal for impacted customers need to follow edges in the "in" direction first?**

A: The AFFECTED relationship is defined as `(Incident)-[:AFFECTED]->(Service)`. An incident affects a service, so the edge points from incident to service.

When answering "what incidents affected the Payments API?", we start at the Service node and need to find Incidents pointing *to* it. This requires traversing edges in the **reverse** direction — following in-edges.

If we only had out-edges from Service nodes (following the OWNED_BY relationship), we could not find the incidents efficiently. The separate `_in` index solves this: given a service's node_id, it looks up all edges where this node is the *target*, finds the incidents as sources.

This is a classic trade-off in graph storage: maintaining both forward and backward indices doubles the index size but enables bidirectional traversal in O(degree) time.

---

**Q8: Explain the lazy connection pattern in Neo4jGraphStore.**

A: The Neo4j driver is not created when `Neo4jGraphStore()` is instantiated. It is created only on the first call to any method via `_connect()`. This is called a lazy (or deferred) initialisation pattern.

```python
def _connect(self) -> Any:
    if self._driver is not None:
        return self._driver  # already connected
    # ... open connection ...
    self._driver = driver
    return driver
```

**Why lazy?** If we opened the connection at object construction time, the backend would fail to start if Neo4j is not running. With lazy connection:
- The backend starts successfully even if Neo4j is unavailable
- The health check calls `ping()` which triggers `_connect()` and catches the `ConnectionError`
- The health check returns `"degraded"` instead of crashing
- The backend continues to serve requests using other stores (vector, SQL)
- When Neo4j eventually becomes available, the next operation opens the connection automatically

---

**Q9: How does the read-only Cypher guard work?**

A: It uses a compiled regular expression to scan for write keywords:

```python
_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL)\b",
    re.IGNORECASE,
)
```

The `\b` anchors ensure we match whole words — so a property named `creating_time` would not be a false positive.

`assert_readonly_cypher()` calls this and raises `ValueError` if any write keyword is found. This ValueError propagates to the API layer and becomes a `400 Bad Request` response.

**Limitations of this approach:** Regular expression matching is not a full Cypher parser. A sophisticated attacker could potentially construct a query that bypasses the keyword check while still having side effects (e.g. using CALL with a write procedure). For the in-memory adapter this is not a concern (it has no CALL support). For Neo4j in production, the more robust approach is to use Neo4j's built-in read-only mode (a database setting that prevents any write operations at the protocol level).

---

**Q10: How is graph evidence formatted, and how does it fit into the overall Evidence schema?**

A: Every retrieval path (documents, SQL, graph) returns the same `Evidence` Pydantic model from `backend/app/schemas/common.py`. The `source_type` field discriminates the three cases.

For graph evidence:
- `source_type = "graph"`
- `locator` = a string identifying the graph path, e.g. `"incident-8->customer-1"`
- `content` = a human-readable sentence: "Customer 'Meridian Financial Group' was impacted by incident 'INC-2031' (Payments API complete outage) which affected service 'Payments API'."
- `metadata["cypher"]` = the Cypher query string shown to users
- `metadata["traversal"]` = which traversal was used: `"impacted_customers"` / `"owning_teams"` / `"related_decisions"`

The `id` field starts with `"ev-graph-"` to distinguish it from document evidence (`"ev-"`) and SQL evidence.

**Why one shape?** The synthesis node in the LangGraph workflow processes a flat list of Evidence objects from all three retrieval paths. It assigns numbered citations `[1]`, `[2]`, `[3]` without caring whether the evidence came from a document, a SQL query, or a graph traversal. If we had separate shapes, the synthesis node would need three separate code paths.

---

**Q11: How does the graph seeder build approximately 85 nodes and 260 edges?**

A: The seeder loads 8 JSON files and creates:

**Nodes (85 total):**
- 6 Teams + 8 Services + 10 Customers + 12 Incidents + 8 Decisions + 20 Employees + 6 Projects + 15 Tickets = 85

**Edges (~260 total):**
- 20 Employee→MEMBER_OF→Team
- 8 Service→OWNED_BY→Team
- 12 Incident→AFFECTED→Service
- 46 Incident→IMPACTED→Customer (sum of all impacted_customer_ids arrays)
- 11 Decision→ADDRESSES→Incident
- 6 Project→OWNED_BY→Team
- 15 Ticket→PART_OF→Project
- 15 Ticket→ASSIGNED_TO→Employee
- ~49 Customer→USES→Service (based on customer segment)
- 4 Service→DEPENDS_ON→Service (known architectural dependencies)
- 7 Project→ADDRESSES→Decision
- 12 Incident→INVESTIGATED_BY→Team
- ~10 Decision→APPLIES_TO→Service
- 15 Employee→WORKS_ON→Project
- 4 Team→COORDINATES_WITH→Team

Total ≈ 234–260 edges, depending on the exact service assignments.

---

**Q12: What happens when Neo4j is unavailable during a research run?**

A: The research workflow is designed to continue even when a retrieval store fails. The workflow degrade path:

1. The routing node decides a sub-question needs graph retrieval
2. The graph retrieval node calls `traverse_impacted_customers()` on the `Neo4jGraphStore`
3. `_connect()` raises `ConnectionError`
4. The retrieval node catches the exception and records an error on that sub-question
5. The sub-question is marked as `strategy=graph, error="Cannot connect to Neo4j"`
6. The workflow continues to the `collect_evidence` node with the graph evidence missing
7. The `check_missing_evidence` node may trigger a corrective retrieval round using the vector store
8. The final answer is produced from document and SQL evidence, with a note that graph results were unavailable

**Health endpoint** simultaneously shows `graph_store: degraded` so operators know the graph is down.

---

## Testing Questions

**Q13: How do you test typed graph traversals without a real Neo4j database?**

A: By using the `MemoryGraphStore` which is a fully functional, in-process graph store. The test fixture `tiny_store` manually builds a minimal five-node graph with exactly the nodes and edges needed to test each traversal:

```python
@pytest.fixture
def tiny_store() -> MemoryGraphStore:
    store = MemoryGraphStore()
    store.add_node(GraphNode("team-1", "Team", {"name": "Payments Platform"}))
    store.add_node(GraphNode("svc-1", "Service", {"name": "Payments API"}))
    store.add_node(GraphNode("inc-1", "Incident", {"incident_id": "INC-2031", ...}))
    store.add_node(GraphNode("cust-1", "Customer", {"name": "Meridian Financial Group"}))
    store.add_node(GraphNode("dec-1", "Decision", {"adr_id": "ADR-001", ...}))
    # add edges ...
    return store
```

This is better than seeding the full 85-node graph for unit tests because:
1. It is explicit — the test knows exactly what data exists
2. It is fast — no file I/O
3. It is isolated — no other tests' graph data can interfere

The `seeded_store` fixture is used only for integration-level tests that verify the full dataset (e.g. that INC-2031 has exactly 5 impacted customers in the real data).

---

**Q14: How do you test the degraded readiness behaviour without taking Neo4j down?**

A: By registering a custom health check that simulates the `ConnectionError`:

```python
def test_degraded_readiness_when_neo4j_connection_error() -> None:
    def _failing_check() -> dict[str, str]:
        raise ConnectionError("Cannot connect to Neo4j...")

    def _safe_check() -> dict[str, str]:
        try:
            return _failing_check()
        except ConnectionError as exc:
            return {"status": "degraded", "detail": str(exc)}

    register_check("graph_store_neo4j_test", _safe_check)
    checks, overall = run_all_checks()
    assert checks["graph_store_neo4j_test"]["status"] == "degraded"
```

This tests the exact logic that `register_graph_store_check()` uses, without needing a real Neo4j instance.

---

**Q15: How many tests does Phase 7 add, and what do they prove?**

A: Phase 7 adds 40 tests in `tests/rag/test_graph_traversals.py`. Together with the 162 existing tests, the total is 202 tests.

The 40 tests cover:
- **Store unit tests (8):** add/count nodes, add/count edges, get_node, upsert, get_neighbors (in and out), clear
- **Typed traversals (10):** owning teams, impacted customers (with and without date filter), related decisions, empty results, unique IDs, score range
- **Seeded graph integration (6):** node count ≈85, edge count ≈260, real data traversals (Payments API team, INC-2031 customers, INC-2031 decisions), all required relationship types present
- **Read-only Cypher (10):** accepts MATCH/RETURN/WHERE/WITH; rejects CREATE/MERGE/DELETE/DETACH/SET/REMOVE/DROP; case-insensitive; ValueError on write
- **execute_cypher_readonly (3):** returns rows for valid MATCH, rejects write statements, filters by label property
- **Health checks (2):** registration, counts in detail string
- **Degraded readiness (1):** ConnectionError → degraded status

---

## Architecture Philosophy Questions

**Q16: Why are the traversals deterministic (pre-programmed) rather than letting the LLM write Cypher?**

A: This is one of the most important design decisions in the platform. There are three reasons:

1. **Correctness under LLM_PROVIDER=fake.** The offline demo and all tests run with a fake LLM that returns deterministic dummy responses. If the graph traversal path were generated by the LLM, it would not work in fake mode. By making traversals deterministic, the entire platform works without any real AI model.

2. **Safety.** An LLM-generated Cypher could contain write operations (even accidentally). The read-only guard catches these, but a pre-programmed traversal never generates write operations in the first place.

3. **Reliability.** Relationship questions need relationships. The rules in `agents/rules.py` enforce this: a question that needs relationships is *never* routed to vector-only retrieval, whatever the LLM says. Similarly, a relationship traversal is never generated incorrectly by the LLM — the path is always correct.

The philosophy is: **LLM proposes, rules correct**. The LLM helps with language understanding, but deterministic code controls all structural decisions.

---

**Q17: How does the graph store fit into the layering rules of the project?**

A: The layering rules state: `api → services → repositories → models` for the backend, and `agents / rag / memory → app.core` for the AI pipeline. `core/` is the bottom layer and never imports from `agents/` or `rag/`.

The graph store sits in `rag/` — the retrieval layer. This means:
- The graph store can import from `app.core` (settings, health, schemas) ✓
- The graph store cannot import from `app.api` or `app.services` ✓
- Research agents in `agents/` can call graph traversals ✓
- The API layer in `app.api/` does not call graph traversals directly (it calls services, which call agents) ✓

The `register_graph_store_check()` function is called once during the FastAPI lifespan (`app.main`), which is in the `app` package. This is the only deliberate coupling point: the main application bootstraps the health check at startup. All subsequent calls to the graph store go through the protocol.
