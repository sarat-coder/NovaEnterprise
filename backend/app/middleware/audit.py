from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class AuditMiddleware(BaseHTTPMiddleware):
    """Emit a structured audit log entry for every state-changing HTTP request.

    The entry includes method, path, response status and the correlation
    request_id so individual changes can be traced across services.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if request.method in _STATE_CHANGING:
            logger.info(
                "audit",
                extra={
                    "audit": True,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    # Read from the response header: RequestContextMiddleware guarantees
                    # X-Request-ID is set before the response propagates back to us.
                    "request_id": response.headers.get("X-Request-ID", "-"),
                },
            )
        return response
