"""Unit tests for domestic alternatives (§4B2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agent.tools.chip_select import ChipSelectTool


@pytest.mark.unit
class TestDomesticAlternatives:
    @pytest.mark.asyncio
    async def test_pg_alternatives_found(self) -> None:
        conn = AsyncMock()
        conn.fetch.return_value = [
            {"part_number": "GD32F407", "manufacturer": "GD", "compat_score": 0.92, "key_differences": ""}
        ]
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = ChipSelectTool(db_pool=pool)
        alts = await tool._find_domestic_alternatives(1)
        assert len(alts) == 1
        assert alts[0]["part_number"] == "GD32F407"

    @pytest.mark.asyncio
    async def test_no_alternatives(self) -> None:
        conn = AsyncMock()
        conn.fetch.return_value = []
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = ChipSelectTool(db_pool=pool)
        alts = await tool._find_domestic_alternatives(1)
        assert alts == []

    @pytest.mark.asyncio
    async def test_graph_dedup(self) -> None:
        conn = AsyncMock()
        conn.fetch.return_value = [
            {"part_number": "GD32F407", "manufacturer": "GD", "compat_score": 0.92, "key_differences": ""}
        ]
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        graph = AsyncMock()
        graph.find_alternatives.return_value = [
            {"part_number": "GD32F407"},  # duplicate
            {"part_number": "AT32F407"},  # new
        ]

        tool = ChipSelectTool(db_pool=pool, graph_search=graph)
        alts = await tool._find_domestic_alternatives(1)
        parts = [a["part_number"] for a in alts]
        assert "GD32F407" in parts
        assert "AT32F407" in parts
        assert len(alts) == 2  # No duplicates
