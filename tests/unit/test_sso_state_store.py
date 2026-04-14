"""Unit tests for SSOStateStore (Redis-backed CSRF state)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routers._sso_state import SSOStateStore


def _make_redis_mock(store: dict[str, str] | None = None) -> AsyncMock:
    """Create a mock async Redis client backed by a plain dict."""
    _store: dict[str, str] = store if store is not None else {}
    mock = AsyncMock()

    async def _setex(key: str, ttl: int, value: str) -> None:
        _store[key] = value

    async def _getdel(key: str) -> str | None:
        return _store.pop(key, None)

    async def _get(key: str) -> str | None:
        return _store.get(key)

    async def _delete(key: str) -> int:
        return 1 if _store.pop(key, None) is not None else 0

    mock.setex = AsyncMock(side_effect=_setex)
    mock.getdel = AsyncMock(side_effect=_getdel)
    mock.get = AsyncMock(side_effect=_get)
    mock.delete = AsyncMock(side_effect=_delete)
    mock._store = _store
    return mock


@pytest.mark.unit
class TestSSOStateStorePutPop:
    @pytest.mark.asyncio
    async def test_put_then_pop_returns_payload(self) -> None:
        redis = _make_redis_mock()
        store = SSOStateStore(redis, ttl=600)
        payload = {"nonce": "abc", "provider": "keycloak"}
        await store.put("state123", payload)
        result = await store.pop("state123")
        assert result == payload

    @pytest.mark.asyncio
    async def test_pop_empty_returns_none(self) -> None:
        redis = _make_redis_mock()
        store = SSOStateStore(redis, ttl=600)
        result = await store.pop("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_pop_is_atomic_second_pop_returns_none(self) -> None:
        redis = _make_redis_mock()
        store = SSOStateStore(redis, ttl=600)
        await store.put("state_once", {"nonce": "x", "provider": "keycloak"})
        first = await store.pop("state_once")
        second = await store.pop("state_once")
        assert first is not None
        assert second is None

    @pytest.mark.asyncio
    async def test_setex_called_with_ttl(self) -> None:
        redis = _make_redis_mock()
        store = SSOStateStore(redis, ttl=300)
        await store.put("s1", {"nonce": "n"})
        redis.setex.assert_awaited_once()
        call_args = redis.setex.call_args
        assert call_args[0][1] == 300  # TTL


@pytest.mark.unit
class TestSSOStateStoreGetdelFallback:
    @pytest.mark.asyncio
    async def test_fallback_to_get_delete_on_old_redis(self) -> None:
        """When GETDEL raises (Redis < 6.2), fall back to GET+DELETE."""
        backing: dict[str, str] = {}
        redis = _make_redis_mock(backing)

        async def _getdel_raises(key: str) -> None:
            raise Exception("ERR unknown command 'GETDEL'")

        redis.getdel = AsyncMock(side_effect=_getdel_raises)
        store = SSOStateStore(redis, ttl=600)

        # Manually insert into backing store
        backing["sso:state:fallback"] = json.dumps({"nonce": "fb", "provider": "dingtalk"})

        result = await store.pop("fallback")
        assert result == {"nonce": "fb", "provider": "dingtalk"}
        assert "sso:state:fallback" not in backing


@pytest.mark.unit
class TestSSOStateStoreRedisNone:
    @pytest.mark.asyncio
    async def test_put_raises_503_when_redis_none(self) -> None:
        store = SSOStateStore(redis=None)
        with pytest.raises(HTTPException) as exc_info:
            await store.put("s1", {"nonce": "n"})
        assert exc_info.value.status_code == 503
        assert "Redis" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_pop_raises_503_when_redis_none(self) -> None:
        store = SSOStateStore(redis=None)
        with pytest.raises(HTTPException) as exc_info:
            await store.pop("s1")
        assert exc_info.value.status_code == 503
        assert "Redis" in exc_info.value.detail
