"""test_corrective_retrieval_triggers_for_unanswerable_part — bounded loop (F9)."""

from __future__ import annotations

from agents.rules import should_correct


def test_should_correct_when_missing_and_under_limit():
    """F9: corrective retrieval triggers when there are missing keys and rounds < max."""
    assert should_correct(["sq1"], rounds=0, max_rounds=1) is True


def test_should_not_correct_when_no_missing():
    """F9: no corrective retrieval when all sub-questions have evidence."""
    assert should_correct([], rounds=0, max_rounds=1) is False


def test_should_not_correct_when_at_limit():
    """F9 / N4: corrective retrieval stops at MAX_CORRECTIVE_ROUNDS."""
    assert should_correct(["sq1"], rounds=1, max_rounds=1) is False


def test_corrective_loop_bounded_in_workflow():
    """F9: running the full graph never exceeds corrective_rounds=1."""
    from agents.graph import build_graph  # noqa: PLC0415

    compiled = build_graph()
    # Use a question unlikely to have good evidence so corrective may trigger
    state = compiled.invoke(
        {
            "session_id": "test-corrective",
            "question": "What happened to the xyz123 nonexistent service last decade?",
            "evidence": [],
            "sub_questions": [],
            "strategies_used": [],
            "corrective_rounds": 0,
            "missing_evidence_keys": [],
            "error": None,
        }
    )
    assert state.get("corrective_rounds", 0) <= 1, (
        f"Corrective rounds exceeded 1: {state.get('corrective_rounds')}"
    )
