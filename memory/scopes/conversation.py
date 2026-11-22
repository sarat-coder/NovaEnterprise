"""Conversation memory scope — per-session turn history in Redis / fakeredis.

Each session gets a Redis list key:  `conv:{session_id}`
Each entry is a JSON object: {"role": "user"|"assistant", "content": str, "ts": ISO8601}

TTL defaults to 24 h so stale sessions don't accumulate indefinitely.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

_DEFAULT_TTL = 86_400  # 24 h in seconds
_KEY_PREFIX = "conv:"


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def add_turn(
    redis_client: Any,
    session_id: str,
    role: str,
    content: str,
    *,
    ttl: int = _DEFAULT_TTL,
) -> None:
    """Append one turn to the conversation history."""
    entry = json.dumps(
        {"role": role, "content": content, "ts": datetime.now(UTC).isoformat()},
        ensure_ascii=False,
    )
    key = _key(session_id)
    redis_client.rpush(key, entry)
    redis_client.expire(key, ttl)


def get_turns(redis_client: Any, session_id: str) -> list[dict[str, str]]:
    """Return all turns for a session in insertion order."""
    raw = redis_client.lrange(_key(session_id), 0, -1)
    return [json.loads(item) for item in raw]


def clear(redis_client: Any, session_id: str) -> None:
    """Delete the conversation history for a session."""
    redis_client.delete(_key(session_id))
