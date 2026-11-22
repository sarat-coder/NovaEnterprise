"""Node: sql_retrieval — run SQL template queries for 'sql' sub-questions."""

from __future__ import annotations

from agents.state import ResearchState


def _build_params(state: ResearchState) -> dict:
    """Build template params from entities and time range in state."""
    entities = state.get("entities", [])
    time_range = state.get("time_range", {})
    service_name = entities[0] if entities else "Payments API"

    params: dict = {"service_name": service_name}

    if time_range.get("label") == "last_quarter":
        # Resolve last_quarter using organizational memory if available
        try:
            from memory.scopes.organizational import resolve_quarter  # noqa: PLC0415

            resolved = resolve_quarter("last quarter")
            params["start_date"] = resolved.get("start_date", "2026-07-01")
            params["end_date"] = resolved.get("end_date", "2026-09-30")
        except Exception:
            params["start_date"] = "2026-07-01"
            params["end_date"] = "2026-09-30"
    elif time_range.get("start_date"):
        params["start_date"] = time_range["start_date"]
        params["end_date"] = time_range.get("end_date", "2026-12-31")

    return params


def sql_retrieval(state: ResearchState) -> ResearchState:
    from rag.sql_retrieval import SqlRetriever  # noqa: PLC0415

    retriever = SqlRetriever()
    new_sqs = []
    new_evidence = list(state.get("evidence", []))
    params = _build_params(state)

    for sq in state.get("sub_questions", []):
        if sq.get("strategy") != "sql":
            new_sqs.append(sq)
            continue
        try:
            # Pick template based on whether we have a date range
            if "start_date" in params and "end_date" in params:
                template = "incidents_by_service_and_date"
            else:
                template = "incidents_by_service"

            results = retriever.retrieve(template, params)
            ids = []
            for ev in results:
                new_evidence.append(ev)
                ids.append(ev.id)
            new_sqs.append({**sq, "status": "completed", "evidence_ids": ids})
        except Exception as exc:
            new_sqs.append({**sq, "status": "error", "error_detail": str(exc)})

    return {**state, "sub_questions": new_sqs, "evidence": new_evidence}
