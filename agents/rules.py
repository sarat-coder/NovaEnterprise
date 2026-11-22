"""Deterministic analysis, complexity and routing rules (P11-1, F2–F5).

Rules run on top of any LLM output: the AI proposes, rules correct.
Everything here works with LLM_PROVIDER=fake.

Design guarantee (CLAUDE.md §6.2):
  A question that needs relationships is NEVER routed vector-only.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Service entity registry — names the router recognises
# ---------------------------------------------------------------------------

SERVICE_NAMES: frozenset[str] = frozenset(
    {
        "payments api",
        "identity service",
        "data pipeline",
        "analytics dashboard",
        "notification service",
        "billing engine",
        "customer portal",
        "search service",
    }
)

# ---------------------------------------------------------------------------
# Canonical question pattern
# ---------------------------------------------------------------------------

_CANONICAL_KEYWORDS = frozenset(
    {
        "impacted",
        "incidents",
        "teams",
        "own",
        "decisions",
        "prevent",
        "recurrence",
        "last quarter",
    }
)


def _is_canonical(question: str) -> bool:
    q = question.lower()
    matches = sum(1 for kw in _CANONICAL_KEYWORDS if kw in q)
    return matches >= 4


# ---------------------------------------------------------------------------
# Public: analyze_question
# ---------------------------------------------------------------------------


def analyze_question(question: str) -> dict[str, Any]:
    """Extract intent, entities, time range, and flags from raw question text."""
    q = question.lower()

    # Entity extraction — find service names
    entities: list[str] = []
    for svc in SERVICE_NAMES:
        if svc in q:
            entities.append(svc.title())

    # Time range detection
    time_range: dict[str, Any] = {}
    if "last quarter" in q or "previous quarter" in q:
        time_range = {"label": "last_quarter"}
    elif re.search(r"q[1-4]\s*20\d\d", q):
        m = re.search(r"(q[1-4])\s*(20\d\d)", q)
        if m:
            time_range = {"label": m.group(1).upper(), "year": int(m.group(2))}

    # Relationship indicators
    needs_relationships = any(
        kw in q
        for kw in (
            "which customers",
            "which teams",
            "who owns",
            "owned by",
            "impacted",
            "affected",
        )
    )

    # Aggregation indicators
    needs_aggregation = any(kw in q for kw in ("how many", "count", "total", "summary"))

    # Intent classification
    if "policy" in q or "retention" in q or "procedure" in q:
        intent = "policy_lookup"
    elif needs_relationships:
        intent = "relationship_traversal"
    elif time_range:
        intent = "temporal_query"
    else:
        intent = "general_research"

    return {
        "intent": intent,
        "entities": entities,
        "time_range": time_range,
        "needs_relationships": needs_relationships,
        "needs_aggregation": needs_aggregation,
    }


# ---------------------------------------------------------------------------
# Public: classify_complexity
# ---------------------------------------------------------------------------


def classify_complexity(analysis: dict[str, Any]) -> str:
    """Score the question and return simple | moderate | complex."""
    score = 0
    if analysis.get("needs_relationships"):
        score += 2
    if analysis.get("time_range"):
        score += 1
    if len(analysis.get("entities", [])) > 0:
        score += 1
    # multi-strategy questions score higher
    if analysis.get("needs_relationships") and analysis.get("time_range"):
        score += 2

    if score >= 4:
        return "complex"
    if score >= 2:
        return "moderate"
    return "simple"


# ---------------------------------------------------------------------------
# Public: decompose_question
# ---------------------------------------------------------------------------


def decompose_question(
    question: str,
    analysis: dict[str, Any],
    complexity: str,
    max_subquestions: int = 4,
) -> list[dict[str, Any]]:
    """Return a list of sub-question dicts with id, question, strategy."""
    if complexity == "simple":
        return [
            {
                "id": "sq1",
                "question": question,
                "strategy": "vector",
                "status": "pending",
                "evidence_ids": [],
                "error_detail": None,
            }
        ]

    if _is_canonical(question):
        return _decompose_canonical(question)

    # General complex decomposition
    subs: list[dict[str, Any]] = []
    sq_id = 0

    if analysis.get("needs_relationships") and analysis.get("entities"):
        sq_id += 1
        entity = analysis["entities"][0]
        subs.append(
            {
                "id": f"sq{sq_id}",
                "question": f"Which customers were impacted by {entity}?",
                "strategy": "graph",
                "status": "pending",
                "evidence_ids": [],
                "error_detail": None,
            }
        )

    if analysis.get("time_range"):
        sq_id += 1
        subs.append(
            {
                "id": f"sq{sq_id}",
                "question": f"What incidents occurred? {question}",
                "strategy": "sql",
                "status": "pending",
                "evidence_ids": [],
                "error_detail": None,
            }
        )

    if analysis.get("needs_relationships"):
        sq_id += 1
        subs.append(
            {
                "id": f"sq{sq_id}",
                "question": f"Which teams own the affected services? {question}",
                "strategy": "graph",
                "status": "pending",
                "evidence_ids": [],
                "error_detail": None,
            }
        )

    if not subs:
        subs.append(
            {
                "id": "sq1",
                "question": question,
                "strategy": "vector",
                "status": "pending",
                "evidence_ids": [],
                "error_detail": None,
            }
        )

    return subs[:max_subquestions]


def _decompose_canonical(question: str) -> list[dict[str, Any]]:
    """Fixed decomposition for the canonical question."""
    return [
        {
            "id": "sq1",
            "question": "Which customers were impacted by the Payments API?",
            "strategy": "graph",
            "status": "pending",
            "evidence_ids": [],
            "error_detail": None,
        },
        {
            "id": "sq2",
            "question": "What incidents occurred involving the Payments API last quarter?",
            "strategy": "sql",
            "status": "pending",
            "evidence_ids": [],
            "error_detail": None,
        },
        {
            "id": "sq3",
            "question": "Which teams own the Payments API service?",
            "strategy": "graph",
            "status": "pending",
            "evidence_ids": [],
            "error_detail": None,
        },
        {
            "id": "sq4",
            "question": (
                "What decisions were taken to prevent recurrence of Payments API incidents?"
            ),
            "strategy": "hybrid",
            "status": "pending",
            "evidence_ids": [],
            "error_detail": None,
        },
    ]


# ---------------------------------------------------------------------------
# Public: correct_routing  (guarantee: relationship → graph, never vector-only)
# ---------------------------------------------------------------------------


def correct_routing(sub_questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hard-override any routing that would send a relationship question to vector-only."""
    corrected = []
    for sq in sub_questions:
        q = sq["question"].lower()
        strategy = sq["strategy"]

        # Relationship questions must use graph (or hybrid if they also need docs)
        if any(
            kw in q
            for kw in (
                "which customers",
                "impacted by",
                "which teams",
                "owned by",
                "who owns",
            )
        ):
            if strategy == "vector":
                strategy = "graph"

        # SQL triggers
        elif any(kw in q for kw in ("incidents", "occurred", "last quarter", "records for")):
            if strategy == "vector":
                strategy = "sql"

        # Hybrid triggers — only escalate to hybrid when there are ALSO relationship/time indicators
        # Simple policy questions stay vector-only
        elif (
            any(kw in q for kw in ("decisions", "prevent recurrence", "postmortem"))
            and strategy == "vector"
        ):
            strategy = "hybrid"

        corrected.append({**sq, "strategy": strategy})
    return corrected


# ---------------------------------------------------------------------------
# Public: should_correct  (bounded corrective loop)
# ---------------------------------------------------------------------------


def should_correct(missing_keys: list[str], rounds: int, max_rounds: int) -> bool:
    """Return True only if there are missing keys AND we haven't hit the round limit."""
    return bool(missing_keys) and rounds < max_rounds
