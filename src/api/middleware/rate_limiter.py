"""Redis-backed rate limiter: per-user + global LLM semaphore.

Three levels:
  1. Per-User Per-Minute (default: 30 req/min)
  2. Per-User Per-Hour (default: 500 req/hr)
  3. Global LLM Semaphore (primary max 2, router max 10)

Graceful degradation: falls back to in-process counters when Redis is unavailable.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger("chipwise.rate_limiter")


class RateLimiter:
    """Token-bucket rate limiter backed by Redis with in-process fallback."""

    def __init__(
        self,
        redis: Any | None,
        per_minute: int = 30,
        per_hour: int = 500,
        llm_primary_concurrent: int = 2,
        llm_router_concurrent: int = 10,
    ):
        self.redis = redis
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.llm_primary_concurrent = llm_primary_concurrent
        self.llm_router_concurrent = llm_router_concurrent

        # In-process fallback counters
        self._local_minute: dict[str, list[float]] = defaultdict(list)
        self._local_hour: dict[str, list[float]] = defaultdict(list)
        self._local_slots: set[str] = set()

    async def check_rate_limit(self, user_id: str) -> tuple[bool, int]:
        """Check per-user rate limits.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        if self.redis is not None:
            try:
                return await self._check_redis(user_id)
            except Exception as exc:
                logger.warning("Redis rate limit check failed, using local fallback: %s", exc)

        return self._check_local(user_id)

    async def _check_redis(self, user_id: str) -> tuple[bool, int]:
        """Redis-backed rate limit check using INCR + EXPIRE."""
        now = int(time.time())

        # Level 1: per-minute
        minute_key = f"ratelimit:{user_id}:minute:{now // 60}"
        count = await self.redis.incr(minute_key)
        if count == 1:
            await self.redis.expire(minute_key, 60)
        if count > self.per_minute:
            ttl = await self.redis.ttl(minute_key)
            return False, max(ttl, 1)

        # Level 2: per-hour
        hour_key = f"ratelimit:{user_id}:hour:{now // 3600}"
        count = await self.redis.incr(hour_key)
        if count == 1:
            await self.redis.expire(hour_key, 3600)
        if count > self.per_hour:
            ttl = await self.redis.ttl(hour_key)
            return False, max(ttl, 1)

        return True, 0

    def _check_local(self, user_id: str) -> tuple[bool, int]:
        """In-process fallback rate limit check."""
        now = time.time()

        # Clean old entries and check minute limit
        self._local_minute[user_id] = [
            t for t in self._local_minute[user_id] if now - t < 60
        ]
        if len(self._local_minute[user_id]) >= self.per_minute:
            if self._local_minute[user_id]:
                oldest = self._local_minute[user_id][0]
                return False, int(60 - (now - oldest)) + 1
            return False, 60

        # Check hour limit
        self._local_hour[user_id] = [
            t for t in self._local_hour[user_id] if now - t < 3600
        ]
        if len(self._local_hour[user_id]) >= self.per_hour:
            if self._local_hour[user_id]:
                oldest = self._local_hour[user_id][0]
                return False, int(3600 - (now - oldest)) + 1
            return False, 3600

        self._local_minute[user_id].append(now)
        self._local_hour[user_id].append(now)
        return True, 0

    async def acquire_llm_slot(
        self,
        request_id: str,
        model_type: str = "primary",
        timeout: float = 30.0,
    ) -> bool:
        """Acquire a global LLM concurrency slot.

        Args:
            request_id: Unique request identifier.
            model_type: "primary" or "router".
            timeout: Max seconds to wait for a slot.

        Returns:
            True if slot acquired, False if timeout reached.
        """
        max_concurrent = (
            self.llm_primary_concurrent
            if model_type == "primary"
            else self.llm_router_concurrent
        )
        sem_key = f"ratelimit:llm:{model_type}:semaphore"
        slot_ttl = int(timeout) + 30  # Auto-expire slots for crash recovery

        if self.redis is not None:
            try:
                return await self._acquire_redis_slot(
                    sem_key, request_id, max_concurrent, timeout, slot_ttl
                )
            except Exception as exc:
                logger.warning("Redis semaphore failed, using local fallback: %s", exc)

        return self._acquire_local_slot(request_id, max_concurrent)

    async def _acquire_redis_slot(
        self,
        sem_key: str,
        request_id: str,
        max_concurrent: int,
        timeout: float,
        slot_ttl: int,
    ) -> bool:
        """Redis SADD-based semaphore with TTL auto-cleanup."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            current = await self.redis.scard(sem_key)
            if current < max_concurrent:
                await self.redis.sadd(sem_key, request_id)
                await self.redis.expire(sem_key, slot_ttl)
                return True
            await _async_sleep(0.5)
        return False

    def _acquire_local_slot(self, request_id: str, max_concurrent: int) -> bool:
        """In-process fallback semaphore."""
        if len(self._local_slots) < max_concurrent:
            self._local_slots.add(request_id)
            return True
        return False

    async def release_llm_slot(
        self, request_id: str, model_type: str = "primary"
    ) -> None:
        """Release a global LLM concurrency slot."""
        sem_key = f"ratelimit:llm:{model_type}:semaphore"
        if self.redis is not None:
            try:
                await self.redis.srem(sem_key, request_id)
                return
            except Exception as exc:
                logger.warning("Redis semaphore release failed: %s", exc)

        self._local_slots.discard(request_id)


async def _async_sleep(seconds: float) -> None:
    """Async sleep wrapper."""
    import asyncio

    await asyncio.sleep(seconds)


# ── ASGI Middleware ─────────────────────────────────────────────────


class RateLimitMiddleware:
    """ASGI middleware that enforces rate limits on incoming requests."""

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/readiness", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app: Any, rate_limiter: RateLimiter):
        self.app = app
        self.limiter = rate_limiter

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        # Extract user_id from scope (set by auth middleware)
        user_id = "anonymous"
        # In a real setup, user_id would come from JWT claims via request.state
        # For now, use a header or default
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-user-id":
                user_id = header_value.decode()
                break

        allowed, retry_after = await self.limiter.check_rate_limit(user_id)

        if not allowed:
            import json

            body = json.dumps({
                "error": "Rate limit exceeded",
                "detail": f"Too many requests. Retry after {retry_after}s.",
                "retry_after": retry_after,
            }).encode()

            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"retry-after", str(retry_after).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await self.app(scope, receive, send)
