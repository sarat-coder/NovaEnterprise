"""Pytest wrapper for the evaluation suite (P15-1).

Runs all eval cases offline and asserts that every metric meets its CI
threshold.  A failing eval case lowers the aggregate score and can trip the
threshold, which causes the test to fail.

Requirement: N1 (offline), and all F/N rows via the eval thresholds table in
CLAUDE.md §12.
"""

from __future__ import annotations

import pytest

from tests.evaluation.evaluate import THRESHOLDS, evaluate


@pytest.mark.parametrize("metric,threshold", list(THRESHOLDS.items()))
def test_eval_metric_meets_threshold(metric: str, threshold: float) -> None:
    """Each evaluation metric must meet its CI threshold.

    Running the full eval suite once per parametrize call would be slow; we
    run it once at module level and cache the result.
    """
    scores = _get_scores()
    score = scores[metric]
    assert score >= threshold, (
        f"Metric '{metric}' scored {score:.3f}, below threshold {threshold:.2f}. "
        "A regression in retrieval quality was introduced."
    )


# Module-level cache so the workflow runs once for all parametrize cases.
_cached_scores: dict[str, float] | None = None


def _get_scores() -> dict[str, float]:
    global _cached_scores
    if _cached_scores is None:
        _cached_scores = evaluate(verbose=False)
    return _cached_scores
