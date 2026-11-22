"""test_simple_question_single_subquestion — simple questions route vector-only (F3, F5)."""

from __future__ import annotations

from agents.graph import build_graph

SIMPLE_QUESTION = "What is our data retention policy?"


def test_simple_question_complexity_and_strategy():
    """F3: simple question → complexity=simple, exactly 1 sub-question, strategy=vector."""
    compiled = build_graph()
    state = compiled.invoke(
        {
            "session_id": "test-simple",
            "question": SIMPLE_QUESTION,
            "evidence": [],
            "sub_questions": [],
            "strategies_used": [],
            "corrective_rounds": 0,
            "missing_evidence_keys": [],
            "error": None,
        }
    )

    assert state.get("complexity") == "simple", f"Expected simple, got {state.get('complexity')}"
    sqs = state.get("sub_questions", [])
    assert len(sqs) == 1, f"Expected 1 sub-question, got {len(sqs)}"
    assert sqs[0]["strategy"] == "vector", f"Expected vector, got {sqs[0]['strategy']}"


def test_simple_question_no_sql_no_graph():
    """F5: simple policy question must not trigger sql or graph retrieval."""
    compiled = build_graph()
    state = compiled.invoke(
        {
            "session_id": "test-no-graph",
            "question": SIMPLE_QUESTION,
            "evidence": [],
            "sub_questions": [],
            "strategies_used": [],
            "corrective_rounds": 0,
            "missing_evidence_keys": [],
            "error": None,
        }
    )

    strategies = state.get("strategies_used", [])
    assert "sql" not in strategies, f"SQL should not be used for simple question, got {strategies}"
    assert "graph" not in strategies, (
        f"Graph should not be used for simple question, got {strategies}"
    )


def test_simple_question_has_answer():
    """Simple question produces a non-empty answer string."""
    compiled = build_graph()
    state = compiled.invoke(
        {
            "session_id": "test-answer",
            "question": SIMPLE_QUESTION,
            "evidence": [],
            "sub_questions": [],
            "strategies_used": [],
            "corrective_rounds": 0,
            "missing_evidence_keys": [],
            "error": None,
        }
    )

    assert state.get("answer"), "Answer should not be empty"
