from __future__ import annotations

import functools

from app.core.health import register_check
from app.core.logging import get_logger

logger = get_logger(__name__)


@functools.lru_cache(maxsize=1)
def _get_redis_and_detail():
    """Return (client, detail_string). Cached after first call."""
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if settings.redis_url:
        import redis as redis_lib  # noqa: PLC0415

        client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
        detail = "real"
    else:
        import fakeredis  # noqa: PLC0415

        client = fakeredis.FakeRedis(decode_responses=True)
        detail = "fakeredis"
    return client, detail


def get_redis_client():
    """Return the Redis (or fakeredis) client."""
    client, _ = _get_redis_and_detail()
    return client


def register_redis_check() -> None:
    """Register the Redis readiness check with the health registry."""

    def _check() -> dict:
        try:
            client, detail = _get_redis_and_detail()
            client.ping()
            return {"status": "ok", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)}

    register_check("redis", _check)


def reset_redis_cache() -> None:
    """Clear the lru_cache so the next call picks up updated settings. Use in tests only."""
    _get_redis_and_detail.cache_clear()
