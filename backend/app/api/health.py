from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.health import run_all_checks

router = APIRouter(tags=["health"])


@router.get("/health", status_code=200)
def health() -> dict:
    """Liveness ping — always 200 while the process is up."""
    return {"status": "ok"}


@router.get("/health/live", status_code=200)
def health_live() -> dict:
    """Kubernetes liveness probe — identical to /health."""
    return {"status": "ok"}


@router.get("/health/ready", status_code=200)
def health_ready() -> JSONResponse:
    """
    Readiness probe.  Runs every registered check and returns:
      {"status": "ok"|"degraded"|"error", "checks": {"<name>": {"status": ..., "detail": ...}}}
    Returns HTTP 200 for ok/degraded, 503 for error.
    """
    checks, overall = run_all_checks()
    status_code = 503 if overall == "error" else 200
    return JSONResponse(
        content={"status": overall, "checks": checks},
        status_code=status_code,
    )
