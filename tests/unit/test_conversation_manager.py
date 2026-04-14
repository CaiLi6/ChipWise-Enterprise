"""Unit tests for ConversationManager (§2D1)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.core.conversation_manager import MAX_TURNS, SESSION_TTL, ConversationManager


@pytest.mark.unit
class TestConversationManager:
    @pytest.fixture
    def redis(self) -> AsyncMock:
        r = AsyncMock()
        r._store: dict[str, str] = {}

        async def _get(key: str):
            return r._store.get(key)

        async def _set(key: str, value: str, ex: int = 0):
            r._store[key] = value

        async def _delete(key: str):
            r._store.pop(key, None)

        r.get = AsyncMock(side_effect=_get)
        r.set = AsyncMock(side_effect=_set)
        r.delete = AsyncMock(side_effect=_delete)
        return r

    @pytest.fixture
    def mgr(self, redis: AsyncMock) -> ConversationManager:
        return ConversationManager(redis)

    @pytest.mark.asyncio
    async def test_empty_history(self, mgr: ConversationManager) -> None:
        history = await mgr.get_history(1, "sess1")
        assert history == []

    @pytest.mark.asyncio
    async def test_append_and_get(self, mgr: ConversationManager) -> None:
        await mgr.append_turn(1, "s1", "user", "Hello")
        await mgr.append_turn(1, "s1", "assistant", "Hi!")
        history = await mgr.get_history(1, "s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hi!"

    @pytest.mark.asyncio
    async def test_10_turns_retained(self, mgr: ConversationManager) -> None:
        for i in range(10):
            await mgr.append_turn(1, "s1", "user", f"msg {i}")
        history = await mgr.get_history(1, "s1")
        assert len(history) == 10

    @pytest.mark.asyncio
    async def test_truncation_at_15_turns(self, mgr: ConversationManager) -> None:
        for i in range(15):
            await mgr.append_turn(1, "s1", "user", f"msg {i}")
        history = await mgr.get_history(1, "s1")
        assert len(history) == MAX_TURNS
        # Oldest should be msg 5 (15 - 10)
        assert history[0]["content"] == "msg 5"

    @pytest.mark.asyncio
    async def test_clear_session(self, mgr: ConversationManager) -> None:
        await mgr.append_turn(1, "s1", "user", "Hi")
        await mgr.clear_session(1, "s1")
        history = await mgr.get_history(1, "s1")
        assert history == []

    @pytest.mark.asyncio
    async def test_ttl_set_on_write(self, mgr: ConversationManager, redis: AsyncMock) -> None:
        await mgr.append_turn(1, "s1", "user", "test")
        redis.set.assert_called()
        call_args = redis.set.call_args
        assert call_args.kwargs.get("ex") == SESSION_TTL or call_args[1].get("ex") == SESSION_TTL

    @pytest.mark.asyncio
    async def test_key_format(self, mgr: ConversationManager) -> None:
        key = mgr._key(42, "abc")
        assert key == "session:42:abc"

    @pytest.mark.asyncio
    async def test_corrupt_data_returns_empty(self, mgr: ConversationManager, redis: AsyncMock) -> None:
        redis._store["session:1:s1"] = "not-valid-json{{"
        history = await mgr.get_history(1, "s1")
        assert history == []
