"""test_multi_hop_citations_and_grounding — citation integrity (F11, F12)."""

from __future__ import annotations

from agents.nodes.verify_citations import verify_citations
from app.schemas.common import Evidence


def _make_ev(num: int) -> Evidence:
    ev = Evidence(
        id=f"ev-{num}",
        source_type="document",
        locator=f"chunk-{num}",
        content=f"Evidence item {num}.",
    )
    ev.metadata["citation_number"] = num
    return ev


def test_citations_valid_when_all_resolved():
    """F12: all [n] in answer match evidence citation_numbers → citations_valid=True."""
    state = {
        "session_id": "t1",
        "question": "test",
        "answer": "According to [1] and [2] the service was down.",
        "evidence": [_make_ev(1), _make_ev(2)],
    }
    result = verify_citations(state)
    assert result["citations_valid"] is True


def test_citations_invalid_when_reference_missing():
    """F12: a [5] with no matching evidence → citations_valid=False."""
    state = {
        "session_id": "t2",
        "question": "test",
        "answer": "According to [1] and [5] the service was down.",
        "evidence": [_make_ev(1), _make_ev(2)],
    }
    result = verify_citations(state)
    assert result["citations_valid"] is False


def test_no_citations_in_answer():
    """F12: answer with no [n] markers → citations_valid=True (nothing to invalidate)."""
    state = {
        "session_id": "t3",
        "question": "test",
        "answer": "The service was down.",
        "evidence": [_make_ev(1)],
    }
    result = verify_citations(state)
    assert result["citations_valid"] is True


def test_empty_answer_valid():
    """F12: empty answer produces citations_valid=True."""
    state = {
        "session_id": "t4",
        "question": "test",
        "answer": "",
        "evidence": [],
    }
    result = verify_citations(state)
    assert result["citations_valid"] is True
