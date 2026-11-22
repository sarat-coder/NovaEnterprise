"""Node: hybrid_retrieval — vector + graph for 'hybrid' sub-questions."""

from __future__ import annotations

from agents.state import ResearchState


def hybrid_retrieval(state: ResearchState) -> ResearchState:
    from rag.graph_store import get_graph_store  # noqa: PLC0415
    from rag.retriever import retrieve  # noqa: PLC0415

    store = get_graph_store()
    new_sqs = []
    new_evidence = list(state.get("evidence", []))

    for sq in state.get("sub_questions", []):
        if sq.get("strategy") != "hybrid":
            new_sqs.append(sq)
            continue
        try:
            ids = []

            # Vector portion
            vec_results = retrieve(sq["question"], top_k=4)
            for ev in vec_results:
                new_evidence.append(ev)
                ids.append(ev.id)

            # Graph portion — decisions related to entity
            entity = _first_entity(state)
            graph_results = store.traverse_related_decisions(entity)
            for ev in graph_results:
                new_evidence.append(ev)
                ids.append(ev.id)

            new_sqs.append({**sq, "status": "completed", "evidence_ids": ids})
        except Exception as exc:
            new_sqs.append({**sq, "status": "error", "error_detail": str(exc)})

    return {**state, "sub_questions": new_sqs, "evidence": new_evidence}


def _first_entity(state: ResearchState) -> str:
    entities = state.get("entities", [])
    if entities:
        return entities[0]
    return "Payments API"
