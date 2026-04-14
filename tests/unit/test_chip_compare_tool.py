"""Unit tests for ChipCompareTool (§4A1)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.agent.tools.chip_compare import ChipCompareTool


@pytest.mark.unit
class TestChipCompareTool:
    @pytest.fixture
    def tool(self) -> ChipCompareTool:
        llm = AsyncMock()
        llm.generate.return_value = "STM32F407 has higher clock speed."
        return ChipCompareTool(db_pool=None, llm=llm)

    def test_name(self, tool: ChipCompareTool) -> None:
        assert tool.name == "chip_compare"

    def test_schema(self, tool: ChipCompareTool) -> None:
        schema = tool.parameters_schema
        assert "chip_names" in schema["properties"]
        assert schema["properties"]["chip_names"]["minItems"] == 2

    @pytest.mark.asyncio
    async def test_too_few_chips(self, tool: ChipCompareTool) -> None:
        result = await tool.execute(chip_names=["STM32F407"])
        assert "error" in result

    @pytest.mark.asyncio
    async def test_compare_no_db(self, tool: ChipCompareTool) -> None:
        result = await tool.execute(chip_names=["STM32F407", "STM32F103"])
        assert "comparison_table" in result
        assert "analysis" in result
        assert result["chips"] == ["STM32F407", "STM32F103"]

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = Exception("LLM down")
        tool = ChipCompareTool(db_pool=None, llm=llm)
        result = await tool.execute(chip_names=["A", "B"])
        assert "comparison_table" in result
        assert result["analysis"] == ""

    def test_build_comparison_table(self) -> None:
        params = {
            "STM32F407": {"freq": {"typ": "168", "unit": "MHz", "category": "timing"}},
            "STM32F103": {"freq": {"typ": "72", "unit": "MHz", "category": "timing"}},
        }
        table = ChipCompareTool._build_comparison_table(params)
        assert "freq" in table
        assert "STM32F407" in table["freq"]

    def test_format_table(self) -> None:
        table = {"freq": {"A": {"typ": "168", "unit": "MHz"}, "B": {"typ": "72", "unit": "MHz"}}}
        text = ChipCompareTool._format_table(table, ["A", "B"])
        assert "168" in text
        assert "72" in text
