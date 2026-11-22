"""Node: corrective_retrieval — broadened vector search for missing evidence (F9)."""

from __future__ import annotations

from agents.state import ResearchState


def corrective_retrieval(state: ResearchState) -> ResearchState:
    from rag.retriever import retrieve  # noqa: PLC0415

    new_evidence = list(state.get("evidence", []))
    rounds = state.get("corrective_rounds", 0) + 1
    missing = state.get("missing_evidence_keys", [])

    # Find sub-questions that need corrective retrieval
    for sq in state.get("sub_questions", []):
        if sq["id"] not in missing:
            continue
        try:
            # Broadened search: use the original question for broader context
            results = retrieve(state["question"], top_k=3)
            for ev in results:
                if ev.id not in {e.id for e in new_evidence}:
                    new_evidence.append(ev)
        except Exception:
            pass  # degrade silently — workflow continues

    return {**state, "evidence": new_evidence, "corrective_rounds": rounds}
