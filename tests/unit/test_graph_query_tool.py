"""Unit tests for GraphQueryTool."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.agent.tools.graph_query import GraphQueryTool


@pytest.mark.unit
class TestGraphQueryTool:
    @pytest.fixture
    def tool(self) -> GraphQueryTool:
        graph_search = AsyncMock()
        graph_search.find_alternatives.return_value = [
            {"part_number": "GD32F407", "score": 0.85}
        ]
        graph_search.find_errata_by_peripheral.return_value = [
            {"code": "ERR001", "title": "SPI bug"}
        ]
        graph_search.get_chip_subgraph.return_value = [{"node": "data"}]
        graph_search.param_range_search.return_value = [
            {"part_number": "STM32F4", "value": 168}
        ]
        graph_search.execute_custom_cypher.return_value = [{"val": 42}]
        return GraphQueryTool(graph_search)

    def test_name(self, tool: GraphQueryTool) -> None:
        assert tool.name == "graph_query"

    @pytest.mark.asyncio
    async def test_find_alternatives(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(query_type="find_alternatives", part_number="STM32F407")
        assert result["total"] == 1
        assert result["results"][0]["part_number"] == "GD32F407"

    @pytest.mark.asyncio
    async def test_find_errata(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(
            query_type="find_errata_by_peripheral", part_number="STM32F407", peripheral="SPI"
        )
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_chip_subgraph(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(query_type="chip_subgraph", part_number="STM32F407")
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_param_range(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(
            query_type="param_range_search", param_name="freq", min_val=100, max_val=200
        )
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_custom_cypher_allowed(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(query_type="custom_cypher", cypher="RETURN 42 AS val")
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_custom_cypher_write_blocked(self, tool: GraphQueryTool) -> None:
        tool._graph.execute_custom_cypher.side_effect = ValueError("Write not allowed")
        result = await tool.execute(query_type="custom_cypher", cypher="CREATE (n:X)")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_query_type(self, tool: GraphQueryTool) -> None:
        result = await tool.execute(query_type="unknown_type")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_graph_unavailable(self, tool: GraphQueryTool) -> None:
        tool._graph.find_alternatives.side_effect = Exception("DB down")
        result = await tool.execute(query_type="find_alternatives", part_number="X")
        assert "error" in result
        assert result["results"] == []
