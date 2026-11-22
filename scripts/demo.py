"""Demo script — runs the canonical question (and optionally a custom question) end-to-end.

Usage:
    python scripts/demo.py
    python scripts/demo.py --question "What is our data retention policy?"
"""

from __future__ import annotations

import argparse
import json
import os
import time

# Ensure offline mode
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("GRAPH_STORE", "memory")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/enterprise.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("JWT_SECRET", "demo-secret-not-for-production-use")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

CANONICAL_QUESTION = (
    "Which customers were impacted by the Payments API last quarter, "
    "what incidents occurred, which teams own those services, and what "
    "decisions were taken to prevent recurrence?"
)

BOX_WIDTH = 70


def _hr(char: str = "─") -> str:
    return char * BOX_WIDTH


def _box(title: str, content: str) -> None:
    print(f"\n┌{_hr()}┐")
    print(f"│ {title:<{BOX_WIDTH - 2}} │")
    print(f"├{_hr()}┤")
    for line in content.splitlines():
        # Wrap long lines
        while len(line) > BOX_WIDTH - 4:
            print(f"│  {line[: BOX_WIDTH - 4]}  │")
            line = line[BOX_WIDTH - 4 :]
        print(f"│  {line:<{BOX_WIDTH - 4}}  │")
    print(f"└{_hr()}┘")


def run_demo(question: str) -> None:
    print(f"\n{'=' * BOX_WIDTH}")
    print("  NovaEnterprise — Research Demo")
    print(f"{'=' * BOX_WIDTH}")
    print(f"\nQuestion:\n  {question}\n")

    # Bootstrap the application
    from app.core.db import get_session_factory, init_db  # noqa: PLC0415
    from app.services.seed_service import seed  # noqa: PLC0415
    from rag.graph_seed import seed_graph  # noqa: PLC0415
    from rag.ingest import ingest_all  # noqa: PLC0415

    print("[1/5] Initialising database...")
    init_db()
    factory = get_session_factory()
    with factory() as db:
        seed(db)
        db.commit()

    print("[2/5] Seeding knowledge graph...")
    seed_graph()

    print("[3/5] Ingesting documents...")
    ingest_all()

    print("[4/5] Running research workflow...\n")
    t0 = time.perf_counter()

    from agents.graph import GRAPH_NODES, build_graph  # noqa: PLC0415
    from app.core.observability import WorkflowTracer  # noqa: PLC0415

    events_log: list[dict] = []

    def demo_persist(node: str, event_type: str, payload: dict, duration_ms: float) -> None:
        events_log.append(
            {
                "node": node,
                "event_type": event_type,
                "duration_ms": round(duration_ms, 1),
                **payload,
            }
        )
        status = "✓" if event_type == "transition" else "✗"
        print(f"  {status} {node:<30} {duration_ms:>7.1f} ms")

    tracer = WorkflowTracer(session_id="demo", persist_fn=demo_persist)
    compiled = build_graph(tracer=tracer)

    initial_state = {
        "session_id": "demo",
        "question": question,
        "evidence": [],
        "sub_questions": [],
        "strategies_used": [],
        "corrective_rounds": 0,
        "missing_evidence_keys": [],
        "error": None,
    }

    final_state = compiled.invoke(initial_state)
    elapsed = time.perf_counter() - t0

    print(f"\n[5/5] Complete in {elapsed:.1f}s\n")

    # Print results
    _box(
        "Analysis",
        "\n".join(
            [
                f"Complexity  : {final_state.get('complexity', 'n/a')}",
                f"Intent      : {final_state.get('intent', 'n/a')}",
                f"Entities    : {', '.join(final_state.get('entities', []))}",
                f"Time range  : {json.dumps(final_state.get('time_range', {}))}",
            ]
        ),
    )

    sqs = final_state.get("sub_questions", [])
    if sqs:
        sq_lines = [
            f"  [{sq.get('id')}] strategy={sq.get('strategy'):<8} status={sq.get('status')}"
            for sq in sqs
        ]
        _box("Sub-questions", "\n".join(sq_lines))

    evidence = final_state.get("evidence", [])
    _box(
        "Evidence summary",
        "\n".join(
            [
                f"Items collected  : {len(evidence)}",
                f"Strategies used  : {', '.join(final_state.get('strategies_used', []))}",
                f"Corrective rounds: {final_state.get('corrective_rounds', 0)}",
                f"Citations valid  : {final_state.get('citations_valid', 'n/a')}",
            ]
        ),
    )

    answer = final_state.get("answer", "No answer generated.")
    _box("Answer", answer)

    print(f"\n{'=' * BOX_WIDTH}")
    print(f"  Total nodes: {len(GRAPH_NODES)}  |  Elapsed: {elapsed:.1f}s")
    print(f"{'=' * BOX_WIDTH}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="NovaEnterprise demo")
    parser.add_argument(
        "--question",
        default=CANONICAL_QUESTION,
        help="Research question to run (default: canonical question)",
    )
    args = parser.parse_args()
    run_demo(args.question)


if __name__ == "__main__":
    main()
