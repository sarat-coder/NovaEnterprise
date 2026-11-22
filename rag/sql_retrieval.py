"""SQL retrieval: validator, templates, and retriever (P8-1, P8-2, P8-3, F7).

Security contract
-----------------
- validate_sql() is called on EVERY statement before execution.
- Only SELECT is allowed; DDL, DML, and comment tricks are rejected.
- Only allowlisted tables and columns may appear in a query.
- Every executed query is recorded with a UUID and returned as Evidence.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.schemas.common import Evidence

# ---------------------------------------------------------------------------
# Allowlists (P8-1)
# ---------------------------------------------------------------------------

ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "teams",
        "employees",
        "services",
        "customers",
        "incidents",
        "incident_customers",
        "decisions",
        "incident_decisions",
        "projects",
        "tickets",
    }
)

# Map table → allowed column names (use "*" to allow all columns on that table)
ALLOWED_COLUMNS: dict[str, frozenset[str]] = {
    "teams": frozenset({"id", "name", "slug", "description", "lead_email", "created_at"}),
    "employees": frozenset({"id", "name", "email", "title", "team_id", "created_at"}),
    "services": frozenset(
        {"id", "name", "slug", "description", "owner_team_id", "tier", "created_at"}
    ),
    "customers": frozenset(
        {"id", "name", "slug", "segment", "industry", "contract_tier", "created_at"}
    ),
    "incidents": frozenset(
        {
            "id",
            "incident_id",
            "title",
            "severity",
            "status",
            "service_id",
            "root_cause",
            "summary",
            "started_at",
            "resolved_at",
            "created_at",
        }
    ),
    "incident_customers": frozenset({"incident_id", "customer_id", "impact_description"}),
    "decisions": frozenset(
        {
            "id",
            "adr_id",
            "title",
            "status",
            "context",
            "decision_text",
            "consequences",
            "decided_at",
            "created_at",
        }
    ),
    "incident_decisions": frozenset({"incident_id", "decision_id"}),
    "projects": frozenset(
        {
            "id",
            "name",
            "slug",
            "description",
            "status",
            "team_id",
            "start_date",
            "end_date",
            "created_at",
        }
    ),
    "tickets": frozenset(
        {
            "id",
            "ticket_id",
            "title",
            "description",
            "status",
            "priority",
            "project_id",
            "assignee_id",
            "story_points",
            "created_at",
            "closed_at",
        }
    ),
}

# DDL and DML keywords that must never appear in an allowed query
_FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "insert",
    "update",
    "delete",
    "merge",
    "upsert",
    "create",
    "alter",
    "drop",
    "truncate",
    "replace",
    "grant",
    "revoke",
    "execute",
    "exec",
    "call",
    "pragma",  # SQLite PRAGMA can expose/change settings
    "attach",
    "detach",
    "load_extension",
)

# ---------------------------------------------------------------------------
# Validator (P8-1)
# ---------------------------------------------------------------------------


class SqlValidationError(ValueError):
    """Raised when a SQL statement fails validation."""


def validate_sql(sql: str) -> str:
    """Validate *sql* against the security allowlist.

    Returns the stripped, normalised statement on success.
    Raises SqlValidationError with a human-readable message on failure.

    Rules (all must hold):
    1. Non-empty after stripping.
    2. No inline comments (--) or block comments (/* */).
    3. No semicolons that separate multiple statements.
    4. Must start with SELECT (after stripping comments).
    5. No forbidden DDL / DML keywords at word boundaries.
    6. All table names referenced are in ALLOWED_TABLES.
    7. All column names referenced are in the allowlist for their table
       (or the query uses SELECT * which is permitted for simplicity).
    """
    if not sql or not sql.strip():
        raise SqlValidationError("SQL statement is empty.")

    stmt = sql.strip()

    # Rule 2 — reject comment tricks
    if "--" in stmt:
        raise SqlValidationError("Inline SQL comments (--) are not permitted.")
    if re.search(r"/\*", stmt):
        raise SqlValidationError("Block SQL comments (/* */) are not permitted.")

    # Rule 3 — reject multiple statements (semicolons)
    if ";" in stmt:
        raise SqlValidationError("Multiple SQL statements separated by ';' are not permitted.")

    # Normalise to lower-case for keyword checks (preserving original for execution)
    lower = stmt.lower()

    # Rule 4 — must be a SELECT
    if not lower.lstrip().startswith("select"):
        raise SqlValidationError(
            "Only SELECT statements are permitted; this statement starts with something else."
        )

    # Rule 5 — no forbidden keywords at word boundaries
    for kw in _FORBIDDEN_KEYWORDS:
        pattern = rf"\b{re.escape(kw)}\b"
        if re.search(pattern, lower):
            raise SqlValidationError(f"Forbidden keyword '{kw.upper()}' found in SQL statement.")

    # Rule 6 — all table names must be allowlisted
    # Extract identifiers after FROM, JOIN keywords
    table_refs = re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", lower)
    for tbl in table_refs:
        if tbl not in ALLOWED_TABLES:
            raise SqlValidationError(f"Table '{tbl}' is not in the SQL allowlist.")

    # Rule 7 — column names (skip wildcard SELECT *)
    # Only validate explicit dot-qualified columns: table.column
    dot_refs = re.findall(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", lower)
    for tbl, col in dot_refs:
        if tbl in ALLOWED_COLUMNS and col not in ALLOWED_COLUMNS[tbl]:
            raise SqlValidationError(
                f"Column '{col}' on table '{tbl}' is not in the SQL allowlist."
            )

    return stmt


# ---------------------------------------------------------------------------
# Query templates (P8-2)
# ---------------------------------------------------------------------------

# Each template is a string with named :param placeholders (SQLAlchemy style).
# They are validated at module load time to catch mistakes early.

QUERY_TEMPLATES: dict[str, str] = {
    # Incidents that affected a named service within a date range
    "incidents_by_service_and_date": (
        "SELECT i.incident_id, i.title, i.severity, i.status, "
        "i.started_at, i.resolved_at, i.root_cause, i.summary, "
        "s.name AS service_name "
        "FROM incidents i "
        "JOIN services s ON s.id = i.service_id "
        "WHERE s.name = :service_name "
        "AND i.started_at >= :start_date "
        "AND i.started_at <= :end_date "
        "ORDER BY i.started_at DESC"
    ),
    # All incidents for a service (no date filter)
    "incidents_by_service": (
        "SELECT i.incident_id, i.title, i.severity, i.status, "
        "i.started_at, i.resolved_at, i.root_cause, i.summary, "
        "s.name AS service_name "
        "FROM incidents i "
        "JOIN services s ON s.id = i.service_id "
        "WHERE s.name = :service_name "
        "ORDER BY i.started_at DESC"
    ),
    # Decisions related to a specific incident
    "decisions_for_incident": (
        "SELECT d.adr_id, d.title, d.status, d.decision_text, d.decided_at "
        "FROM decisions d "
        "JOIN incident_decisions id ON id.decision_id = d.id "
        "JOIN incidents i ON i.id = id.incident_id "
        "WHERE i.incident_id = :incident_id"
    ),
    # Customers impacted by a specific incident
    "customers_impacted_by_incident": (
        "SELECT c.name, c.segment, c.industry, ic.impact_description "
        "FROM customers c "
        "JOIN incident_customers ic ON ic.customer_id = c.id "
        "JOIN incidents i ON i.id = ic.incident_id "
        "WHERE i.incident_id = :incident_id"
    ),
    # Services owned by a team
    "services_owned_by_team": (
        "SELECT s.name, s.slug, s.tier, s.description "
        "FROM services s "
        "JOIN teams t ON t.id = s.owner_team_id "
        "WHERE t.name = :team_name"
    ),
}

# Validate every template at import time
for _name, _sql in QUERY_TEMPLATES.items():
    try:
        # Strip :param placeholders before validation (they look like identifiers)
        _cleaned = re.sub(r":\w+", "'placeholder'", _sql)
        validate_sql(_cleaned)
    except SqlValidationError as _exc:
        raise RuntimeError(f"Built-in SQL template '{_name}' failed validation: {_exc}") from _exc


# ---------------------------------------------------------------------------
# Recorded query store (P8-3)
# ---------------------------------------------------------------------------


@dataclass
class RecordedQuery:
    """A single executed SQL query with its results and a stable id."""

    query_id: str
    template_name: str
    sql: str
    params: dict[str, Any]
    rows: list[dict[str, Any]]
    executed_at: str  # ISO-8601


# Module-level in-process store for the demo/test path.
# In production this would be persisted to the database.
_recorded_queries: list[RecordedQuery] = []


def get_recorded_queries() -> list[RecordedQuery]:
    """Return all queries recorded in this process (read-only copy)."""
    return list(_recorded_queries)


def clear_recorded_queries() -> None:
    """Clear the recorded query store. Use in tests only."""
    _recorded_queries.clear()


# ---------------------------------------------------------------------------
# SQL Retriever (P8-3)
# ---------------------------------------------------------------------------


class SqlRetriever:
    """Execute a named SQL template and return Evidence.

    This class is the single entry point for SQL retrieval in the research
    workflow.  It:
    1. Looks up the template by name.
    2. Substitutes params into a copy for display (not for execution — the
       driver handles binding to prevent injection).
    3. Validates the template SQL (params stripped).
    4. Executes the query against the database (or the in-memory fake path).
    5. Records the query with a UUID.
    6. Returns a list of Evidence(source_type="sql") items.
    """

    def __init__(self, db_session: Any | None = None) -> None:
        self._db = db_session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        template_name: str,
        params: dict[str, Any],
        *,
        top_k: int = 10,
    ) -> list[Evidence]:
        """Run a template query and return evidence.

        Parameters
        ----------
        template_name:
            Key in QUERY_TEMPLATES.
        params:
            Named parameters matched to the template's :param slots.
        top_k:
            Maximum number of rows to return as evidence items.
        """
        if template_name not in QUERY_TEMPLATES:
            raise ValueError(
                f"Unknown SQL template '{template_name}'. Available: {sorted(QUERY_TEMPLATES)}"
            )

        sql = QUERY_TEMPLATES[template_name]

        # Always validate before execution (even though it passed at import)
        cleaned = re.sub(r":\w+", "'placeholder'", sql)
        validate_sql(cleaned)

        rows = self._execute(sql, params, top_k)
        query_id = str(uuid.uuid4())

        recorded = RecordedQuery(
            query_id=query_id,
            template_name=template_name,
            sql=sql,
            params=params,
            rows=rows,
            executed_at=datetime.utcnow().isoformat(),
        )
        _recorded_queries.append(recorded)

        return self._rows_to_evidence(recorded)

    def retrieve_raw(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        top_k: int = 10,
    ) -> list[Evidence]:
        """Execute a raw SQL string after validation.

        Used by analysts who write their own queries.  The same validation
        rules apply — if it fails, SqlValidationError is raised.
        """
        validate_sql(sql)
        rows = self._execute(sql, params or {}, top_k)
        query_id = str(uuid.uuid4())

        recorded = RecordedQuery(
            query_id=query_id,
            template_name="raw",
            sql=sql,
            params=params or {},
            rows=rows,
            executed_at=datetime.utcnow().isoformat(),
        )
        _recorded_queries.append(recorded)

        return self._rows_to_evidence(recorded)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute(
        self,
        sql: str,
        params: dict[str, Any],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Run *sql* with *params* and return at most *top_k* rows as dicts."""
        if self._db is None:
            # No live session — return empty rows (fake / offline path).
            return []

        from sqlalchemy import text  # noqa: PLC0415

        result = self._db.execute(text(sql), params)
        columns = list(result.keys())
        rows = []
        for row in result.fetchmany(top_k):
            row_dict: dict[str, Any] = {}
            for col, val in zip(columns, row, strict=False):
                # Convert non-serialisable types (datetime → ISO string)
                if isinstance(val, datetime):
                    row_dict[col] = val.isoformat()
                else:
                    row_dict[col] = val
            rows.append(row_dict)
        return rows

    @staticmethod
    def _rows_to_evidence(recorded: RecordedQuery) -> list[Evidence]:
        """Convert a RecordedQuery into one Evidence item per result row.

        When there are no rows the returned list contains a single evidence
        item noting that the query ran but returned no results (so the agent
        can reason about an empty result set rather than getting silence).
        """
        if not recorded.rows:
            return [
                Evidence(
                    id=f"sql-{recorded.query_id}",
                    source_type="sql",
                    locator=recorded.query_id,
                    content=f"Query '{recorded.template_name}' returned no results.",
                    score=0.5,
                    metadata={
                        "sql": recorded.sql,
                        "params": recorded.params,
                        "executed_at": recorded.executed_at,
                    },
                )
            ]

        evidence_items: list[Evidence] = []
        for idx, row in enumerate(recorded.rows):
            # Build a readable content string from the row
            content_parts = [f"{k}: {v}" for k, v in row.items() if v is not None]
            content = " | ".join(content_parts)
            evidence_items.append(
                Evidence(
                    id=f"sql-{recorded.query_id}-{idx}",
                    source_type="sql",
                    locator=recorded.query_id,
                    content=content,
                    score=1.0,
                    metadata={
                        "sql": recorded.sql,
                        "params": recorded.params,
                        "row_index": idx,
                        "executed_at": recorded.executed_at,
                    },
                )
            )
        return evidence_items
