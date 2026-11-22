"""Node: graph_retrieval — run typed graph traversals for 'graph' sub-questions."""

from __future__ import annotations

from agents.state import ResearchState


def graph_retrieval(state: ResearchState) -> ResearchState:
    from rag.graph_store import get_graph_store  # noqa: PLC0415

    store = get_graph_store()
    new_sqs = []
    new_evidence = list(state.get("evidence", []))

    for sq in state.get("sub_questions", []):
        if sq.get("strategy") != "graph":
            new_sqs.append(sq)
            continue
        try:
            q = sq["question"].lower()
            results = []

            if "customers" in q or "impacted" in q:
                entity = _first_entity(state)
                results = store.traverse_impacted_customers(entity)
            elif "teams" in q or "own" in q or "owned" in q:
                entity = _first_entity(state)
                results = store.traverse_owning_teams(entity)
            else:
                # Generic: get decisions related to entity
                entity = _first_entity(state)
                results = store.traverse_related_decisions(entity)

            ids = []
            for ev in results:
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
