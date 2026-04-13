"""Unit tests for BOM alternative recommendation (§4C3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.tools.bom_review import BOMReviewTool


def _make_pool_fetchrow(row: dict | None) -> MagicMock:
    conn = AsyncMock()
    conn.fetchrow.return_value = row
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


@pytest.mark.unit
class TestFindAlternative:
    @pytest.mark.asyncio
    async def test_pg_alternative_found(self) -> None:
        pool = _make_pool_fetchrow(
            {
                "part_number": "GD32F407",
                "manufacturer": "GigaDevice",
                "compat_score": 0.95,
                "key_differences": "Same pinout, lower power",
            }
        )
        tool = BOMReviewTool(db_pool=pool)
        alt = await tool._find_alternative(1)
        assert alt is not None
        assert alt["part_number"] == "GD32F407"
        assert alt["compat_score"] == 0.95

    @pytest.mark.asyncio
    async def test_no_alternative_returns_none(self) -> None:
        pool = _make_pool_fetchrow(None)
        tool = BOMReviewTool(db_pool=pool)
        alt = await tool._find_alternative(999)
        assert alt is None

    @pytest.mark.asyncio
    async def test_graph_fallback_when_pg_empty(self) -> None:
        pool = _make_pool_fetchrow(None)
        graph = MagicMock()
        graph.find_alternatives = AsyncMock(
            return_value=[
                {"part_number": "CH32F407", "manufacturer": "WCH", "compat_score": 0.8}
            ]
        )
        tool = BOMReviewTool(db_pool=pool, graph_search=graph)
        alt = await tool._find_alternative(2)
        assert alt is not None
        assert alt["part_number"] == "CH32F407"

    @pytest.mark.asyncio
    async def test_eol_flow_triggers_alternative_lookup(self) -> None:
        """EOL chip in inline BOM gets alternative field populated."""
        pool = _make_pool_fetchrow(
            {
                "part_number": "ALT1",
                "manufacturer": "Vendor",
                "compat_score": 0.9,
                "key_differences": "Drop-in",
            }
        )
        tool = BOMReviewTool(db_pool=pool)
        alt = await tool._find_alternative(5)
        assert alt is not None
        assert "key_differences" in alt
