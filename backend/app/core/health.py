from __future__ import annotations

from collections.abc import Callable

# Registry: name → sync callable that returns {"status": str, "detail": str}
CheckFn = Callable[[], dict[str, str]]
_registry: dict[str, CheckFn] = {}


def register_check(name: str, fn: CheckFn) -> None:
    """Register a readiness check under *name*. Called once during lifespan."""
    _registry[name] = fn


def run_all_checks() -> tuple[dict[str, dict[str, str]], str]:
    """Run every registered check; return (checks_dict, overall_status)."""
    results: dict[str, dict[str, str]] = {}
    overall = "ok"
    for name, fn in _registry.items():
        try:
            result = fn()
        except Exception as exc:
            result = {"status": "error", "detail": str(exc)}
        results[name] = result
        if result.get("status") == "error":
            overall = "error"
        elif result.get("status") == "degraded" and overall != "error":
            overall = "degraded"
    return results, overall
