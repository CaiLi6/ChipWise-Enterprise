"""Unit tests for BOMReviewTool (§4C1-4C3)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.tools.bom_review import BOMReviewTool, BOMItem


@pytest.mark.unit
class TestBOMReviewTool:
    @pytest.fixture
    def tool(self) -> BOMReviewTool:
        return BOMReviewTool(db_pool=None)

    def test_name(self, tool: BOMReviewTool) -> None:
        assert tool.name == "bom_review"

    @pytest.mark.asyncio
    async def test_no_input(self, tool: BOMReviewTool) -> None:
        result = await tool.execute()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_inline_bom_data(self, tool: BOMReviewTool) -> None:
        result = await tool.execute(bom_data=[
            {"part_number": "STM32F407", "description": "MCU", "quantity": 1},
            {"part_number": "TPS65217", "description": "PMIC", "quantity": 2},
        ])
        assert result["bom_review"]["total_items"] == 2
        assert result["bom_review"]["unmatched"] == 2  # No DB

    @pytest.mark.asyncio
    async def test_bom_item_to_dict(self) -> None:
        item = BOMItem(1, "STM32F407", "MCU ARM", 5, "U1")
        d = item.to_dict()
        assert d["part_number"] == "STM32F407"
        assert d["quantity"] == 5
        assert d["match_status"] == "unmatched"

    def test_check_eol(self) -> None:
        item = BOMItem(1, "CHIP1")
        item._status = "EOL"
        BOMReviewTool._check_eol(item)
        assert item.eol_flag is True

    def test_check_nrnd(self) -> None:
        item = BOMItem(1, "CHIP2")
        item._status = "NRND"
        BOMReviewTool._check_eol(item)
        assert item.nrnd_flag is True

    def test_check_active(self) -> None:
        item = BOMItem(1, "CHIP3")
        item._status = "active"
        BOMReviewTool._check_eol(item)
        assert not item.eol_flag
        assert not item.nrnd_flag


@pytest.mark.unit
class TestBOMConflicts:
    @pytest.mark.asyncio
    async def test_no_conflicts_without_description(self) -> None:
        tool = BOMReviewTool(db_pool=None)
        item = BOMItem(1, "X", "", 1)
        item.chip_id = 1
        await tool._check_conflicts(item)
        assert item.parameter_conflicts == []


@pytest.mark.unit
class TestBOMAlternatives:
    @pytest.mark.asyncio
    async def test_no_alternative_found(self) -> None:
        conn = AsyncMock()
        conn.fetchrow.return_value = None
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = BOMReviewTool(db_pool=pool)
        alt = await tool._find_alternative(999)
        assert alt is None

    @pytest.mark.asyncio
    async def test_alternative_found_in_pg(self) -> None:
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "part_number": "GD32F407", "manufacturer": "GD",
            "compat_score": 0.92, "key_differences": "Lower power"
        }
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = BOMReviewTool(db_pool=pool)
        alt = await tool._find_alternative(1)
        assert alt is not None
        assert alt["part_number"] == "GD32F407"
