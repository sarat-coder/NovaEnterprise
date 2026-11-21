# Phase 5 — Interview Q&A: API Contract and Browse API

---

## Conceptual Questions

**Q1. What is an API contract and why is it important in a full-stack project?**

An API contract is a written agreement between the backend and frontend that specifies every
URL, every request/response field, every status code, and every error shape. It matters because:

- Teams can work in parallel without waiting for the other side to be "done."
- Both sides have a single source of truth — if the shape changes, the contract changes first.
- Automated tests can verify that the implementation matches the contract.
- New developers understand the system without reading all the code.

In this project, `docs/API_CONTRACT.md` is that contract. Any endpoint change requires updating
the contract, the backend schemas, and the frontend types **in the same commit**.

---

**Q2. What is the contract-first design pattern?**

Contract-first (also called API-first or spec-first) means you write the API specification
before writing any implementation code. The specification — in our case a Markdown document —
becomes the shared blueprint. Benefits:

1. The UI can build a typed client against the spec before the backend exists.
2. The backend can be tested against the spec independently.
3. Disagreements surface at design time, not at integration time.

The alternative (code-first) lets the implementation drive the spec, which often leads to
inconsistencies between teams.

---

**Q3. What is a Pydantic schema and why use it instead of plain Python dicts?**

Pydantic is a data validation library. A schema is a class that describes the shape of data —
field names, types, constraints. Benefits over plain dicts:

- **Automatic validation:** a `ResearchRequest` with a 3-character question is rejected before
  any business logic runs.
- **Type safety:** `str | None` fields are explicit; dicts silently return `None` for missing keys.
- **Serialisation:** `.model_dump()` converts to JSON automatically; FastAPI uses this.
- **Documentation:** FastAPI generates OpenAPI docs from Pydantic schemas.
- **`from_attributes=True`:** allows reading SQLAlchemy ORM objects directly into schemas.

---

**Q4. Why are the browse endpoints readable by all roles including viewers?**

Browse endpoints return read-only data. The RBAC hierarchy (`viewer < analyst < admin`) restricts
*actions*, not *knowledge*. A viewer should be able to understand the data landscape — which
customers exist, which incidents happened — to make sense of the research answers they're shown.

Restricting browse to analysts would create friction without security benefit (the data is not
sensitive in this context — it's internal enterprise records, not PII).

---

## Schema and Validation Questions

**Q5. How does the 5–2000 character limit on research questions work?**

```python
class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=2000)
```

Pydantic validates this at **deserialisation time** — the moment FastAPI parses the request body.
If the question is too short or too long, Pydantic raises a `ValidationError`, which FastAPI
converts to a `422 Unprocessable Entity` with a structured error body. No business logic runs.

The 5-character minimum prevents trivially empty questions ("why", "hi"). The 2000-character
maximum protects the backend from prompt-injection attempts that pad a large body.

---

**Q6. What is `from_attributes=True` in Pydantic v2?**

By default, Pydantic reads data from dicts (`obj["field"]`). SQLAlchemy ORM objects are not
dicts — they expose attributes (`obj.field`). Setting `model_config = {"from_attributes": True}`
switches Pydantic to attribute access, so:

```python
customer_orm = session.get(Customer, 1)
customer_out = CustomerOut.model_validate(customer_orm)  # works!
```

Without this setting, `model_validate` would fail because an ORM object is not subscriptable.

---

**Q7. Why are `IncidentOut` and `IncidentDetail` separate schemas instead of one?**

The list endpoint (`GET /api/v1/incidents`) returns many records — it should be lean. The detail
endpoint (`GET /api/v1/incidents/{id}`) returns one record enriched with related data. If both
used the same schema:

- Either the list response carries expensive join data for every row (slow and wasteful).
- Or the detail response has fields that are always `null`, which confuses the frontend.

Using `IncidentDetail(IncidentOut)` — a subclass — means `Detail` inherits all base fields and
adds `impacted_customers` and `decisions` only for the single-record case.

---

**Q8. How does FastAPI's dependency injection work for the browse endpoints?**

Each route handler declares its dependencies with `Annotated[T, Depends(factory)]`:

```python
def list_incidents(
    _user: Annotated[UserContext, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[IncidentOut]:
```

FastAPI resolves these before calling the handler:
1. Calls `get_current_user(token)` — decodes the JWT, raises 401 if invalid.
2. Calls `get_db()` — opens a SQLAlchemy session, commits on success, rolls back on error.
3. Passes both resolved values into the handler.

If step 1 raises, the handler never runs — a lightweight guard that never touches the database
for unauthenticated requests.

---

## Architecture Questions

**Q9. How does the layering rule prevent the router from containing business logic?**

The rule (from CLAUDE.md §4.2) says: `api → services → repositories → models`. Each layer
only calls the layer directly below it.

For browse endpoints this means:
- The router calls a repository method (e.g., `IncidentRepository.get_all()`).
- It **never** writes SQL inline.
- It **never** imports from `agents/` or `rag/`.

If a future requirement needs to filter incidents by a complex business rule (e.g., "incidents
where the customer is at risk of churning"), that logic goes in a service, not the router.

---

**Q10. What is the difference between `docs/API_CONTRACT.md` and `docs/FRONTEND_ASSUMPTIONS.md`?**

`API_CONTRACT.md` describes **what the API does** — the HTTP surface: methods, paths, fields,
status codes. It answers "what can I call and what do I get back?"

`FRONTEND_ASSUMPTIONS.md` describes **how the frontend should behave** — polling cadence, the
exact string IDs for the 13 LangGraph nodes, how to handle degraded mode, what the four memory
scope keys are. It answers "what does the backend guarantee beyond the HTTP shape?"

Separating them keeps the contract focused on the HTTP layer and the assumptions document
focused on runtime behaviour that is harder to encode in a schema.

---

**Q11. Why does `GET /api/v1/incidents` accept `severity` and `service_id` as query parameters
rather than path segments?**

Path segments (`/incidents/SEV1`) imply a hierarchical resource identity — "the SEV1 incident."
But `SEV1` is a filter, not an identifier. Query parameters (`?severity=SEV1`) are the HTTP
convention for filtering a collection. This follows REST best practices:

- `/incidents/1` → fetch the single incident whose database id is 1
- `/incidents?severity=SEV1` → filter the collection to SEV1 incidents

---

## Testing Questions

**Q12. What does `test_list_incidents_viewer_200` prove?**

It proves three things at once:
1. The endpoint exists and returns 200 (not 404 or 500).
2. A viewer-role JWT is accepted (not 403).
3. The seeded database contains exactly 12 incidents (the demo checkpoint for Phase 5).

If the seed data ever changes, this test fails — which is the correct behaviour.

---

**Q13. How are the tests isolated from each other?**

The `conftest.py` fixture `_reset_settings` runs before and after every test, clearing the
`lru_cache` on `get_settings()`. This prevents test A from leaving stale config that affects
test B.

Each test also uses a fresh `TestClient` context (the `client` fixture opens a new lifespan),
which re-runs `init_db()` and `seed()`. Because the database URL points to `data/test.db` (a
SQLite file), tests are isolated from the development database.

---

**Q14. What does the `model_config` on each schema do?**

`model_config = {"from_attributes": True}` enables ORM mode (previously called `orm_mode`
in Pydantic v1). It tells Pydantic to use `getattr(obj, "field")` instead of `obj["field"]`
when validating. This is the bridge between the SQLAlchemy ORM layer and the Pydantic
response layer — without it, `CustomerOut.model_validate(customer_orm)` would raise a
`TypeError`.

---

## Practical / Scenario Questions

**Q15. A developer adds a `region` field to the Customer model. What must they update?**

Per CLAUDE.md §15 rule 1 and the backend conventions:
1. `backend/app/models/entities.py` — add the SQLAlchemy column.
2. `database/schema.sql` — add the column to the SQL schema.
3. `database/migrations/` — add an Alembic migration.
4. `sample_data/customers.json` — add the field to seed data.
5. `backend/app/schemas/browse.py` — add `region: str | None` to `CustomerOut`.
6. `docs/API_CONTRACT.md` — add `region` to the customer response shape.
7. The frontend types (Phase 13) — add `region` to the TypeScript interface.
8. Update `tests/api/test_browse_api.py` if the new field should be asserted.

The key rule: **contract, schema, and frontend types change together**.

---

**Q16. A viewer calls `POST /api/v1/research`. What happens?**

1. The JWT is valid → `get_current_user` returns `UserContext(role=VIEWER)`.
2. The research router uses `Depends(require_role(Role.ANALYST))`.
3. `require_role` checks `user.role >= ANALYST` → `VIEWER (1) < ANALYST (2)` → raises
   `HTTPException(403, "Insufficient permissions")`.
4. The browser receives `403 {"detail": "Insufficient permissions"}`.

The database is never touched. The LLM is never called.
