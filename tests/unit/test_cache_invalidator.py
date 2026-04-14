"""Unit tests for CacheInvalidator (0% → 70%+)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.cache.cache_invalidator import CacheInvalidator


@pytest.mark.unit
class TestCacheInvalidator:
    def test_init(self) -> None:
        redis = MagicMock()
        inv = CacheInvalidator(redis)
        assert inv._redis is redis
        assert inv._running is False

    def test_stop(self) -> None:
        redis = MagicMock()
        inv = CacheInvalidator(redis)
        inv._running = True
        inv.stop()
        assert inv._running is False

    @pytest.mark.asyncio
    async def test_on_message_with_valid_part_number(self) -> None:
        redis = AsyncMock()
        # Simulate scan returning cursor 0 (done) and one key
        redis.scan.return_value = (0, [b"gptcache:bucket:1"])
        redis.lrange.return_value = [
            json.dumps({"query": "STM32F407 frequency"}),
            json.dumps({"query": "ESP32 power consumption"}),
        ]
        pipe = AsyncMock()
        # redis.pipeline() is sync, returns context manager
        pipe_ctx = MagicMock()
        pipe_ctx.__aenter__ = AsyncMock(return_value=pipe)
        pipe_ctx.__aexit__ = AsyncMock(return_value=False)
        redis.pipeline = MagicMock(return_value=pipe_ctx)

        inv = CacheInvalidator(redis)
        message = {
            "type": "pmessage",
            "data": json.dumps({"part_number": "STM32F407"}),
        }
        await inv.on_message(message)

        # Should have scanned for gptcache buckets
        redis.scan.assert_awaited_once()
        redis.lrange.assert_awaited_once()
        # Pipeline should delete and re-add only ESP32 entry
        pipe.delete.assert_awaited_once_with(b"gptcache:bucket:1")
        pipe.rpush.assert_awaited_once()
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_message_no_part_number(self) -> None:
        redis = AsyncMock()
        inv = CacheInvalidator(redis)
        message = {"type": "pmessage", "data": json.dumps({})}
        await inv.on_message(message)
        # Should return early, no scan
        redis.scan.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_message_empty_data(self) -> None:
        redis = AsyncMock()
        inv = CacheInvalidator(redis)
        message = {"type": "pmessage", "data": "{}"}
        await inv.on_message(message)
        redis.scan.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_message_no_matching_entries(self) -> None:
        redis = AsyncMock()
        redis.scan.return_value = (0, [b"gptcache:bucket:1"])
        redis.lrange.return_value = [
            json.dumps({"query": "ESP32 power consumption"}),
        ]
        inv = CacheInvalidator(redis)
        message = {
            "type": "pmessage",
            "data": json.dumps({"part_number": "STM32F407"}),
        }
        await inv.on_message(message)
        # No entries matched, so pipeline shouldn't be called
        redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_exception_handled(self) -> None:
        redis = AsyncMock()
        redis.scan.side_effect = Exception("Redis error")
        inv = CacheInvalidator(redis)
        message = {
            "type": "pmessage",
            "data": json.dumps({"part_number": "STM32F407"}),
        }
        # Should not raise
        await inv.on_message(message)

    @pytest.mark.asyncio
    async def test_subscribe_processes_pmessage(self) -> None:
        redis = MagicMock()
        pubsub = AsyncMock()
        redis.pubsub.return_value = pubsub

        # Simulate one pmessage then stop
        async def mock_listen():
            yield {"type": "pmessage", "data": json.dumps({"part_number": "X"})}

        pubsub.listen = mock_listen

        inv = CacheInvalidator(redis)
        # Make on_message a no-op and stop after first message
        inv.on_message = AsyncMock(side_effect=lambda _: inv.stop())
        inv._running = True

        # subscribe should enter loop then break when _running is False
        await inv.subscribe()
        inv.on_message.assert_awaited_once()
