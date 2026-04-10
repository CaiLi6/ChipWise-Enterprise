"""Unit tests for ParamExtractor (§3A2)."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ingestion.param_extractor import ParamExtractor
from src.libs.llm.base import LLMResponse


@pytest.mark.unit
class TestParamExtractor:
    @pytest.fixture
    def llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.generate.return_value = LLMResponse(text=json.dumps([
            {
                "name": "Maximum Clock Frequency",
                "category": "timing",
                "min_value": None,
                "typ_value": "168",
                "max_value": "168",
                "unit": "MHz",
                "condition": "VDD = 3.3V",
            }
        ]))
        return llm

    @pytest.fixture
    def extractor(self, llm: AsyncMock) -> ParamExtractor:
        return ParamExtractor(llm)

    @pytest.mark.asyncio
    async def test_extract_basic(self, extractor: ParamExtractor) -> None:
        table = [["Parameter", "Min", "Typ", "Max", "Unit"],
                 ["Clock Frequency", "-", "168", "168", "MHz"]]
        result = await extractor.extract_from_table(table, "STM32F407", 5)
        assert len(result) == 1
        assert result[0]["name"] == "Maximum Clock Frequency"

    @pytest.mark.asyncio
    async def test_parse_markdown_code_block(self) -> None:
        output = '```json\n[{"name": "VDD", "category": "electrical", "unit": "V"}]\n```'
        result = ParamExtractor._parse_llm_output(output)
        assert len(result) == 1
        assert result[0]["name"] == "VDD"

    @pytest.mark.asyncio
    async def test_parse_plain_json(self) -> None:
        output = '[{"name": "ICC", "category": "electrical", "unit": "mA"}]'
        result = ParamExtractor._parse_llm_output(output)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self) -> None:
        result = ParamExtractor._parse_llm_output("not json at all")
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_json_with_wrapper(self) -> None:
        output = '{"parameters": [{"name": "VDD", "category": "electrical", "unit": "V"}]}'
        result = ParamExtractor._parse_llm_output(output)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_llm_failure_retries(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = [
            Exception("timeout"),
            LLMResponse(text=json.dumps([{"name": "X", "category": "electrical", "unit": "V"}])),
        ]
        extractor = ParamExtractor(llm)
        result = await extractor.extract_from_table([["A"]], "CHIP", 1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_llm_double_failure(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = Exception("timeout")
        extractor = ParamExtractor(llm)
        result = await extractor.extract_from_table([["A"]], "CHIP", 1)
        assert result == []

    @pytest.mark.asyncio
    async def test_with_validator(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = LLMResponse(text=json.dumps([
            {"name": "Freq", "category": "timing", "unit": "MHz", "typ_value": "168"}
        ]))
        validator = MagicMock()
        validator.validate_chip_param.return_value = {"valid": True, "warnings": []}
        extractor = ParamExtractor(llm, validator=validator)
        result = await extractor.extract_from_table([["A"]], "STM32", 1)
        assert len(result) == 1
        assert result[0]["needs_review"] is False

    @pytest.mark.asyncio
    async def test_validator_with_warnings(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = LLMResponse(text=json.dumps([
            {"name": "Freq", "category": "timing", "unit": "MHz", "typ_value": "-50"}
        ]))
        validator = MagicMock()
        validator.validate_chip_param.return_value = {
            "valid": True, "warnings": ["Negative frequency"]
        }
        extractor = ParamExtractor(llm, validator=validator)
        result = await extractor.extract_from_table([["A"]], "STM32", 1)
        assert result[0]["needs_review"] is True
