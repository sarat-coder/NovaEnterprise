"""Research service — create session, run workflow in background, persist after each node (P12-3).

Design rules:
- Never import from app.api (no HTTP types here).
- The graph runs in-process via BackgroundTasks for v1.
- State is persisted to the DB after every node via the tracer's persist_fn.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.core.observability import WorkflowTracer
from app.models.research import ResearchSession, WorkflowEvent
from app.repositories.research_repo import ResearchRepository
from app.schemas.common import Evidence

logger = get_logger(__name__)


class ResearchService:
    """Orchestrates the research workflow and persists its state."""

    def create_session(self, question: str, user_id: str | None = None) -> str:
        """Create a new research session row and return the session_id."""
        session_id = str(uuid.uuid4())
        factory = get_session_factory()
        with factory() as db:
            repo = ResearchRepository(db)
            session = ResearchSession(
                id=session_id,
                question=question,
                status="running",
                user_id=user_id,
                started_at=datetime.utcnow(),
            )
            repo.create_session(session)
            db.commit()
        return session_id

    def start_research(self, session_id: str, question: str) -> None:
        """Run the full research workflow synchronously (called from BackgroundTasks)."""
        factory = get_session_factory()

        def persist_fn(
            node: str, event_type: str, payload: dict[str, Any], duration_ms: float
        ) -> None:
            with factory() as db:
                repo = ResearchRepository(db)
                event = WorkflowEvent(
                    session_id=session_id,
                    node=node,
                    event_type=event_type,
                    payload=json.dumps(payload),
                    duration_ms=duration_ms,
                    occurred_at=datetime.utcnow(),
                )
                repo.add_event(event)
                db.commit()

        tracer = WorkflowTracer(session_id=session_id, persist_fn=persist_fn)

        try:
            from agents.graph import build_graph  # noqa: PLC0415

            compiled = build_graph(tracer=tracer)

            initial_state = {
                "session_id": session_id,
                "question": question,
                "evidence": [],
                "sub_questions": [],
                "strategies_used": [],
                "corrective_rounds": 0,
                "missing_evidence_keys": [],
                "error": None,
            }

            final_state = compiled.invoke(initial_state)
            self._persist_final(session_id, final_state)

        except Exception as exc:
            logger.error(
                "research_workflow_error",
                extra={"session_id": session_id, "error": str(exc)},
            )
            self._persist_error(session_id, str(exc))

    def _persist_final(self, session_id: str, state: dict[str, Any]) -> None:
        factory = get_session_factory()
        with factory() as db:
            repo = ResearchRepository(db)
            session = repo.get_session(session_id)
            if session is None:
                return
            evidence: list[Evidence] = state.get("evidence", [])
            answer = state.get("answer", "")
            # Count [n] citations in answer
            import re  # noqa: PLC0415

            citation_count = len(re.findall(r"\[\d+\]", answer or ""))

            session.status = "completed"
            session.complexity = state.get("complexity")
            session.strategies_used = json.dumps(state.get("strategies_used", []))
            session.answer = answer
            session.evidence_count = len(evidence)
            session.citation_count = citation_count
            session.corrective_rounds = state.get("corrective_rounds", 0)
            session.completed_at = datetime.utcnow()
            session.error = state.get("error")

            repo.update_session(session)
            db.commit()

    def _persist_error(self, session_id: str, error: str) -> None:
        factory = get_session_factory()
        with factory() as db:
            repo = ResearchRepository(db)
            session = repo.get_session(session_id)
            if session is None:
                return
            session.status = "error"
            session.error = error
            session.completed_at = datetime.utcnow()
            repo.update_session(session)
            db.commit()

    def get_session(self, session_id: str) -> ResearchSession | None:
        factory = get_session_factory()
        with factory() as db:
            repo = ResearchRepository(db)
            return repo.get_session(session_id)

    def get_events(self, session_id: str) -> list[WorkflowEvent]:
        factory = get_session_factory()
        with factory() as db:
            repo = ResearchRepository(db)
            return repo.get_events(session_id)


_service: ResearchService | None = None


def get_research_service() -> ResearchService:
    global _service
    if _service is None:
        _service = ResearchService()
    return _service
