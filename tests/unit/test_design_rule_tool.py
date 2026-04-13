"""Unit tests for DesignRuleCheckTool (§5B1)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.tools.design_rule import DesignRuleCheckTool


def _make_pool(rows: list[dict]) -> MagicMock:
    conn = AsyncMock()
    conn.fetch.return_value = rows
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


@pytest.mark.unit
class TestDesignRuleCheckTool:
    def test_name(self) -> None:
        tool = DesignRuleCheckTool()
        assert tool.name == "design_rule_check"

    def test_schema_requires_chip_name(self) -> None:
        schema = DesignRuleCheckTool().parameters_schema
        assert "chip_name" in schema["required"]

    @pytest.mark.asyncio
    async def test_no_pool_returns_empty_lists(self) -> None:
        tool = DesignRuleCheckTool(db_pool=None, llm=None)
        result = await tool.execute(chip_name="STM32F407")
        assert result["design_rules"] == []
        assert result["errata"] == []

    @pytest.mark.asyncio
    async def test_design_rules_fetched(self) -> None:
        pool = _make_pool([
            {"rule_id": 1, "rule_type": "decoupling_cap", "rule_text": "Add 100nF per VCC pin",
             "severity": "mandatory", "chip_id": 1}
        ])
        tool = DesignRuleCheckTool(db_pool=pool)
        result = await tool.execute(chip_name="STM32F407")
        assert len(result["design_rules"]) == 1
        assert result["design_rules"][0]["rule_type"] == "decoupling_cap"

    @pytest.mark.asyncio
    async def test_errata_fetched(self) -> None:
        call_count = 0

        async def mock_fetch(query: str, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # design rules
            return [  # errata
                {"errata_id": 1, "errata_code": "ES0182-1", "title": "ADC issue",
                 "severity": "major", "status": "workaround", "chip_id": 1}
            ]

        conn = AsyncMock()
        conn.fetch.side_effect = mock_fetch
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire.return_value = cm

        tool = DesignRuleCheckTool(db_pool=pool)
        result = await tool.execute(chip_name="STM32F407")
        assert len(result["errata"]) == 1
        assert result["errata"][0]["errata_code"] == "ES0182-1"

    @pytest.mark.asyncio
    async def test_app_note_search(self) -> None:
        search_result = MagicMock()
        search_result.content = "Place 100nF decoupling cap close to VCC pin."
        search_result.doc_id = "doc123"
        search_result.score = 0.9
        search = AsyncMock()
        search.search.return_value = [search_result]

        tool = DesignRuleCheckTool(hybrid_search=search)
        result = await tool.execute(chip_name="STM32F407")

        assert len(result["app_note_citations"]) == 1
        assert result["app_note_citations"][0]["content"] == search_result.content

    @pytest.mark.asyncio
    async def test_search_failure_non_blocking(self) -> None:
        search = AsyncMock()
        search.search.side_effect = RuntimeError("Milvus down")

        tool = DesignRuleCheckTool(hybrid_search=search)
        result = await tool.execute(chip_name="STM32F407")

        assert "design_rules" in result
        assert result["app_note_citations"] == []

    @pytest.mark.asyncio
    async def test_llm_analysis_generated(self) -> None:
        pool = _make_pool([{"rule_type": "decoupling_cap", "rule_text": "100nF per VCC"}])
        llm = AsyncMock()
        llm.generate.return_value = "Key design consideration: add 100nF decoupling cap."

        tool = DesignRuleCheckTool(db_pool=pool, llm=llm)
        result = await tool.execute(chip_name="STM32F407")

        assert result["analysis"] == "Key design consideration: add 100nF decoupling cap."
        llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_non_blocking(self) -> None:
        pool = _make_pool([])
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM timeout")

        tool = DesignRuleCheckTool(db_pool=pool, llm=llm)
        result = await tool.execute(chip_name="STM32F407")

        assert result["analysis"] == ""
        assert "design_rules" in result

    @pytest.mark.asyncio
    async def test_result_contains_chip_name(self) -> None:
        tool = DesignRuleCheckTool()
        result = await tool.execute(chip_name="STM32F407")
        assert result["chip_name"] == "STM32F407"
