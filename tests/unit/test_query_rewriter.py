"""Unit tests for QueryRewriter (§2D2)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.query_rewriter import QueryRewriter


@pytest.mark.unit
class TestQueryRewriter:
    @pytest.fixture
    def llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.generate.return_value = "STM32F407 的主频是多少"
        return llm

    @pytest.fixture
    def rewriter(self, llm: AsyncMock) -> QueryRewriter:
        return QueryRewriter(llm)

    @pytest.mark.asyncio
    async def test_no_history_returns_original(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        result = await rewriter.rewrite("STM32F407 主频", [])
        assert result == "STM32F407 主频"
        llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pronoun_returns_original(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        history = [{"role": "user", "content": "STM32F407"}]
        result = await rewriter.rewrite("STM32F407 主频是多少", history)
        assert result == "STM32F407 主频是多少"
        llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_pronoun_triggers_rewrite(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        history = [{"role": "user", "content": "STM32F407"}]
        result = await rewriter.rewrite("它的主频是多少", history)
        assert result == "STM32F407 的主频是多少"
        llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_english_pronoun(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        llm.generate.return_value = "What is the clock speed of STM32F407"
        history = [{"role": "user", "content": "STM32F407"}]
        result = await rewriter.rewrite("What is its clock speed", history)
        assert "STM32F407" in result

    @pytest.mark.asyncio
    async def test_this_pronoun(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        history = [{"role": "user", "content": "Show me TPS65217"}]
        result = await rewriter.rewrite("这个芯片的电压", history)
        llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        llm.generate.side_effect = Exception("LLM timeout")
        history = [{"role": "user", "content": "STM32F407"}]
        result = await rewriter.rewrite("它的主频", history)
        assert result == "它的主频"

    @pytest.mark.asyncio
    async def test_empty_llm_response_returns_original(self, rewriter: QueryRewriter, llm: AsyncMock) -> None:
        llm.generate.return_value = ""
        history = [{"role": "user", "content": "STM32F407"}]
        result = await rewriter.rewrite("它的价格", history)
        assert result == "它的价格"

    def test_needs_rewrite_with_pronouns(self, rewriter: QueryRewriter) -> None:
        assert rewriter._needs_rewrite("它的主频")
        assert rewriter._needs_rewrite("这个芯片")
        assert rewriter._needs_rewrite("What is its speed")
        assert rewriter._needs_rewrite("Tell me about that chip")

    def test_needs_rewrite_without_pronouns(self, rewriter: QueryRewriter) -> None:
        assert not rewriter._needs_rewrite("STM32F407 主频")
        assert not rewriter._needs_rewrite("Show parameters")
