from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Echo or generate a request correlation id.
    - If the client sends X-Request-ID, echo it.
    - Otherwise generate a UUID4.
    - Set the id into the request_id_var ContextVar so JSON logs pick it up.
    - Add the id to every response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get(HEADER) or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[HEADER] = req_id
        return response
