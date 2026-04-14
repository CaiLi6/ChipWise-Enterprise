"""Unit tests for RAGSearchTool (task 2C4).

Acceptance criteria:
- rag_search(query="STM32F407 主频") returns results with content/part_number/page/score
- use_graph_boost=True boosts chunks with errata info
- Filters (part_number, doc_type) correctly passed
- Empty data returns {results:[], total:0} — no error
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.agent.tools.rag_search import RAGSearchTool
from src.core.types import RetrievalResult


def _mock_retrieval_results(n: int = 5, page: int = 1) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id=f"c{i}",
            doc_id=f"d{i}",
            content=f"content {i}",
            score=0.9 - i * 0.1,
            page_number=page + i,
            metadata={"part_number": "STM32F407"},
        )
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

    def test_schema_optional_fields(self, tool: RAGSearchTool) -> None:
        props = tool.parameters_schema["properties"]
        assert "part_number" in props
        assert "doc_type" in props
        assert props["doc_type"]["enum"] == ["datasheet", "app_note", "errata"]
        assert "top_k" in props
        assert "use_graph_boost" in props

    @pytest.mark.asyncio
    async def test_search_normal(self, tool: RAGSearchTool) -> None:
        result = await tool.execute(query="STM32F407 clock speed")
        assert "results" in result
        assert result["total"] == 3
        # Each result should have content, score, page_number
        r0 = result["results"][0]
        assert "content" in r0
        assert "score" in r0
        assert "page_number" in r0
        assert "chunk_id" in r0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, tool: RAGSearchTool) -> None:
        result = await tool.execute(query="test", part_number="STM32F407", doc_type="datasheet")
        assert result["total"] == 3
        # Verify filters were passed to hybrid search
        call_kwargs = tool._hybrid.search.call_args
        assert call_kwargs[1]["filters"]["part_number"] == "STM32F407"
        assert call_kwargs[1]["filters"]["doc_type"] == "datasheet"

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        hybrid = AsyncMock()
        hybrid.search.return_value = []
        reranker = AsyncMock()
        tool = RAGSearchTool(hybrid, reranker)
        result = await tool.execute(query="nonexistent")
        assert result["total"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_graph_boost_applied(self, tool: RAGSearchTool) -> None:
        """use_graph_boost=True + part_number → scores boosted."""
        result = await tool.execute(query="test", part_number="STM32F407", use_graph_boost=True)
        assert result["total"] == 3
        # Graph boost should have been attempted
        tool._graph.get_chip_subgraph.assert_called_once_with("STM32F407", max_depth=1)

    @pytest.mark.asyncio
    async def test_no_graph_without_part_number(self) -> None:
        """Graph boost skipped when no part_number provided."""
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(3)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(2)
        graph = AsyncMock()
        tool = RAGSearchTool(hybrid, reranker, graph)
        await tool.execute(query="test", use_graph_boost=True)
        graph.get_chip_subgraph.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_graph_boost_when_disabled(self) -> None:
        """use_graph_boost=False → graph not queried."""
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(3)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(2)
        graph = AsyncMock()
        tool = RAGSearchTool(hybrid, reranker, graph)
        await tool.execute(query="test", part_number="STM32", use_graph_boost=False)
        graph.get_chip_subgraph.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_graph_service(self) -> None:
        """Graceful degradation when graph_search is None."""
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(3)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(2)
        tool = RAGSearchTool(hybrid, reranker, None)
        result = await tool.execute(query="test", part_number="X", use_graph_boost=True)
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_graph_failure_graceful(self) -> None:
        """Graph boost failure does not crash the tool."""
        hybrid = AsyncMock()
        hybrid.search.return_value = _mock_retrieval_results(3)
        reranker = AsyncMock()
        reranker.rerank.return_value = _mock_retrieval_results(2)
        graph = AsyncMock()
        graph.get_chip_subgraph.side_effect = RuntimeError("Graph down")
        tool = RAGSearchTool(hybrid, reranker, graph)
        result = await tool.execute(query="test", part_number="X", use_graph_boost=True)
        assert result["total"] == 2  # still returns results

    def test_openai_tool_format(self, tool: RAGSearchTool) -> None:
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "rag_search"
