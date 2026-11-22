"""Node: vector_retrieval — run hybrid vector search for 'vector' sub-questions."""

from __future__ import annotations

from agents.state import ResearchState


def vector_retrieval(state: ResearchState) -> ResearchState:
    from rag.retriever import retrieve  # noqa: PLC0415

    new_sqs = []
    new_evidence = list(state.get("evidence", []))

    for sq in state.get("sub_questions", []):
        if sq.get("strategy") != "vector":
            new_sqs.append(sq)
            continue
        try:
            results = retrieve(sq["question"], top_k=5)
            ids = []
            for ev in results:
                new_evidence.append(ev)
                ids.append(ev.id)
            new_sqs.append({**sq, "status": "completed", "evidence_ids": ids})
        except Exception as exc:
            new_sqs.append({**sq, "status": "error", "error_detail": str(exc)})

    return {**state, "sub_questions": new_sqs, "evidence": new_evidence}
