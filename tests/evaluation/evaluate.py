"""Evaluation runner for NovaEnterprise retrieval quality metrics.

Runs offline against the fake LLM and memory stores.  Every metric has a CI
threshold defined in THRESHOLDS; the script exits with code 1 if any threshold
is not met, so the CI eval gate job fails on regression.

Usage:
    uv run python -m tests.evaluation.evaluate
    # or via Makefile once the target is wired up:
    make evaluate
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Offline environment — must be set before any app import
# ---------------------------------------------------------------------------
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("GRAPH_STORE", "memory")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/eval.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("JWT_SECRET", "eval-runner-secret-32-characters!!")

# ---------------------------------------------------------------------------
# CI thresholds — never weaken to make a test pass
# ---------------------------------------------------------------------------
THRESHOLDS: dict[str, float] = {
    "retrieval_relevance": 0.80,
    "sql_correctness": 1.00,
    "graph_correctness": 1.00,
    "multi_hop_coverage": 0.66,
    "citation_support": 1.00,
    "answer_grounding": 0.50,
}

DATASETS_DIR = Path(__file__).parent.parent.parent / "datasets"
EVAL_CASES_PATH = DATASETS_DIR / "eval_cases.json"


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def _load_eval_cases() -> list[dict[str, Any]]:
    with EVAL_CASES_PATH.open() as f:
        return json.load(f)


def _score_retrieval_relevance(
    evidence: list[dict[str, Any]], ground_truth: dict[str, Any]
) -> float:
    """Fraction of expected document ids found in retrieved evidence."""
    expected_docs = set(ground_truth.get("relevant_doc_ids", []))
    if not expected_docs:
        return 1.0
    found = sum(
        1
        for e in evidence
        if any(
            doc_id in e.get("locator", "") or doc_id in e.get("content", "")
            for doc_id in expected_docs
        )
    )
    return min(found / len(expected_docs), 1.0)


def _score_sql_correctness(evidence: list[dict[str, Any]], ground_truth: dict[str, Any]) -> float:
    """1.0 if all required SQL tables appear in SQL evidence, else 0.0."""
    required_tables = ground_truth.get("relevant_sql_tables", [])
    if not required_tables:
        return 1.0
    sql_evidence = [e for e in evidence if e.get("source_type") == "sql"]
    if not sql_evidence:
        return 0.0
    sql_text = " ".join(e.get("content", "") + e.get("locator", "") for e in sql_evidence).lower()
    return 1.0 if all(t.lower() in sql_text for t in required_tables) else 0.0


def _score_graph_correctness(evidence: list[dict[str, Any]], ground_truth: dict[str, Any]) -> float:
    """1.0 if all required graph traversal types appear in graph evidence."""
    required_traversals = ground_truth.get("relevant_graph_traversals", [])
    if not required_traversals:
        return 1.0
    graph_evidence = [e for e in evidence if e.get("source_type") == "graph"]
    if not graph_evidence:
        return 0.0
    graph_text = " ".join(
        e.get("content", "") + e.get("locator", "") for e in graph_evidence
    ).lower()
    matches = sum(
        1
        for t in required_traversals
        if t.replace("_", " ").lower() in graph_text or t.lower() in graph_text
    )
    return matches / len(required_traversals)


def _score_multi_hop_coverage(result: dict[str, Any], expected: dict[str, Any]) -> float:
    """Fraction of expected strategies actually used."""
    expected_strategies = set(expected.get("strategies", []))
    if not expected_strategies:
        return 1.0
    used_strategies = set(result.get("strategies_used", []))
    hit = expected_strategies & used_strategies
    return len(hit) / len(expected_strategies)


def _score_citation_support(result: dict[str, Any], evidence: list[dict[str, Any]]) -> float:
    """1.0 if citations_valid is true and answer contains at least one [n] marker."""
    if not result.get("citations_valid", False):
        return 0.0
    answer = result.get("answer", "")
    import re

    markers = re.findall(r"\[\d+\]", answer)
    return 1.0 if markers else 0.0


def _score_answer_grounding(result: dict[str, Any], expected: dict[str, Any]) -> float:
    """Check that expected entities appear in the answer."""
    must_entities = expected.get("must_contain_entities", [])
    if not must_entities:
        return 1.0
    answer = result.get("answer", "").lower()
    found = sum(1 for e in must_entities if e.lower() in answer)
    return found / len(must_entities)


# ---------------------------------------------------------------------------
# Research runner
# ---------------------------------------------------------------------------


def _run_research(question: str) -> dict[str, Any]:
    """Run the research workflow offline and return the final state."""
    from app.core.db import get_session_factory, init_db
    from app.services.research_service import ResearchService

    init_db()
    factory = get_session_factory()

    with factory() as session:
        svc = ResearchService(session)
        import asyncio

        async def _run() -> str:
            session_id = await svc.create_session(question, user_id="eval-runner")
            await svc.start_research(session_id)
            return session_id

        session_id = asyncio.run(_run())

        with factory() as s2:
            svc2 = ResearchService(s2)
            import asyncio as aio

            async def _get() -> dict[str, Any]:
                return await svc2.get_session(session_id)

            session_data = aio.run(_get())

    return session_data


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------


def evaluate(verbose: bool = True) -> dict[str, float]:
    cases = _load_eval_cases()

    totals: dict[str, list[float]] = {k: [] for k in THRESHOLDS}

    for case in cases:
        cid = case["id"]
        question = case["question"]
        expected = case.get("expected", {})
        ground_truth = case.get("ground_truth", {})

        if verbose:
            print(f"\n[{cid}] {question[:60]}...")

        try:
            result = _run_research(question)
        except Exception as exc:
            if verbose:
                print(f"  ERROR: {exc}")
            # Failed case gets zero for all metrics
            for k in totals:
                totals[k].append(0.0)
            continue

        evidence: list[dict[str, Any]] = [
            e if isinstance(e, dict) else e.model_dump() for e in result.get("evidence", [])
        ]

        rr = _score_retrieval_relevance(evidence, ground_truth)
        sc = _score_sql_correctness(evidence, ground_truth)
        gc = _score_graph_correctness(evidence, ground_truth)
        mh = _score_multi_hop_coverage(result, expected)
        cs = _score_citation_support(result, evidence)
        ag = _score_answer_grounding(result, expected)

        totals["retrieval_relevance"].append(rr)
        totals["sql_correctness"].append(sc)
        totals["graph_correctness"].append(gc)
        totals["multi_hop_coverage"].append(mh)
        totals["citation_support"].append(cs)
        totals["answer_grounding"].append(ag)

        if verbose:
            print(f"  retrieval_relevance={rr:.2f}  sql={sc:.2f}  graph={gc:.2f}")
            print(f"  multi_hop={mh:.2f}  citation={cs:.2f}  grounding={ag:.2f}")

    scores = {k: (sum(v) / len(v) if v else 0.0) for k, v in totals.items()}
    return scores


def _print_report(scores: dict[str, float]) -> bool:
    print("\n" + "=" * 60)
    print("Evaluation report")
    print("=" * 60)
    all_pass = True
    for metric, score in scores.items():
        threshold = THRESHOLDS[metric]
        status = "PASS" if score >= threshold else "FAIL"
        if score < threshold:
            all_pass = False
        print(f"  {metric:<25} {score:.3f}  (threshold {threshold:.2f})  [{status}]")
    print("=" * 60)
    print("Result:", "ALL PASS" if all_pass else "THRESHOLD FAILURE")
    return all_pass


if __name__ == "__main__":
    scores = evaluate(verbose=True)
    passed = _print_report(scores)
    sys.exit(0 if passed else 1)
