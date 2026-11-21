"""
Tests for research request/response Pydantic schemas.

Covers:
  P5-3 — ResearchRequest validation (5..2000 chars), SubQuestion, ResearchSessionOut
  Phase 5 exit criteria — schema enforces question length bounds
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.research import ResearchRequest, ResearchSessionOut, SubQuestion

# ---------------------------------------------------------------------------
# ResearchRequest validation
# ---------------------------------------------------------------------------


def test_valid_question_min_length():
    """A question of exactly 5 characters is accepted."""
    req = ResearchRequest(question="hello")
    assert req.question == "hello"


def test_valid_question_typical():
    """A normal-length question is accepted."""
    req = ResearchRequest(
        question="Which customers were impacted by the Payments API last quarter?"
    )
    assert len(req.question) > 5


def test_valid_question_max_length():
    """A question of exactly 2000 characters is accepted."""
    req = ResearchRequest(question="x" * 2000)
    assert len(req.question) == 2000


def test_question_too_short_raises():
    """A question under 5 characters is rejected with a ValidationError (P5-3)."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="hi")


def test_question_empty_raises():
    """Empty string is rejected."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="")


def test_question_too_long_raises():
    """A question over 2000 characters is rejected (P5-3)."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="x" * 2001)


# ---------------------------------------------------------------------------
# SubQuestion
# ---------------------------------------------------------------------------


def test_subquestion_defaults():
    """SubQuestion has sensible defaults for status and evidence_ids."""
    sq = SubQuestion(id="sq1", question="What happened?", strategy="sql")
    assert sq.status == "pending"
    assert sq.evidence_ids == []


def test_subquestion_valid_strategies():
    """All four strategy values are accepted."""
    for strategy in ("vector", "sql", "graph", "hybrid"):
        sq = SubQuestion(id="sq1", question="Q", strategy=strategy)
        assert sq.strategy == strategy


# ---------------------------------------------------------------------------
# ResearchSessionOut
# ---------------------------------------------------------------------------


def test_session_out_defaults():
    """ResearchSessionOut has correct default values."""
    out = ResearchSessionOut(
        session_id="abc",
        question="What is the data retention policy?",
        status="running",
    )
    assert out.strategies_used == []
    assert out.evidence == []
    assert out.evidence_count == 0
    assert out.corrective_rounds == 0
    assert "organizational" in out.memory_scopes
    assert "conversation" in out.memory_scopes
    assert "session" in out.memory_scopes
    assert "user" in out.memory_scopes


def test_session_out_completed_shape():
    """A completed session carries answer, citations_valid, and evidence."""
    from app.schemas.common import Evidence

    out = ResearchSessionOut(
        session_id="xyz",
        question="Who was impacted?",
        status="completed",
        complexity="complex",
        strategies_used=["graph", "sql"],
        evidence=[
            Evidence(
                id="e1",
                source_type="sql",
                locator="q-001",
                content="3 customers impacted",
                score=0.9,
            )
        ],
        answer="Three customers were impacted [1].",
        citations_valid=True,
        evidence_count=1,
        citation_count=1,
    )
    assert out.status == "completed"
    assert out.answer is not None
    assert out.citations_valid is True
    assert len(out.evidence) == 1
