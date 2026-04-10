"""Unit tests for RAGSearchTool."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.types import RetrievalResult
from src.libs.reranker.base import RerankResult
from src.agent.tools.rag_search import RAGSearchTool


def _mock_retrieval_results(n: int = 5) -> list[RetrievalResult]:
    return [
        RetrievalResult(chunk_id=f"c{i}", doc_id=f"d{i}", content=f"content {i}", score=0.9 - i * 0.1)
        for i in range(n)
    ]


@pytest.mark.unit
class TestRAGSearchTool:
    @pytest.fixture
    def tool(self) -> RAGSearchTool:
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(5)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(3)
        graph = AsyncMock()
        graph.get_chip_subgraph.return_value = [{"node": "data"}]
        return RAGSearchTool(hybrid, reranker, graph)

    def test_name(self, tool: RAGSearchTool) -> None:
        assert tool.name == "rag_search"

    def test_schema_has_query(self, tool: RAGSearchTool) -> None:
        schema = tool.parameters_schema
        assert "query" in schema["properties"]
        assert "query" in schema["required"]

    @pytest.mark.asyncio
    async def test_search_normal(self, tool: RAGSearchTool) -> None:
        result = await tool.execute(query="STM32F407 clock speed")
        assert "results" in result
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_search_with_filters(self, tool: RAGSearchTool) -> None:
        result = await tool.execute(query="test", part_number="STM32F407", doc_type="datasheet")
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        hybrid = AsyncMock()
        hybrid.search.return_value = []
        reranker = AsyncMock()
        tool = RAGSearchTool(hybrid, reranker)
        result = await tool.execute(query="nonexistent")
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_graph_boost_applied(self, tool: RAGSearchTool) -> None:
        result = await tool.execute(query="test", part_number="STM32F407", use_graph_boost=True)
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_no_graph_boost(self) -> None:
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(3)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(2)
        tool = RAGSearchTool(hybrid, reranker, None)
        result = await tool.execute(query="test", use_graph_boost=True)
        assert result["total"] == 2

    def test_openai_tool_format(self, tool: RAGSearchTool) -> None:
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "rag_search"
