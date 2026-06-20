"""Unit tests for memory scoring and prompt-budgeted retrieval."""

from __future__ import annotations

import pytest
from src.core.conversation_manager import ConversationContext
from src.core.memory_retriever import MemoryRetrievalConfig, MemoryRetriever
from src.core.memory_scorer import MemoryImportanceScorer


@pytest.mark.unit
class TestMemoryImportanceScorer:
    def test_scores_chip_numeric_fact_as_important(self) -> None:
        scorer = MemoryImportanceScorer()
        meta = scorer.score_turn("user", "XCKU5PFFVD900 PCIe user clock is 300 MHz")
        assert meta["importance"] >= 0.7
        assert meta["entities"]["chips"] == ["XCKU5PFFVD900"]
        assert "parameter_query" in meta["topics"]
        assert meta["facts"]

    def test_detects_user_preference(self) -> None:
        scorer = MemoryImportanceScorer()
        meta = scorer.score_turn("user", "以后默认优先用 sql_query 查单参数")
        assert "preference" in meta["topics"]
        assert meta["importance"] >= 0.5


@pytest.mark.unit
class TestMemoryRetriever:
    def test_includes_summary_and_recent_turns_under_budget(self) -> None:
        context = ConversationContext(
            summary="用户正在比较 XCKU5PFFVD900 的 PCIe 参数。",
            turns=[
                {"role": "user", "content": "unrelated old message", "metadata": {"importance": 0.1}},
                {
                    "role": "assistant",
                    "content": "XCKU5PFFVD900 PCIe user clock is 300 MHz",
                    "metadata": {
                        "importance": 0.9,
                        "entities": {"chips": ["XCKU5PFFVD900"]},
                        "topics": ["parameter_query"],
                    },
                },
                {"role": "user", "content": "它的带宽呢？", "metadata": {"importance": 0.4}},
            ],
        )
        retriever = MemoryRetriever(MemoryRetrievalConfig(prompt_budget_chars=500, recent_turns_always=1))
        messages = retriever.select_messages(context, "XCKU5PFFVD900 PCIe clock")
        assert messages[0]["role"] == "system"
        assert any("300 MHz" in msg["content"] for msg in messages)
        assert messages[-1]["content"] == "它的带宽呢？"

    def test_respects_prompt_budget(self) -> None:
        context = ConversationContext(
            summary="S" * 50,
            turns=[{"role": "user", "content": "A" * 200, "metadata": {"importance": 1.0}}],
        )
        retriever = MemoryRetriever(MemoryRetrievalConfig(prompt_budget_chars=80))
        messages = retriever.select_messages(context, "anything")
        assert sum(len(msg["content"]) for msg in messages) <= 80

    def test_includes_pinned_memory_after_summary(self) -> None:
        context = ConversationContext(
            summary="用户关注 XCKU5PFFVD900。",
            pinned=[{"content": "以后默认优先用 sql_query 查单参数"}],
            turns=[],
        )
        retriever = MemoryRetriever(MemoryRetrievalConfig(prompt_budget_chars=500))
        messages = retriever.select_messages(context, "DSP 数量")
        assert len(messages) == 2
        assert "Pinned conversation memory" in messages[1]["content"]
