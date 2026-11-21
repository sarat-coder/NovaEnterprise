# Phase 5 — Interview Q&A: API Contract and Browse API

---

## Conceptual Questions

**Q1. What is an API contract and why is it important in a full-stack project?**

An API contract is a written agreement between the backend and frontend that specifies every URL,
every request/response field, every status code, and every error shape. It matters because teams
can work in parallel without waiting for the other side, both sides have a single source of truth,
automated tests can verify that the implementation matches the contract, and new developers
understand the system without reading all the code.

In this project, `docs/API_CONTRACT.md` is that contract. Any endpoint change requires updating
the contract, the backend schemas, and the frontend types **in the same commit**.

---

**Q2. What is the contract-first design pattern?**

Contract-first (also called API-first or spec-first) means you write the API specification before
writing any implementation code. The specification becomes the shared blueprint. Benefits: the UI
can build a typed client before the backend exists; the backend can be tested against the spec
independently; disagreements surface at design time, not at integration time.

The alternative (code-first) lets the implementation drive the spec, which often leads to
inconsistencies between teams.

---

**Q3. What is a Pydantic schema and why use it instead of plain Python dicts?**

Pydantic is a data validation library. A schema is a class that describes the shape of data —
field names, types, constraints. Benefits: automatic validation (a 3-character question is
rejected before business logic runs), type safety, automatic JSON serialisation, OpenAPI docs
generation, and `from_attributes=True` for reading SQLAlchemy ORM objects directly.

---

**Q4. Why are the browse endpoints readable by all roles including viewers?**

Browse endpoints return read-only data. The RBAC hierarchy restricts *actions*, not *knowledge*.
A viewer should understand the data landscape to make sense of the research answers they're shown.
Restricting browse to analysts would create friction without security benefit (the data is
internal enterprise records, not PII).

---

## Schema and Validation Questions

**Q5. How does the 5–2000 character limit on research questions work?**

```python
class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=2000)
```

Pydantic validates this at deserialisation time — the moment FastAPI parses the request body. If
the question is too short or too long, Pydantic raises a `ValidationError`, which FastAPI converts
to `422 Unprocessable Entity`. No business logic runs. The 5-character minimum prevents trivially
empty questions; the 2000-character maximum protects against prompt-injection padding.

---

**Q6. What is `from_attributes=True` in Pydantic v2?**

By default Pydantic reads data from dicts (`obj["field"]`). SQLAlchemy ORM objects expose
attributes (`obj.field`). Setting `model_config = {"from_attributes": True}` switches Pydantic
to attribute access, so `CustomerOut.model_validate(customer_orm)` works without manual mapping.

---

**Q7. Why are `IncidentOut` and `IncidentDetail` separate schemas?**

The list endpoint should be lean (many records). The detail endpoint is enriched with related
entities. If both used the same schema, either the list carries expensive join data for every row,
or the detail has fields that are always `null`. Using `IncidentDetail(IncidentOut)` — a subclass
— means Detail inherits all base fields and adds `impacted_customers` and `decisions` only for
the single-record case.

---

**Q8. How does FastAPI's dependency injection work for the browse endpoints?**

Each route handler declares dependencies with `Annotated[T, Depends(factory)]`. FastAPI resolves
them before calling the handler: (1) calls `get_current_user(token)` — decodes the JWT, raises
401 if invalid; (2) calls `get_db()` — opens a session, commits on success, rolls back on error;
(3) passes both resolved values into the handler. If step 1 raises, the handler never runs.

---

## Architecture Questions

**Q9. How does the layering rule prevent the router from containing business logic?**

The rule is `api → services → repositories → models`. For browse endpoints: the router calls a
repository method (e.g., `IncidentRepository.get_all()`), never writes SQL inline, never imports
from `agents/` or `rag/`. If a future requirement needs a complex business rule, that logic goes
in a service, not the router.

---

**Q10. What is the difference between `docs/API_CONTRACT.md` and `docs/FRONTEND_ASSUMPTIONS.md`?**

`API_CONTRACT.md` describes the HTTP surface: methods, paths, fields, status codes.
`FRONTEND_ASSUMPTIONS.md` describes runtime behaviour: polling cadence, the exact string IDs for
the 13 LangGraph nodes, how to handle degraded mode, what the four memory scope keys are.
Separating them keeps the contract focused on HTTP and the assumptions document focused on
behaviour that is harder to encode in a schema.

---

## Testing Questions

**Q11. What does `test_list_incidents_viewer_200` prove?**

Three things: the endpoint exists and returns 200; a viewer-role JWT is accepted (not 403); the
seeded database contains exactly 12 incidents (the demo checkpoint for Phase 5). If the seed data
ever changes, this test fails — which is the correct behaviour.

---

**Q12. How are the tests isolated from each other?**

The `_reset_settings` fixture clears `get_settings()` lru_cache before and after every test. Each
test uses a fresh `TestClient` context that re-runs `init_db()` and `seed()`. The database URL
points to `data/test.db` (SQLite), isolating tests from the development database.

---

## Practical / Scenario Questions

**Q13. A developer adds a `region` field to the Customer model. What must they update?**

Per the backend conventions: (1) `models/entities.py` — add the SQLAlchemy column; (2)
`database/schema.sql` — add the column; (3) `database/migrations/` — add an Alembic migration;
(4) `sample_data/customers.json` — add the field to seed data; (5) `schemas/browse.py` — add
`region: str | None` to `CustomerOut`; (6) `docs/API_CONTRACT.md` — update the customer response
shape; (7) frontend types — add `region` to the TypeScript interface. The key rule: contract,
schema, and frontend types change together.

---

**Q14. A viewer calls `POST /api/v1/research`. What happens?**

1. The JWT is valid → `get_current_user` returns `UserContext(role=VIEWER)`.
2. The research router uses `Depends(require_role(Role.ANALYST))`.
3. `require_role` checks `VIEWER (1) < ANALYST (2)` → raises `HTTPException(403)`.
4. Browser receives `403 {"detail": "Insufficient permissions"}`.
Database and LLM are never touched.
