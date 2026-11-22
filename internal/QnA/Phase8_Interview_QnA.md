# Phase 8 — Interview Questions & Answers: SQL Retrieval

> All possible interview questions from Phase 8 — SQL validator, query templates, and the SQL retriever.
> Questions cover beginner, intermediate, and advanced levels.

---

## Section A — Concept and motivation

**Q1. Why does the platform need a SQL retrieval path at all? Can't it answer everything from documents?**

A: Documents are unstructured — they describe events in prose. When you need exact, structured records (e.g. "every incident between July 1 and September 30 with severity SEV1"), a document search gives you approximate matches. A SQL query gives you definitive results from the authoritative database. The canonical question requires both: incident details come from SQL; the postmortem narrative comes from vector search. No single retrieval strategy can answer it alone.

---

**Q2. What is the key design principle behind Phase 8's SQL safety model?**

A: Defence in depth — multiple overlapping security controls rather than one single gate. Specifically:
1. **Template-first:** The AI picks a named template, not free-form SQL. The SQL structure is fixed.
2. **Validate every statement:** Even template SQL is validated at runtime (and at import time). There is no trusted path.
3. **Allowlist, not denylist:** We enumerate what IS allowed (tables, non-DDL/DML keywords), rather than trying to block every possible attack.
4. **Read-only by construction:** The validator blocks all write operations; there is no code path that could issue an UPDATE or DELETE.

---

**Q3. What is the difference between a denylist and an allowlist approach to SQL security? Which did you use?**

A: A **denylist** says "block these bad things" — it is inherently incomplete because an attacker can find new ways to cause harm that are not on the list. An **allowlist** says "only permit these specific things" — anything not explicitly permitted is blocked. Phase 8 uses an **allowlist**: only specific tables (`ALLOWED_TABLES`) and columns (`ALLOWED_COLUMNS`) are permitted. Unknown tables are blocked by default. This is the stronger approach.

---

**Q4. Why are SQL templates validated at import time rather than only at runtime?**

A: Fail-fast principle. If a developer accidentally introduces a dangerous keyword into a template (e.g. while refactoring), the application will refuse to start and print a `RuntimeError`. The bug is caught before any traffic hits the server, not after a customer query triggers it. It also acts as self-documentation — every template is a tested, certified-safe query.

---

## Section B — The SQL validator

**Q5. Walk me through every rule the SQL validator applies.**

A: Seven rules, in order:
1. **Non-empty:** Blank input is rejected immediately.
2. **No inline comments (`--`):** These can be used to inject hidden SQL after a comment marker.
3. **No block comments (`/* */`):** Same injection risk; also used to obfuscate malicious keywords.
4. **No semicolons:** Semicolons separate statements; `SELECT 1; DROP TABLE incidents` is a classic injection.
5. **Must start with SELECT:** INSERT, UPDATE, DELETE, DDL — all rejected before any further analysis.
6. **No forbidden keywords at word boundaries:** A regex check for `\b(insert|drop|delete|...)\b` catches keywords embedded in longer statements.
7. **All tables in ALLOWED_TABLES:** Any table reference after FROM or JOIN is extracted and checked against the allowlist.

---

**Q6. Why do you check for `--` comments even though they don't modify data?**

A: Comments are a classic SQL injection vector. `SELECT * FROM users WHERE id = 1 -- AND role = 'admin'` bypasses a WHERE clause by commenting it out. Even read-only injection can expose data the analyst is not authorised to see (e.g. a table not in the allowlist). Blocking comments eliminates an entire class of injection technique.

---

**Q7. The validator uses regex to find table names. Could a clever attacker bypass this?**

A: The regex extracts table names after `FROM` and `JOIN` keywords (`\b(?:from|join)\s+([a-z_][a-z0-9_]*)`). An attacker could try subqueries or CTEs (`WITH x AS (SELECT ...)`). The current validator does not parse SQL — it uses pattern matching. For a production hardening path: use a proper SQL parser (e.g. `sqlglot` or `sqlparse`) to build an AST and walk the table references. The current approach is sufficient for the controlled template path and analyst-entered queries; it is documented as a known limitation.

---

**Q8. What happens if `validate_sql()` is called with a template that uses `:param` placeholders?**

A: Placeholders like `:service_name` look like `identifier:identifier` to regex. The validator normalises them before checking — `re.sub(r":\w+", "'placeholder'", sql)` replaces every `:param` with the string `'placeholder'`. This prevents false positives where a parameter name happened to match a forbidden keyword.

---

**Q9. How does the validator handle the `PRAGMA` keyword in SQLite?**

A: `PRAGMA` is in the `_FORBIDDEN_KEYWORDS` tuple. SQLite `PRAGMA` statements can expose or change database settings (e.g. `PRAGMA integrity_check`, `PRAGMA journal_mode=DELETE`). Blocking it prevents both information leakage and setting manipulation. This is a SQLite-specific addition to the standard SQL denylist.

---

## Section C — Query templates

**Q10. Why use pre-written templates instead of letting the LLM generate SQL from scratch?**

A: Three reasons:
1. **Correctness:** A human engineer verified that each template joins the right tables with the right conditions. An LLM-generated query might silently produce wrong results (wrong join key, off-by-one in a date filter).
2. **Safety:** Templates are validated once and certified. Free-form LLM SQL requires real-time validation of every output, and the LLM might find ways around the validator that templates never would.
3. **Offline operation:** Templates work with `LLM_PROVIDER=fake` — the agent just selects a template name. Free-form generation requires a real LLM.

---

**Q11. What templates did you create for Phase 8? What question does each one answer?**

A: Five templates:

| Template | Question answered |
|---|---|
| `incidents_by_service_and_date` | Show incidents for a service within a start/end date range |
| `incidents_by_service` | Show all incidents for a service (no date filter) |
| `decisions_for_incident` | What decisions addressed a given incident? |
| `customers_impacted_by_incident` | Which customers were affected by a given incident? |
| `services_owned_by_team` | Which services does a given team own? |

The first template directly answers the "what incidents occurred?" sub-question of the canonical research question.

---

**Q12. How does the agent choose which template to use?**

A: In Phase 8, the routing is done by the research agent's routing node (implemented in Phase 11). The agent analyses the sub-question and picks the template that best matches it. For Phase 8's standalone tests, the retriever is called directly with a specified template name. The template selection logic is deterministic — driven by rules in `agents/rules.py`, not by the LLM.

---

## Section D — The SQL retriever and evidence

**Q13. What is a `RecordedQuery` and why does it exist?**

A: A `RecordedQuery` is a dataclass that captures everything about one SQL execution:
- `query_id`: a UUID assigned at execution time — this becomes the evidence `locator`
- `template_name`: which template was used (or "raw" for analyst-entered SQL)
- `sql`: the full SQL text
- `params`: the parameter values that were bound
- `rows`: the result rows (as dicts with ISO-8601 dates)
- `executed_at`: when the query ran

It exists for three purposes: transparency (analysts can inspect every query), citation resolution (the `query_id` links an answer's `[n]` marker to its source query), and future audit-log persistence.

---

**Q14. How does the SQL retriever return its results as Evidence? What if a query returns no rows?**

A: The `_rows_to_evidence()` method converts each result row into one `Evidence(source_type="sql")` item. The `content` field is a human-readable `key: value | key: value` string from the row. The `locator` is the `query_id`.

If the query returns no rows, one Evidence item is still returned with the content `"Query '...' returned no results."` and a `score=0.5`. This is intentional: the agent needs to know the query *ran and was empty*, not that the query was silently skipped. An empty result set is a meaningful finding.

---

**Q15. How does the SQL Evidence item integrate with Evidence from vector and graph retrieval?**

A: All three paths return the same `Evidence` Pydantic model from `backend/app/schemas/common.py`:

```python
Evidence(
    id="sql-{uuid}-{row_index}",
    source_type="sql",        # document | sql | graph
    locator="{query_id}",    # resolved to RecordedQuery
    content="...",
    score=1.0,
    metadata={"sql": "...", "params": {...}, "executed_at": "..."}
)
```

The synthesis node in Phase 11 merges all evidence items into a single numbered list. Citations like `[2]` in the answer resolve to `evidence[2].locator`, which the frontend looks up to show either the document chunk, the graph traversal, or the SQL query — depending on `source_type`.

---

**Q16. The retriever accepts `db_session=None`. What happens in that case?**

A: When `db_session=None` (the offline/test path), `_execute()` returns an empty list immediately without attempting a database connection. The query is still recorded (`RecordedQuery` with empty `rows`) and evidence is still returned (the "no results" evidence item). Tests can verify the full retriever lifecycle — template lookup, validation, recording, evidence conversion — without ever touching a real database.

---

## Section E — Testing and architecture

**Q17. CLAUDE.md says there must be exactly 8 unit tests for the SQL validator. What are they?**

A: The eight tests in `tests/unit/test_sql_validator.py` prove:
1. A valid SELECT on an allowlisted table is accepted.
2. An empty statement is rejected.
3. INSERT (DML) is rejected.
4. DROP TABLE (DDL) is rejected.
5. Multiple statements separated by `;` are rejected.
6. Inline comment (`--`) is rejected.
7. Block comment (`/* */`) is rejected.
8. A query referencing an unknown table is rejected.

Each test maps to a specific security rule and can fail independently. This makes regressions easy to diagnose.

---

**Q18. Where does `rag/sql_retrieval.py` sit in the layering rules? What can it import and what can it not?**

A: `rag/` is the retrieval layer. It:
- **CAN import** from `app.schemas.common` (the Evidence model) and `app.core.*` (config, logging).
- **CANNOT import** from `app.api.*` (FastAPI types), `app.services.*`, or `app.repositories.*` (those are the application layer above it).
- **CANNOT import** from `agents/` or `memory/` (those are parallel layers).

The import rule is strictly one-way: `api → services → repositories → models` on one chain, and `agents / rag / memory → app.core` on the other. `rag/` knows nothing about FastAPI, HTTP, or agent state.

---

**Q19. If a new table is added to the database schema in a future phase, what changes are required in `sql_retrieval.py`?**

A: Two additions:
1. Add the table name to `ALLOWED_TABLES`.
2. Add its column names to `ALLOWED_COLUMNS`.

No changes to the validator logic itself. This is the advantage of an allowlist — adding new permissions is a simple, reviewable configuration change.

---

**Q20. How would you extend Phase 8 to support LLM-generated SQL in addition to templates?**

A: The `retrieve_raw()` method already exists for this purpose. The agent would call it with AI-generated SQL, which is then run through `validate_sql()` before execution. The recommended architecture:
1. The LLM generates a candidate SQL string.
2. `validate_sql()` runs — if it fails, the agent retries with an error message in the prompt.
3. If it passes, `retrieve_raw()` executes it and records it.
4. The Evidence items carry the generated SQL in `metadata.sql` for full transparency.

This follows the "rules first, LLM second" principle in CLAUDE.md: templates are always tried first; LLM generation is a fallback for queries the templates cannot cover.

---

## Quick reference: Phase 8 at a glance

| Item | Detail |
|---|---|
| New file | `rag/sql_retrieval.py` |
| New test file | `tests/unit/test_sql_validator.py` |
| Test count | 202 → 210 (8 new) |
| PRD requirement | F7 (read-only SQL), N1 (offline) |
| Allowlisted tables | 10 (teams, employees, services, customers, incidents, incident_customers, decisions, incident_decisions, projects, tickets) |
| Validator rules | 7 |
| Templates | 5 |
| Evidence shape | `source_type="sql"`, locator = `query_id` |
| Offline support | ✅ `db_session=None` returns empty rows |
| Lint status | Clean (`ruff check`, `ruff format --check`) |
