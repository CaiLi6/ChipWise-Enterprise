"""Unit tests for GraphSearch — mock GraphStore."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from src.libs.graph_store.base import BaseGraphStore
from src.retrieval.graph_search import GraphSearch


@pytest.mark.unit
class TestGraphSearch:
    @pytest.fixture
    def mock_store(self) -> MagicMock:
        store = MagicMock(spec=BaseGraphStore)
        store.execute_cypher.return_value = []
        store.get_subgraph.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_find_alternatives_empty(self, mock_store: MagicMock) -> None:
        gs = GraphSearch(mock_store)
        results = await gs.find_alternatives("NONEXISTENT")
        assert results == []
        mock_store.execute_cypher.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_alternatives_with_results(self, mock_store: MagicMock) -> None:
        mock_store.execute_cypher.return_value = [
            {"part_number": "GD32F407", "manufacturer": "GigaDevice",
             "score": 0.85, "compat_type": "pin", "differences": "Flash timing"}
        ]
        gs = GraphSearch(mock_store)
        results = await gs.find_alternatives("STM32F407")
        assert len(results) == 1
        assert results[0]["part_number"] == "GD32F407"

    @pytest.mark.asyncio
    async def test_find_errata_by_peripheral(self, mock_store: MagicMock) -> None:
        mock_store.execute_cypher.return_value = [
            {"code": "ERR001", "title": "SPI bug", "severity": "high", "workaround": "Use DMA"}
        ]
        gs = GraphSearch(mock_store)
        results = await gs.find_errata_by_peripheral("STM32F407", "SPI")
        assert len(results) == 1
        assert results[0]["code"] == "ERR001"

    @pytest.mark.asyncio
    async def test_get_chip_subgraph(self, mock_store: MagicMock) -> None:
        mock_store.get_subgraph.return_value = [{"src": {}, "dest": {}}]
        gs = GraphSearch(mock_store)
        results = await gs.get_chip_subgraph("STM32F407")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_param_range_search(self, mock_store: MagicMock) -> None:
        mock_store.execute_cypher.return_value = [
            {"part_number": "STM32F407", "manufacturer": "ST", "param": "Vcc", "value": 3.3, "unit": "V"}
        ]
        gs = GraphSearch(mock_store)
        results = await gs.param_range_search("Vcc", 3.0, 3.6)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_custom_cypher_read_allowed(self, mock_store: MagicMock) -> None:
        mock_store.execute_cypher.return_value = [{"val": 42}]
        gs = GraphSearch(mock_store)
        results = await gs.execute_custom_cypher("RETURN 42 AS val")
        assert results[0]["val"] == 42

    @pytest.mark.asyncio
    async def test_custom_cypher_write_blocked(self, mock_store: MagicMock) -> None:
        gs = GraphSearch(mock_store)
        with pytest.raises(ValueError, match="Write operations"):
            await gs.execute_custom_cypher("CREATE (n:Chip {name: 'test'})")

    @pytest.mark.asyncio
    async def test_custom_cypher_delete_blocked(self, mock_store: MagicMock) -> None:
        gs = GraphSearch(mock_store)
        with pytest.raises(ValueError, match="Write operations"):
            await gs.execute_custom_cypher("MATCH (n) DELETE n")

    @pytest.mark.asyncio
    async def test_custom_cypher_merge_blocked(self, mock_store: MagicMock) -> None:
        gs = GraphSearch(mock_store)
        with pytest.raises(ValueError, match="Write operations"):
            await gs.execute_custom_cypher("MERGE (n:Chip {name: 'test'})")
