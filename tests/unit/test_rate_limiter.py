"""Unit tests for rate limiter — Redis is mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.api.middleware.rate_limiter import RateLimiter, RateLimitMiddleware

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    """AsyncMock Redis client."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=30)
    redis.scard = AsyncMock(return_value=0)
    redis.sadd = AsyncMock()
    redis.srem = AsyncMock()
    return redis


@pytest.fixture
def limiter(mock_redis):
    return RateLimiter(redis=mock_redis, per_minute=5, per_hour=20)


@pytest.fixture
def local_limiter():
    """Rate limiter without Redis (local fallback)."""
    return RateLimiter(redis=None, per_minute=3, per_hour=10)


# ── Per-user rate limits (Redis) ────────────────────────────────────


@pytest.mark.unit
class TestRedisRateLimit:
    @pytest.mark.asyncio
    async def test_first_request_allowed(self, limiter, mock_redis) -> None:
        mock_redis.incr.return_value = 1
        allowed, retry = await limiter.check_rate_limit("user1")
        assert allowed is True
        assert retry == 0

    @pytest.mark.asyncio
    async def test_exceeds_minute_limit(self, limiter, mock_redis) -> None:
        # Simulate 6th request (limit is 5)
        call_count = 0

        async def incr_side_effect(key):
            nonlocal call_count
            call_count += 1
            if "minute" in key:
                return 6  # Over limit
            return 1

        mock_redis.incr.side_effect = incr_side_effect
        allowed, retry = await limiter.check_rate_limit("user1")
        assert allowed is False
        assert retry > 0

    @pytest.mark.asyncio
    async def test_exceeds_hour_limit(self, limiter, mock_redis) -> None:
        async def incr_side_effect(key):
            if "minute" in key:
                return 3  # Under minute limit
            if "hour" in key:
                return 21  # Over hour limit
            return 1

        mock_redis.incr.side_effect = incr_side_effect
        allowed, retry = await limiter.check_rate_limit("user1")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_redis_failure_fallback(self, limiter, mock_redis) -> None:
        """When Redis fails, fallback to local counter."""
        mock_redis.incr.side_effect = ConnectionError("Redis down")
        allowed, retry = await limiter.check_rate_limit("user1")
        assert allowed is True  # Local fallback allows first request


# ── Local fallback rate limits ──────────────────────────────────────


@pytest.mark.unit
class TestLocalRateLimit:
    @pytest.mark.asyncio
    async def test_first_request_allowed(self, local_limiter) -> None:
        allowed, retry = await local_limiter.check_rate_limit("user1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_exceeds_local_minute_limit(self, local_limiter) -> None:
        for _ in range(3):
            await local_limiter.check_rate_limit("user1")
        allowed, retry = await local_limiter.check_rate_limit("user1")
        assert allowed is False
        assert retry > 0

    @pytest.mark.asyncio
    async def test_different_users_independent(self, local_limiter) -> None:
        for _ in range(3):
            await local_limiter.check_rate_limit("user1")
        # user2 should still be allowed
        allowed, _ = await local_limiter.check_rate_limit("user2")
        assert allowed is True


# ── LLM semaphore ───────────────────────────────────────────────────


@pytest.mark.unit
class TestLLMSemaphore:
    @pytest.mark.asyncio
    async def test_acquire_slot(self, limiter, mock_redis) -> None:
        mock_redis.scard.return_value = 0
        ok = await limiter.acquire_llm_slot("req-1", "primary")
        assert ok is True
        mock_redis.sadd.assert_awaited()

    @pytest.mark.asyncio
    async def test_release_slot(self, limiter, mock_redis) -> None:
        await limiter.release_llm_slot("req-1", "primary")
        mock_redis.srem.assert_awaited()

    @pytest.mark.asyncio
    async def test_local_semaphore_limit(self) -> None:
        limiter = RateLimiter(redis=None, llm_primary_concurrent=2)
        assert limiter._acquire_local_slot("r1", 2) is True
        assert limiter._acquire_local_slot("r2", 2) is True
        assert limiter._acquire_local_slot("r3", 2) is False  # Full

    @pytest.mark.asyncio
    async def test_local_semaphore_release(self) -> None:
        limiter = RateLimiter(redis=None, llm_primary_concurrent=2)
        limiter._acquire_local_slot("r1", 2)
        limiter._acquire_local_slot("r2", 2)
        limiter._local_slots.discard("r1")  # Release
        assert limiter._acquire_local_slot("r3", 2) is True


# ── ASGI Middleware ─────────────────────────────────────────────────


@pytest.mark.unit
class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_health_exempt(self) -> None:
        """Health endpoint is exempt from rate limiting."""
        limiter = RateLimiter(redis=None, per_minute=0)  # Block everything
        app_mock = AsyncMock()
        middleware = RateLimitMiddleware(app_mock, limiter)

        scope = {"type": "http", "path": "/health", "headers": []}
        await middleware(scope, AsyncMock(), AsyncMock())
        app_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rate_limited_returns_429(self) -> None:
        """When rate limit exceeded, returns 429."""
        limiter = RateLimiter(redis=None, per_minute=0, per_hour=0)

        sent_responses = []

        async def mock_send(msg):
            sent_responses.append(msg)

        middleware = RateLimitMiddleware(AsyncMock(), limiter)
        scope = {"type": "http", "path": "/api/query", "headers": []}

        await middleware(scope, AsyncMock(), mock_send)

        assert sent_responses[0]["status"] == 429
        assert any(
            h[0] == b"retry-after"
            for h in sent_responses[0]["headers"]
        )

    @pytest.mark.asyncio
    async def test_allowed_request_passes_through(self) -> None:
        """Normal requests pass through to the app."""
        limiter = RateLimiter(redis=None, per_minute=100)
        app_mock = AsyncMock()
        middleware = RateLimitMiddleware(app_mock, limiter)

        scope = {"type": "http", "path": "/api/query", "headers": []}
        await middleware(scope, AsyncMock(), AsyncMock())
        app_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_http_passes_through(self) -> None:
        """WebSocket and other scopes pass through."""
        limiter = RateLimiter(redis=None, per_minute=0)
        app_mock = AsyncMock()
        middleware = RateLimitMiddleware(app_mock, limiter)

        scope = {"type": "websocket", "path": "/ws"}
        await middleware(scope, AsyncMock(), AsyncMock())
        app_mock.assert_awaited_once()
