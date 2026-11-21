from __future__ import annotations

import json
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.redis_client import get_redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP.

    Each (IP, minute-window) bucket is an atomic counter in Redis.  When the
    counter exceeds RATE_LIMIT_PER_MINUTE the request receives 429.  The key
    expires after 60 seconds so the window rolls naturally.  If Redis is
    unavailable the request is allowed through rather than blocking all traffic.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        limit = settings.rate_limit_per_minute
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"rl:{client_ip}:{window}"

        try:
            redis = get_redis_client()
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, 60)
            if count > limit:
                body = json.dumps({"detail": "Rate limit exceeded. Try again next minute."})
                return Response(content=body, status_code=429, media_type="application/json")
        except Exception:  # noqa: BLE001
            pass

        return await call_next(request)
