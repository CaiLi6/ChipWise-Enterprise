"""Unit tests for KnowledgeSearchTool (§5C2)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.tools.knowledge_search import KnowledgeSearchTool


def _make_result(content: str, doc_id: str = "doc1", score: float = 0.9) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.doc_id = doc_id
    r.score = score
    r.metadata = {"note_type": "design_tip", "author": "engineer1", "tags": ["SPI"]}
    return r


@pytest.mark.unit
class TestKnowledgeSearchTool:
    def test_name(self) -> None:
        tool = KnowledgeSearchTool()
        assert tool.name == "knowledge_search"

    def test_schema_requires_query(self) -> None:
        schema = KnowledgeSearchTool().parameters_schema
        assert "query" in schema["required"]

    @pytest.mark.asyncio
    async def test_no_search_returns_empty(self) -> None:
        tool = KnowledgeSearchTool(hybrid_search=None)
        result = await tool.execute(query="SPI timing")
        assert result["results"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        search = AsyncMock()
        search.search.return_value = [
            _make_result("STM32F407 SPI CS timing needs careful attention."),
        ]

        tool = KnowledgeSearchTool(hybrid_search=search)
        result = await tool.execute(query="STM32F407 SPI 注意事项")

        assert result["total"] == 1
        assert result["results"][0]["content"] == "STM32F407 SPI CS timing needs careful attention."
        assert result["results"][0]["source"] == "team_knowledge"

    @pytest.mark.asyncio
    async def test_chip_id_filter_passed_to_search(self) -> None:
        search = AsyncMock()
        search.search.return_value = []

        tool = KnowledgeSearchTool(hybrid_search=search)
        await tool.execute(query="SPI", chip_id=42)

        call_kwargs = search.search.call_args[1]
        assert call_kwargs.get("filters") == {"chip_id": 42}

    @pytest.mark.asyncio
    async def test_no_chip_id_passes_none_filters(self) -> None:
        search = AsyncMock()
        search.search.return_value = []

        tool = KnowledgeSearchTool(hybrid_search=search)
        await tool.execute(query="MCU tips")

        call_kwargs = search.search.call_args[1]
        assert call_kwargs.get("filters") is None

    @pytest.mark.asyncio
    async def test_top_k_forwarded(self) -> None:
        search = AsyncMock()
        search.search.return_value = []

        tool = KnowledgeSearchTool(hybrid_search=search)
        await tool.execute(query="SPI", top_k=3)

        search.search.assert_called_once()
        call_kwargs = search.search.call_args[1]
        assert call_kwargs.get("top_k") == 3

    @pytest.mark.asyncio
    async def test_search_failure_returns_empty(self) -> None:
        search = AsyncMock()
        search.search.side_effect = RuntimeError("Milvus down")

        tool = KnowledgeSearchTool(hybrid_search=search)
        result = await tool.execute(query="SPI timing")

        assert result["results"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_knowledge_notes_collection_used(self) -> None:
        search = AsyncMock()
        search.search.return_value = []

        tool = KnowledgeSearchTool(hybrid_search=search)
        await tool.execute(query="any")

        call_kwargs = search.search.call_args[1]
        assert call_kwargs.get("collection") == "knowledge_notes"
