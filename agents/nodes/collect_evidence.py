"""Node: collect_evidence — merge + deduplicate evidence and assign citation numbers."""

from __future__ import annotations

from agents.state import ResearchState
from app.schemas.common import Evidence


def collect_evidence(state: ResearchState) -> ResearchState:
    seen: dict[str, Evidence] = {}
    for ev in state.get("evidence", []):
        if ev.id not in seen:
            seen[ev.id] = ev

    deduped = list(seen.values())

    # Assign sequential citation_number via metadata
    for idx, ev in enumerate(deduped, start=1):
        ev.metadata["citation_number"] = idx

    # Collect all strategies used
    strategies: set[str] = set()
    for sq in state.get("sub_questions", []):
        if sq.get("status") == "completed":
            strategies.add(sq.get("strategy", "vector"))

    return {
        **state,
        "evidence": deduped,
        "strategies_used": sorted(strategies),
    }
