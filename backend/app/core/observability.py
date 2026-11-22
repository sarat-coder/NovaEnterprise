"""Workflow tracer — wraps every node and writes WorkflowEvents (P12-1, F16).

Usage in agents/graph.py:
    tracer = WorkflowTracer(session_id, persist_fn)
    wrapped_node = tracer.node("analyze_query")(analyze_query)

The persist_fn is injected by the research service so the tracer never
imports the service layer (which would create a cycle).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkflowTracer:
    """Wraps node functions to record timing and persist WorkflowEvent rows."""

    def __init__(
        self,
        session_id: str,
        persist_fn: Callable[[str, str, dict[str, Any], float], None] | None = None,
    ) -> None:
        self._session_id = session_id
        self._persist = persist_fn or _noop

    def node(self, node_name: str) -> Callable:
        """Decorator factory: tracer.node("analyze_query")(fn) → wrapped fn."""

        def decorator(fn: Callable) -> Callable:
            def wrapped(state: Any) -> Any:
                logger.info(
                    "node_start",
                    extra={"session_id": self._session_id, "node": node_name},
                )
                t0 = time.perf_counter()
                try:
                    result = fn(state)
                    duration_ms = (time.perf_counter() - t0) * 1000
                    payload = _safe_payload(result, node_name)
                    self._persist(node_name, "transition", payload, duration_ms)
                    logger.info(
                        "node_complete",
                        extra={
                            "session_id": self._session_id,
                            "node": node_name,
                            "duration_ms": round(duration_ms, 1),
                        },
                    )
                    return result
                except Exception as exc:
                    duration_ms = (time.perf_counter() - t0) * 1000
                    self._persist(
                        node_name,
                        "error",
                        {"error": str(exc)},
                        duration_ms,
                    )
                    logger.error(
                        "node_error",
                        extra={
                            "session_id": self._session_id,
                            "node": node_name,
                            "error": str(exc),
                        },
                    )
                    raise

            wrapped.__name__ = fn.__name__
            return wrapped

        return decorator


def _noop(*args: Any, **kwargs: Any) -> None:
    pass


def _safe_payload(state: Any, node_name: str) -> dict[str, Any]:
    """Extract a small, safe summary from state for the event payload."""
    if not isinstance(state, dict):
        return {"node": node_name}

    payload: dict[str, Any] = {}

    if "complexity" in state:
        payload["complexity"] = state["complexity"]
    if "strategies_used" in state:
        payload["strategies_used"] = state.get("strategies_used", [])
    if "sub_questions" in state:
        sqs = state["sub_questions"]
        payload["sub_question_count"] = len(sqs)
        payload["sub_questions"] = [
            {"id": sq.get("id"), "strategy": sq.get("strategy"), "status": sq.get("status")}
            for sq in sqs
        ]
    if "evidence" in state:
        payload["evidence_count"] = len(state["evidence"])
    if "missing_evidence_keys" in state:
        payload["missing_evidence_keys"] = state["missing_evidence_keys"]
    if "corrective_rounds" in state:
        payload["corrective_rounds"] = state["corrective_rounds"]
    if "citations_valid" in state:
        payload["citations_valid"] = state["citations_valid"]
    if "answer" in state and state.get("answer"):
        payload["answer_length"] = len(state["answer"])

    return payload
