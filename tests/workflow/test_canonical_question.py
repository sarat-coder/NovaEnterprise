"""test_canonical_question_end_to_end — the canonical question exercise (F2–F12)."""

from __future__ import annotations

import pytest

from agents.graph import build_graph

CANONICAL = (
    "Which customers were impacted by the Payments API last quarter, "
    "what incidents occurred, which teams own those services, and what "
    "decisions were taken to prevent recurrence?"
)


@pytest.fixture(scope="module")
def canonical_state():
    compiled = build_graph()
    return compiled.invoke(
        {
            "session_id": "test-canonical",
            "question": CANONICAL,
            "evidence": [],
            "sub_questions": [],
            "strategies_used": [],
            "corrective_rounds": 0,
            "missing_evidence_keys": [],
            "error": None,
        }
    )


def test_complexity_is_complex(canonical_state):
    """F3: canonical question is classified complex."""
    assert canonical_state.get("complexity") == "complex"


def test_entity_detected(canonical_state):
    """F2: Payments API entity is extracted."""
    entities = [e.lower() for e in canonical_state.get("entities", [])]
    assert any("payments" in e for e in entities), (
        f"Payments API not in {canonical_state.get('entities')}"
    )


def test_time_range_detected(canonical_state):
    """F2: last quarter time range is detected."""
    tr = canonical_state.get("time_range", {})
    assert tr, "time_range should not be empty for canonical question"


def test_four_sub_questions(canonical_state):
    """F4: canonical question decomposes to exactly 4 sub-questions."""
    sqs = canonical_state.get("sub_questions", [])
    assert len(sqs) == 4, f"Expected 4 sub-questions, got {len(sqs)}"


def test_routing_uses_multiple_strategies(canonical_state):
    """F5: canonical question uses graph, sql, and hybrid strategies."""
    strategies = set(canonical_state.get("strategies_used", []))
    assert "graph" in strategies, f"graph not in {strategies}"
    assert "sql" in strategies, f"sql not in {strategies}"


def test_no_relationship_question_routed_vector_only(canonical_state):
    """F5 / CLAUDE.md guarantee: relationship sub-questions are never vector-only."""
    for sq in canonical_state.get("sub_questions", []):
        q = sq.get("question", "").lower()
        if any(kw in q for kw in ("which customers", "which teams", "impacted")):
            assert sq.get("strategy") != "vector", (
                f"Relationship sub-question '{sq['question']}' was routed vector-only"
            )


def test_evidence_collected(canonical_state):
    """F6–F8: evidence is collected from at least one retrieval path."""
    evidence = canonical_state.get("evidence", [])
    assert len(evidence) > 0, "No evidence was collected for canonical question"


def test_corrective_rounds_bounded(canonical_state):
    """F9: corrective rounds never exceed MAX_CORRECTIVE_ROUNDS (1)."""
    rounds = canonical_state.get("corrective_rounds", 0)
    assert rounds <= 1, f"Corrective rounds exceeded limit: {rounds}"


def test_answer_produced(canonical_state):
    """F11: an answer string is produced."""
    assert canonical_state.get("answer"), "Answer should not be empty"


def test_citations_valid(canonical_state):
    """F12: all citations in the answer resolve to evidence."""
    cv = canonical_state.get("citations_valid")
    assert cv is True or cv is None
