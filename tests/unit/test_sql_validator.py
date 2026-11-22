"""SQL validator tests (P8-1, F7).

Eight tests that prove validate_sql() enforces the security contract:
1. Valid SELECT passes.
2. Empty statement rejected.
3. Non-SELECT (INSERT) rejected.
4. DDL (DROP TABLE) rejected.
5. Multiple statements (semicolon) rejected.
6. Inline comment trick (--)  rejected.
7. Block comment trick (/* */) rejected.
8. Unknown table rejected.
"""

from __future__ import annotations

import pytest

from rag.sql_retrieval import SqlValidationError, validate_sql

# ---------------------------------------------------------------------------
# 1. Happy-path
# ---------------------------------------------------------------------------


def test_valid_select_passes():
    """A well-formed SELECT on an allowlisted table is accepted (F7, N1)."""
    sql = "SELECT i.incident_id, i.title, i.severity FROM incidents i WHERE i.severity = 'SEV1'"
    result = validate_sql(sql)
    assert result.strip().lower().startswith("select")


# ---------------------------------------------------------------------------
# 2. Empty input
# ---------------------------------------------------------------------------


def test_empty_statement_rejected():
    """An empty string must be rejected (F7)."""
    with pytest.raises(SqlValidationError, match="empty"):
        validate_sql("   ")


# ---------------------------------------------------------------------------
# 3. DML — INSERT
# ---------------------------------------------------------------------------


def test_insert_rejected():
    """INSERT is a DML statement and must be blocked (F7)."""
    with pytest.raises(SqlValidationError):
        validate_sql("INSERT INTO incidents (title) VALUES ('pwned')")


# ---------------------------------------------------------------------------
# 4. DDL — DROP TABLE
# ---------------------------------------------------------------------------


def test_drop_table_rejected():
    """DROP TABLE is DDL and must be blocked even when surrounded by text (F7)."""
    with pytest.raises(SqlValidationError):
        validate_sql("DROP TABLE incidents")


# ---------------------------------------------------------------------------
# 5. Multiple statements via semicolon
# ---------------------------------------------------------------------------


def test_multiple_statements_rejected():
    """Two statements separated by ';' must be rejected (F7)."""
    with pytest.raises(SqlValidationError, match="';'"):
        validate_sql("SELECT 1; DROP TABLE incidents")


# ---------------------------------------------------------------------------
# 6. Inline comment trick (--)
# ---------------------------------------------------------------------------


def test_inline_comment_rejected():
    """SQL injection via '-- comment' must be rejected (F7, N8)."""
    with pytest.raises(SqlValidationError, match="--"):
        validate_sql("SELECT * FROM incidents -- ignore the rest")


# ---------------------------------------------------------------------------
# 7. Block comment trick (/* */)
# ---------------------------------------------------------------------------


def test_block_comment_rejected():
    """SQL injection via '/* block */' must be rejected (F7, N8)."""
    with pytest.raises(SqlValidationError, match=r"/\*"):
        validate_sql("SELECT /* comment */ * FROM incidents")


# ---------------------------------------------------------------------------
# 8. Unknown table
# ---------------------------------------------------------------------------


def test_unknown_table_rejected():
    """A table not in ALLOWED_TABLES must be rejected (F7)."""
    with pytest.raises(SqlValidationError, match="not in the SQL allowlist"):
        validate_sql("SELECT * FROM secret_credentials")
