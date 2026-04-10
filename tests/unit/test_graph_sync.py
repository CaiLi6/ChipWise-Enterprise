"""Unit tests for GraphSynchronizer (§3B3)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ingestion.graph_sync import GraphSynchronizer, SyncResult


@pytest.mark.unit
class TestGraphSynchronizer:
    @pytest.fixture
    def pool(self) -> AsyncMock:
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "chip_id": 1, "part_number": "STM32F407", "manufacturer": "ST"
        }
        conn.fetch.return_value = []  # Default: no related records

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value = cm
        return pool

    @pytest.fixture
    def graph(self) -> AsyncMock:
        g = AsyncMock()
        g.upsert_node.return_value = None
        g.upsert_edge.return_value = None
        return g

    @pytest.fixture
    def syncer(self, pool: AsyncMock, graph: AsyncMock) -> GraphSynchronizer:
        return GraphSynchronizer(pool, graph)

    @pytest.mark.asyncio
    async def test_sync_chip_basic(self, syncer: GraphSynchronizer) -> None:
        result = await syncer.sync_chip(1)
        assert isinstance(result, SyncResult)
        assert result.nodes_created >= 1
        assert not result.errors

    @pytest.mark.asyncio
    async def test_sync_chip_not_found(self, syncer: GraphSynchronizer, pool: AsyncMock) -> None:
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = cm

        result = await syncer.sync_chip(999)
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_sync_with_params(self, syncer: GraphSynchronizer, pool: AsyncMock) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        # Return params on second call to fetch
        call_count = 0
        async def mock_fetch(query, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"param_id": 10, "name": "VDD", "value": "3.3"}]
            return []
        conn.fetch = mock_fetch

        result = await syncer.sync_chip(1)
        assert result.nodes_created >= 2  # chip + param
        assert result.edges_created >= 1  # HAS_PARAM

    @pytest.mark.asyncio
    async def test_sync_result_dataclass(self) -> None:
        r = SyncResult(nodes_created=3, edges_created=5)
        assert r.errors == []
        assert r.nodes_created == 3
