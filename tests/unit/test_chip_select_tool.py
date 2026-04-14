"""Unit tests for ChipSelectTool (§4B1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agent.tools.chip_select import ChipSelectTool


@pytest.mark.unit
class TestChipSelectTool:
    @pytest.fixture
    def tool(self) -> ChipSelectTool:
        return ChipSelectTool(db_pool=None, llm=None)

    def test_name(self, tool: ChipSelectTool) -> None:
        assert tool.name == "chip_select"

    def test_schema(self, tool: ChipSelectTool) -> None:
        schema = tool.parameters_schema
        assert "criteria" in schema["properties"]

    @pytest.mark.asyncio
    async def test_no_pool_returns_empty(self, tool: ChipSelectTool) -> None:
        result = await tool.execute(criteria={"category": "MCU"})
        assert result["candidates"] == []
        assert "No chips" in result["message"]

    @pytest.mark.asyncio
    async def test_with_mock_pool(self) -> None:
        conn = AsyncMock()
        conn.fetch.return_value = [
            {"chip_id": 1, "part_number": "STM32F407", "manufacturer": "ST",
             "category": "MCU", "package": "LQFP100", "status": "active"},
        ]
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = ChipSelectTool(db_pool=pool)
        result = await tool.execute(criteria={"category": "MCU"})
        assert result["total"] == 1
        assert result["candidates"][0]["part_number"] == "STM32F407"

    @pytest.mark.asyncio
    async def test_domestic_alternatives(self) -> None:
        conn = AsyncMock()
        conn.fetch.side_effect = [
            [{"chip_id": 1, "part_number": "STM32F407", "manufacturer": "ST",
              "category": "MCU", "package": "LQFP100", "status": "active"}],
            [{"part_number": "GD32F407", "manufacturer": "GD", "compat_score": 0.92, "key_differences": ""}],
        ]
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = ChipSelectTool(db_pool=pool)
        result = await tool.execute(criteria={"category": "MCU"}, include_domestic=True)
        assert result["total"] == 1
        # Domestic alts queried for each candidate
        assert "domestic_alternatives" in result["candidates"][0]
