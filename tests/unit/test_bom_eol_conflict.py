"""Unit tests for BOM EOL/NRND detection + parameter conflict checking (§4C2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agent.tools.bom_review import BOMItem, BOMReviewTool


def _make_pool(rows: list[dict] | None = None) -> MagicMock:
    conn = AsyncMock()
    conn.fetch.return_value = rows or []
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


@pytest.mark.unit
class TestEOLDetection:
    def test_eol_status_flags(self) -> None:
        item = BOMItem(1, "CHIP-EOL")
        item._status = "EOL"
        BOMReviewTool._check_eol(item)
        assert item.eol_flag is True
        assert item.nrnd_flag is False

    def test_nrnd_status_flags(self) -> None:
        item = BOMItem(2, "CHIP-NRND")
        item._status = "NRND"
        BOMReviewTool._check_eol(item)
        assert item.nrnd_flag is True
        assert item.eol_flag is False

    def test_obsolete_counts_as_eol(self) -> None:
        item = BOMItem(3, "CHIP-OBS")
        item._status = "obsolete"
        BOMReviewTool._check_eol(item)
        assert item.eol_flag is True

    def test_active_not_flagged(self) -> None:
        item = BOMItem(4, "CHIP-ACT")
        item._status = "active"
        BOMReviewTool._check_eol(item)
        assert not item.eol_flag
        assert not item.nrnd_flag


@pytest.mark.unit
class TestParameterConflicts:
    @pytest.mark.asyncio
    async def test_voltage_conflict_detected(self) -> None:
        pool = _make_pool(
            rows=[{"name": "VCC", "max_value": "3.6", "unit": "V"}]
        )
        tool = BOMReviewTool(db_pool=pool)
        item = BOMItem(1, "STM32F407", "MCU 5V LQFP48", 1)
        item.chip_id = 1
        await tool._check_conflicts(item)
        assert len(item.parameter_conflicts) == 1
        assert item.parameter_conflicts[0]["param"] == "vcc"

    @pytest.mark.asyncio
    async def test_no_conflict_when_voltage_matches(self) -> None:
        pool = _make_pool(
            rows=[{"name": "VCC", "max_value": "3.6", "unit": "V"}]
        )
        tool = BOMReviewTool(db_pool=pool)
        item = BOMItem(1, "STM32F407", "MCU 3.3V LQFP48", 1)
        item.chip_id = 1
        await tool._check_conflicts(item)
        assert item.parameter_conflicts == []

    @pytest.mark.asyncio
    async def test_no_conflict_without_description(self) -> None:
        tool = BOMReviewTool(db_pool=None)
        item = BOMItem(1, "X", "", 1)
        item.chip_id = 1
        await tool._check_conflicts(item)
        assert item.parameter_conflicts == []

    @pytest.mark.asyncio
    async def test_description_without_claims_ignored(self) -> None:
        pool = _make_pool(rows=[])
        tool = BOMReviewTool(db_pool=pool)
        item = BOMItem(1, "X", "General purpose MCU", 1)
        item.chip_id = 1
        await tool._check_conflicts(item)
        assert item.parameter_conflicts == []
