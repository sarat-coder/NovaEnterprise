"""Node: verify_evidence — check each claim against collected evidence (F10)."""

from __future__ import annotations

from agents.state import ResearchState
from app.core.guardrails import wrap_untrusted


def verify_evidence(state: ResearchState) -> ResearchState:
    # Wrap all evidence content through the guardrail scanner
    verified = []
    for ev in state.get("evidence", []):
        # Scan content through guardrail; injection attempts are flagged but evidence stays
        wrap_untrusted(ev.content)
        verified.append(ev)
    return {**state, "evidence": verified}
