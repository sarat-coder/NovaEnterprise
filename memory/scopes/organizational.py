"""Organizational memory scope — read-only shared company facts.

Loads `sample_data/organizational_memory.json` once and exposes:
  - `get_all()`       → full dict
  - `resolve_quarter(label)` → start/end dates for "last quarter", "this quarter", etc.
  - `get_fact(key)`   → one top-level value

This scope is never written to at runtime. It is read-only by design.
"""

from __future__ import annotations

import functools
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent.parent.parent / "sample_data" / "organizational_memory.json"


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def get_all() -> dict[str, Any]:
    """Return the full organizational memory dict."""
    return _load()


def get_fact(key: str) -> Any | None:
    """Return a top-level fact by key, or None if not found."""
    return _load().get(key)


def resolve_quarter(label: str, reference_date: date | None = None) -> dict[str, Any]:
    """Resolve a human label like 'last quarter' or 'Q3' to start/end dates.

    Returns:
        {
          "quarter": "Q3",
          "label": "July – September",
          "start_date": "2026-07-01",
          "end_date": "2026-09-30",
          "year": 2026,
        }

    Raises ValueError for unrecognised labels.
    """
    if reference_date is None:
        reference_date = datetime.utcnow().date()

    calendar = _load()["fiscal_calendar"]["quarters"]

    current_month = reference_date.month
    # determine current quarter number (1-4)
    current_q = (current_month - 1) // 3 + 1
    current_year = reference_date.year

    normed = label.strip().lower()

    if normed in ("last quarter", "previous quarter"):
        target_q = current_q - 1
        target_year = current_year
        if target_q == 0:
            target_q = 4
            target_year -= 1
    elif normed in ("this quarter", "current quarter"):
        target_q = current_q
        target_year = current_year
    elif normed.startswith("q") and normed[1:].isdigit():
        target_q = int(normed[1:])
        if not 1 <= target_q <= 4:
            raise ValueError(f"Quarter {target_q} out of range 1-4")
        target_year = current_year
    else:
        raise ValueError(f"Unrecognised quarter label: {label!r}")

    q_key = f"Q{target_q}"
    q_info = calendar[q_key]
    start_month = q_info["start_month"]
    end_month = q_info["end_month"]
    # last day of end_month
    if end_month == 12:
        end_day = 31
    else:
        # first day of next month minus one day
        end_day = (date(target_year, end_month + 1, 1) - date(target_year, end_month, 1)).days

    return {
        "quarter": q_key,
        "label": q_info["label"],
        "start_date": f"{target_year}-{start_month:02d}-01",
        "end_date": f"{target_year}-{end_month:02d}-{end_day:02d}",
        "year": target_year,
    }
