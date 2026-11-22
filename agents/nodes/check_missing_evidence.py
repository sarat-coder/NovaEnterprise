"""Node: check_missing_evidence — detect sub-questions that have no evidence (F9)."""

from __future__ import annotations

from agents.state import ResearchState


def check_missing_evidence(state: ResearchState) -> ResearchState:
    evidence_ids = {ev.id for ev in state.get("evidence", [])}
    missing: list[str] = []

    for sq in state.get("sub_questions", []):
        sq_ids = sq.get("evidence_ids", [])
        completed_no_evidence = sq.get("status") == "completed" and not any(
            eid in evidence_ids for eid in sq_ids
        )
        if completed_no_evidence or sq.get("status") == "pending":
            missing.append(sq["id"])

    return {**state, "missing_evidence_keys": missing}
