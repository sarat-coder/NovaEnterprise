"""Tests for the shared Evidence schema (F4-related, N1).

Every retrieval path returns the same Evidence shape.  These tests prove:
- valid source_types are accepted
- invalid source_types are rejected
- score is clamped 0–1
- metadata defaults to an empty dict
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.common import Evidence


def test_document_evidence_valid():
    """Evidence with source_type='document' is accepted and round-trips correctly."""
    ev = Evidence(
        id="ev-001",
        source_type="document",
        locator="chunk-uuid-1234",
        content="Payments API outage postmortem content",
        score=0.95,
    )
    assert ev.id == "ev-001"
    assert ev.source_type == "document"
    assert ev.locator == "chunk-uuid-1234"
    assert ev.score == 0.95
    assert ev.metadata == {}


def test_sql_evidence_valid():
    """Evidence with source_type='sql' is accepted."""
    ev = Evidence(
        id="ev-002",
        source_type="sql",
        locator="query-uuid-5678",
        content="SELECT incident_id, title FROM incidents WHERE service_id = 1",
    )
    assert ev.source_type == "sql"
    assert ev.score == 1.0  # default


def test_graph_evidence_valid():
    """Evidence with source_type='graph' is accepted."""
    ev = Evidence(
        id="ev-003",
        source_type="graph",
        locator="traversal-uuid-9012",
        content="MATCH (s:Service {name:'Payments API'})<-[:AFFECTED]-(i:Incident) RETURN i",
        metadata={
            "cypher": "MATCH (s:Service {name:'Payments API'})<-[:AFFECTED]-(i:Incident) RETURN i"
        },
    )
    assert ev.source_type == "graph"
    assert "cypher" in ev.metadata


def test_invalid_source_type_rejected():
    """source_type values outside the Literal are rejected by Pydantic."""
    with pytest.raises(ValidationError):
        Evidence(
            id="ev-bad",
            source_type="unknown",  # not in Literal
            locator="x",
            content="x",
        )


def test_score_above_one_rejected():
    """Score > 1.0 violates the ge=0, le=1 constraint."""
    with pytest.raises(ValidationError):
        Evidence(
            id="ev-bad2",
            source_type="document",
            locator="x",
            content="x",
            score=1.5,
        )


def test_score_below_zero_rejected():
    """Score < 0 violates the ge=0 constraint."""
    with pytest.raises(ValidationError):
        Evidence(
            id="ev-bad3",
            source_type="document",
            locator="x",
            content="x",
            score=-0.1,
        )


def test_evidence_metadata_populated():
    """metadata is a free-form dict and can carry any JSON-serialisable values."""
    ev = Evidence(
        id="ev-004",
        source_type="sql",
        locator="q-123",
        content="rows returned",
        metadata={"table": "incidents", "rows": 3, "executed_at": "2026-07-18T11:23:00"},
    )
    assert ev.metadata["rows"] == 3
