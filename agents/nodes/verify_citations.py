"""Node: verify_citations — confirm every [n] in the answer resolves to evidence (F12)."""

from __future__ import annotations

import re

from agents.state import ResearchState


def verify_citations(state: ResearchState) -> ResearchState:
    answer = state.get("answer", "")
    evidence = state.get("evidence", [])

    valid_numbers = {ev.metadata.get("citation_number") for ev in evidence}

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    invalid = cited - valid_numbers

    return {**state, "citations_valid": len(invalid) == 0}
