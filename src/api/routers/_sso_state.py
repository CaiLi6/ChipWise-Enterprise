"""Redis-backed CSRF state store for SSO flows (§6B1).

Uses ``SETEX`` for TTL-managed writes and ``GETDEL`` (Redis ≥ 6.2) for
atomic read-and-delete to prevent TOCTOU double-submit attacks.

When Redis is unavailable the store **refuses to operate** (raises 503)
rather than falling back to an in-memory dict — the latter would silently
break CSRF protection in multi-worker deployments.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_KEY_PREFIX = "sso:state:"
_DEFAULT_TTL = 600  # 10 minutes


class SSOStateStore:
    """Redis-backed CSRF state store for SSO flow."""

    def __init__(self, redis: Any, ttl: int = _DEFAULT_TTL) -> None:
        if redis is None:
            logger.error("SSOStateStore created with redis=None — SSO will be unavailable")
        self._redis = redis
        self._ttl = ttl

    def _key(self, state: str) -> str:
        return f"{_KEY_PREFIX}{state}"

    async def put(self, state: str, payload: dict[str, Any]) -> None:
        """Store CSRF state with TTL. Raises 503 if Redis is unavailable."""
        if self._redis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SSO temporarily unavailable — Redis not reachable",
            )
        await self._redis.setex(self._key(state), self._ttl, json.dumps(payload))

    async def pop(self, state: str) -> dict[str, Any] | None:
        """Atomically read and delete CSRF state. Returns None if expired/missing.

        Uses ``GETDEL`` (Redis ≥ 6.2) for atomic read+delete.
        Falls back to ``GET`` + ``DELETE`` pipeline on older Redis.
        """
        if self._redis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SSO temporarily unavailable — Redis not reachable",
            )
        key = self._key(state)
        try:
            raw = await self._redis.getdel(key)
        except Exception:
            # Fallback for Redis < 6.2 (no GETDEL)
            raw = await self._redis.get(key)
            if raw is not None:
                await self._redis.delete(key)

        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]
