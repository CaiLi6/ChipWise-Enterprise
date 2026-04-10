"""Unit tests for DatasheetCrawler (§3C3)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion.crawler import DatasheetCrawler, MANUFACTURER_CONFIGS


@pytest.mark.unit
class TestDatasheetCrawler:
    def test_manufacturer_configs(self) -> None:
        assert "ST" in MANUFACTURER_CONFIGS
        assert "TI" in MANUFACTURER_CONFIGS
        assert "NXP" in MANUFACTURER_CONFIGS

    def test_max_per_run_limit(self) -> None:
        for cfg in MANUFACTURER_CONFIGS.values():
            assert cfg["max_per_run"] == 50

    @pytest.mark.asyncio
    async def test_unknown_manufacturer(self) -> None:
        crawler = DatasheetCrawler()
        result = await crawler.crawl("UNKNOWN_MFR")
        assert result == []

    @pytest.mark.asyncio
    async def test_crawl_without_playwright(self) -> None:
        # Playwright not installed → empty result, no crash
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            crawler = DatasheetCrawler()
            # Will fail gracefully
            result = await crawler.crawl("ST")
            assert isinstance(result, list)
