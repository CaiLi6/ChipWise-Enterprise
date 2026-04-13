"""Unit tests for TestCaseGenTool (§5A1)."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.tools.test_case_gen import TestCaseGenTool


def _make_pool(rows: list[dict]) -> MagicMock:
    conn = AsyncMock()
    conn.fetch.return_value = rows
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


_SAMPLE_PARAMS = [
    {"name": "VCC", "typ_value": "3.3", "min_value": "1.8", "max_value": "3.6", "unit": "V", "category": "electrical"},
    {"name": "Frequency", "typ_value": "168", "min_value": None, "max_value": "168", "unit": "MHz", "category": "timing"},
    {"name": "Operating Temp", "typ_value": "25", "min_value": "-40", "max_value": "85", "unit": "°C", "category": "thermal"},
]

_SAMPLE_CASES = [
    {"test_item": "Supply voltage nominal", "parameter": "VCC", "condition": "T=25°C",
     "expected_value": "3.3V ±5%", "test_method": "DMM", "priority": "high"},
    {"test_item": "Max clock frequency", "parameter": "Frequency", "condition": "VDD=3.3V T=25°C",
     "expected_value": "168 MHz", "test_method": "Oscilloscope", "priority": "high"},
]


@pytest.mark.unit
class TestTestCaseGenTool:
    def test_name(self) -> None:
        tool = TestCaseGenTool()
        assert tool.name == "test_case_gen"

    def test_schema(self) -> None:
        tool = TestCaseGenTool()
        schema = tool.parameters_schema
        assert "chip_name" in schema["properties"]

    @pytest.mark.asyncio
    async def test_no_pool_returns_error(self) -> None:
        tool = TestCaseGenTool(db_pool=None, llm=None)
        result = await tool.execute(chip_name="STM32F407")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_llm_returns_error(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        tool = TestCaseGenTool(db_pool=pool, llm=None)
        result = await tool.execute(chip_name="STM32F407")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_llm_json_output_parsed(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        llm = AsyncMock()
        llm.generate.return_value = json.dumps(_SAMPLE_CASES)

        tool = TestCaseGenTool(db_pool=pool, llm=llm)
        result = await tool.execute(chip_name="STM32F407")

        assert result["test_case_count"] == 2
        assert result["structured_cases"][0]["test_item"] == "Supply voltage nominal"
        assert result["chip_name"] == "STM32F407"

    @pytest.mark.asyncio
    async def test_llm_code_block_output_parsed(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        llm = AsyncMock()
        llm.generate.return_value = f"```json\n{json.dumps(_SAMPLE_CASES)}\n```"

        tool = TestCaseGenTool(db_pool=pool, llm=llm)
        result = await tool.execute(chip_name="STM32F407")

        assert result["test_case_count"] == 2

    @pytest.mark.asyncio
    async def test_llm_unparsable_output_degrades_gracefully(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        llm = AsyncMock()
        llm.generate.return_value = "Here are your test cases in prose format..."

        tool = TestCaseGenTool(db_pool=pool, llm=llm)
        result = await tool.execute(chip_name="STM32F407")

        # Graceful degradation: raw text returned, structured_cases empty
        assert "test_cases" in result
        assert result["structured_cases"] == []

    @pytest.mark.asyncio
    async def test_search_context_injected(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        llm = AsyncMock()
        llm.generate.return_value = json.dumps(_SAMPLE_CASES)

        search_result = MagicMock()
        search_result.content = "Apply 100nF decoupling cap per VCC pin."
        search = AsyncMock()
        search.search.return_value = [search_result]

        tool = TestCaseGenTool(db_pool=pool, llm=llm, hybrid_search=search)
        result = await tool.execute(chip_name="STM32F407")

        search.search.assert_called_once()
        assert result["test_case_count"] == 2

    @pytest.mark.asyncio
    async def test_search_failure_does_not_block(self) -> None:
        pool = _make_pool(_SAMPLE_PARAMS)
        llm = AsyncMock()
        llm.generate.return_value = json.dumps(_SAMPLE_CASES)

        search = AsyncMock()
        search.search.side_effect = RuntimeError("Search unavailable")

        tool = TestCaseGenTool(db_pool=pool, llm=llm, hybrid_search=search)
        result = await tool.execute(chip_name="STM32F407")

        # Should still succeed — search failure is non-blocking
        assert result["test_case_count"] == 2


@pytest.mark.unit
class TestParseTestCases:
    def test_parse_valid_json_list(self) -> None:
        raw = json.dumps(_SAMPLE_CASES)
        cases = TestCaseGenTool._parse_test_cases(raw)
        assert len(cases) == 2

    def test_parse_code_block(self) -> None:
        raw = f"```json\n{json.dumps(_SAMPLE_CASES)}\n```"
        cases = TestCaseGenTool._parse_test_cases(raw)
        assert len(cases) == 2

    def test_parse_invalid_returns_empty(self) -> None:
        cases = TestCaseGenTool._parse_test_cases("not json at all")
        assert cases == []

    def test_parse_empty_array(self) -> None:
        cases = TestCaseGenTool._parse_test_cases("[]")
        assert cases == []
