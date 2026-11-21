# Phase 2 — Interview Q&A

> All possible interview questions and detailed answers covering Phase 2: Persistence and Sample Data.
> Topics: SQLAlchemy ORM, Evidence schema design, repository pattern, seed service, RLS, sample data.

---

## Section 1: Database and ORM

**Q: Why did you choose SQLAlchemy over a simpler library like SQLite3 directly?**

A: SQLAlchemy gives us two things we need: a type-safe ORM that maps Python classes to tables (so we never write raw INSERT statements in business logic), and database-agnostic query building that lets the same code work against SQLite in development and Postgres in production. Writing raw `sqlite3` queries would have tied us to SQLite forever and made production migration much harder. SQLAlchemy 2's `Mapped[]` type annotations also give us full IDE type checking on model attributes.

---

**Q: What is a DeclarativeBase and why does every model inherit from it?**

A: `DeclarativeBase` is SQLAlchemy's mechanism for linking a Python class to a database table. When you subclass `Base` (which extends `DeclarativeBase`), SQLAlchemy registers the class in `Base.metadata`. When we call `Base.metadata.create_all(engine)`, SQLAlchemy reads every registered class and generates the CREATE TABLE statements. Without the shared `Base`, the metadata would be incomplete and tables would be missing.

---

**Q: What is `lru_cache` on `get_engine()` and why is it important?**

A: `lru_cache(maxsize=1)` means the first call to `get_engine()` creates the engine and caches it. Every subsequent call returns the cached engine. This is critical because SQLAlchemy engines manage a **connection pool** — a set of persistent connections to the database. If you create a new engine on every request, each one would spin up its own pool, exhausting database connections quickly. With `lru_cache`, the entire application shares one pool.

---

**Q: What is WAL mode in SQLite and why did you enable it?**

A: WAL (Write-Ahead Log) is an alternative journaling mode for SQLite that allows **concurrent reads while a write is happening**. In the default journal mode, a write locks the entire file, so a read during a write has to wait. WAL mode separates the write log from the main file, allowing readers to continue against the last committed state while a write is in progress. For a web application with multiple async requests, WAL mode significantly reduces contention.

---

**Q: How does the `get_db()` generator work in FastAPI dependency injection?**

A: `get_db()` is a Python generator that follows the `yield` pattern:
1. Before `yield`: create a session from the session factory.
2. `yield session`: hand the session to the route handler.
3. After `yield` (success): `session.commit()`.
4. After `yield` (exception): `session.rollback()`.
5. `finally`: `session.close()` (always).

FastAPI's `Depends(get_db)` calls this generator for each request and handles the teardown automatically. This ensures every request has a clean session, and sessions are never leaked.

---

**Q: Why not use `async` sessions with `AsyncSession` from SQLAlchemy?**

A: SQLite has poor support for async I/O (it doesn't have an async driver that works well). Using sync sessions with SQLite and async sessions with Postgres would require different code paths. For Phase 2, the simpler synchronous path was chosen — it works correctly with FastAPI's `BackgroundTasks` (which runs synchronously). If we move to Postgres in production, we can add `AsyncSession` with `asyncpg` as an enhancement without changing the repository interface.

---

## Section 2: The Evidence Schema

**Q: What problem does the `Evidence` schema solve?**

A: The research engine retrieves information from three completely different sources: a vector store (document chunks), a SQL database (structured records), and a knowledge graph (relationships). Each source returns data in a different format. When synthesising an answer with citations like `[1] from the postmortem, [2] from the incidents database, [3] from the graph`, you need every piece of evidence to have the same shape. The `Evidence` Pydantic model provides that universal shape, with `source_type` telling you where it came from and `locator` telling you exactly where to find the original source.

---

**Q: What are the three `source_type` values and what does `locator` mean for each?**

A: 
- `document`: The locator is a chunk UUID pointing to a row in `document_chunks`. The evidence comes from a semantic or keyword search over indexed document text.
- `sql`: The locator is a query UUID pointing to a recorded SQL query. The evidence comes from a structured database query (e.g., "incidents for Payments API in Q3 2026").
- `graph`: The locator is a traversal UUID or a Cypher expression label. The evidence comes from a graph traversal (e.g., "customers impacted by incident INC-2031").

---

**Q: Why is `score` constrained to `[0.0, 1.0]`?**

A: Scores from different retrieval systems are on different scales: vector similarity is typically cosine similarity (0 to 1), BM25 is a raw TF-IDF score (unbounded), and graph traversals have no inherent score. By normalising all scores to [0.0, 1.0] on the `Evidence` object, the evidence merging and ranking steps can compare evidence from different sources fairly without needing to know the retrieval method.

---

**Q: Why is `metadata` a free-form dict rather than typed fields?**

A: Different evidence types carry different metadata. A document evidence item might carry `{"page": 3, "section": "Executive Summary"}`. A SQL evidence item might carry `{"table": "incidents", "rows": 2}`. A graph evidence item might carry `{"cypher": "MATCH (i:Incident)...", "nodes_returned": 5}`. Using a typed Pydantic model for each type would require three separate Evidence classes and complicate the merging logic. A `dict[str, Any]` is the right tradeoff: flexible metadata, still validated as a dict, and always serialisable to JSON.

---

## Section 3: Repository Pattern

**Q: What is the repository pattern and why did you use it?**

A: The repository pattern wraps all data access for a domain entity behind an interface. Instead of writing `SELECT * FROM incidents WHERE service_id = ?` in multiple places (the agent node, the API handler, the seed service), you have one `IncidentRepository.get_by_service()` method. Benefits:
1. **Testability**: you can mock a repository and test the business logic without a database.
2. **Single point of change**: if the query needs optimising, you change one method.
3. **Layering enforcement**: CLAUDE.md §4.2 says agents must never import repositories — they receive data from services. The pattern makes this boundary explicit.

---

**Q: Why is `IncidentRepository.get_by_service_and_date_range()` important for the canonical question?**

A: The canonical question asks "what incidents occurred for the Payments API **last quarter**?" Last quarter is resolved to Q3 2026 (July–September) by the `organizational_memory.json` fiscal calendar. The repository method accepts a `service_id`, a `start` datetime, and an `end` datetime and returns all matching incidents. This is the SQL retrieval path that answers the second part of the canonical question deterministically, without any AI involvement.

---

**Q: Why do repositories use `session.query()` for counts but `select()` for queries?**

A: This is a minor pragmatic choice. `session.query(Model).count()` is the SQLAlchemy 1.x ORM style and is the most concise way to count rows. `select(Model)` is the SQLAlchemy 2.x Core style and returns a `Select` object that can be composed with `.where()`, `.join()`, etc. Using `select()` for parameterised queries gives us composability; using `.count()` for simple row counts keeps the code readable. In a future refactor, all queries could be unified to the 2.x style.

---

## Section 4: Sample Data Design

**Q: Why are incidents spread across three quarters, and why are Q3 incidents the ones for the canonical question?**

A: The canonical question asks about "last quarter". Today is 2026-11-21 (Q4 2026), so last quarter is Q3 2026 (July–September). The 12 incidents are distributed across Q1 (3 incidents), Q2 (3 incidents), and Q3 (6 incidents, including 2 SEV1s). Having incidents in multiple quarters means a retrieval system that ignores time ranges would return too many results — it has to correctly filter to Q3 to answer the canonical question. This validates that the SQL retrieval path, the graph traversal, and the query analysis node are all correctly time-aware.

---

**Q: Why is the hostile vendor note in the sample data at all? Couldn't you just not include it?**

A: Excluding the hostile vendor note would mean the guardrail system is never tested against a real adversarial case. CLAUDE.md §8 specifies: "every document chunk is untrusted. Wrap it, scan it, flag it." If the vendor note didn't exist in the test data, we could build a guardrail that only works on clean data and never know. By including it, Phase 4's guardrail tests have a real injection attempt to defend against. The document is flagged `flagged=True` at ingest time by the seed service, so the guardrail layer can check the flag before passing content to the LLM.

---

**Q: What is `organizational_memory.json` and why is "last quarter" defined there rather than in code?**

A: `organizational_memory.json` is a file of curated shared facts that the AI assistant should know without having to retrieve them from documents or the database — things like the fiscal calendar, SLA definitions, severity levels, and on-call contacts. Defining "last quarter" in code would mean the entire test suite breaks on January 1st (when last quarter would become Q4 2026 instead of Q3). Putting the fiscal calendar definition in memory and resolving it at runtime keeps the tests time-independent and also demonstrates the memory system (Phase 10) working correctly.

---

## Section 5: Seed Service and Lifespan

**Q: What does "idempotent seeding" mean and why is it important?**

A: Idempotent means running the operation multiple times produces the same result as running it once. The seed service checks `session.get(Model, row["id"])` before every INSERT. If the row already exists, it skips it. If the server restarts or if `seed()` is called twice in a test, no duplicate rows are created. This matters because: (a) in development, you restart the server many times; (b) in tests, the fixture-scoped session might call `seed()` from multiple places; (c) in production, a rolling restart means multiple pods might attempt seeding simultaneously.

---

**Q: Why is the seed service called in the lifespan rather than as a startup script?**

A: The lifespan function in FastAPI is the application-level equivalent of `setUp`/`tearDown` in a test. Calling `init_db()` and `seed()` in the lifespan means every environment (development, test, CI, staging, production) gets a consistent startup sequence without needing a separate migration step. For development and CI, this is especially valuable: `make backend` or running the TestClient brings up a fully seeded database without any manual steps. For production with Postgres, the seed service skips rows that already exist, so it is safe to run on every deploy.

---

**Q: Why does `init_db()` create the `data/` directory before creating the SQLite engine?**

A: SQLAlchemy's `create_engine()` does not create parent directories for SQLite file paths — it fails with `OperationalError: unable to open database file` if the directory doesn't exist. The `data/` directory is git-ignored (it contains the local database, which should never be committed), so it doesn't exist in a fresh checkout. `Path(db_path).parent.mkdir(parents=True, exist_ok=True)` creates it on first run with no noise on subsequent runs.

---

## Section 6: Security and Row-Level Security

**Q: What is Row-Level Security in Postgres and how does it complement the application-level RBAC in Phase 3?**

A: Row-Level Security (RLS) is a Postgres feature that evaluates an additional predicate on every query. For example, the `research_sessions` table has a policy: `SELECT` is allowed only if `user_id = auth.uid() OR current_app_role() = 'admin'`. This means even if a bug in the FastAPI code accidentally passes the wrong `user_id` to the repository, the database will still return only the rows that belong to that user. The application-level RBAC (Phase 3's `require_role` decorator) is the first gate; RLS is the second gate. Having two independent gates means a single bug in either layer cannot compromise data isolation.

---

**Q: Why is RLS not enforced in SQLite for development and testing?**

A: SQLite has no native RLS support. For the development and test environments, access control is enforced entirely by the application layer (Phase 3's `require_role`). The important guarantee is that the SQLAlchemy models and the Postgres RLS policies agree on the same access rules — they are both derived from the same role definitions in CLAUDE.md §2. When deployed to Supabase with Postgres, RLS becomes active and provides the second layer of defence. For offline testing, the Phase 3 tests directly test the `require_role` checks.

---

## Section 7: Testing

**Q: How does `test_seed_counts.py` prove the Phase 2 exit criteria without an external database?**

A: The test uses a module-scoped `db_session` fixture that calls `init_db()` and `seed()` directly against the same SQLite file specified by `DATABASE_URL=sqlite:///./data/test.db` in the conftest. Each test then runs a simple `session.query(Model).count()`. Since SQLite creates the file when `init_db()` is called and the seed service fills it idempotently, the tests are fully deterministic and require zero external services. The 14 tests in this file collectively prove: correct counts for all 9 entity types, the vendor note is flagged, the canonical postmortem is indexed, incident-customer links are correct, organizational memory is seeded, and seed is idempotent.

---

**Q: Why are Evidence schema tests in `tests/unit/` rather than `tests/api/`?**

A: The `Evidence` schema is a pure Pydantic model with no HTTP, database, or service layer dependencies. Unit tests (in `tests/unit/`) test logic in complete isolation — no FastAPI client, no database session. The 7 Evidence tests prove that valid data is accepted and invalid data is rejected using only `pytest` and `pydantic`. Putting them in `tests/api/` would imply they test HTTP behaviour, which they don't, and would couple them to the TestClient fixture unnecessarily.
