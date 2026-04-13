"""Unit tests for design rule extraction from ingestion (§5B2)."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock

from src.ingestion.design_rule_extractor import extract_design_rules
from src.core.types import Chunk


def _make_chunk(content: str, page: int = 1, section: str = "") -> Chunk:
    return Chunk(
        chunk_id=f"c{page}",
        doc_id="doc1",
        content=content,
        page_number=page,
        metadata={"section_title": section},
    )


_RULE_JSON = json.dumps([
    {"rule_type": "decoupling_cap", "rule_text": "Add 100nF bypass cap per VCC pin", "severity": "mandatory"},
])


@pytest.mark.unit
class TestExtractDesignRules:
    @pytest.mark.asyncio
    async def test_extracts_rule_from_relevant_chunk(self) -> None:
        chunks = [_make_chunk("Add decoupling capacitors near power pins.", 1, "Power Supply")]
        llm = AsyncMock()
        llm.generate.return_value = _RULE_JSON

        rules = await extract_design_rules(chunks, chip_id=1, llm=llm)

        assert len(rules) == 1
        assert rules[0]["rule_type"] == "decoupling_cap"
        assert rules[0]["chip_id"] == 1
        assert rules[0]["source_page"] == 1
        assert rules[0]["source_section"] == "Power Supply"

    @pytest.mark.asyncio
    async def test_irrelevant_chunks_skipped(self) -> None:
        chunks = [_make_chunk("This chip supports UART, SPI, and I2C peripherals.", 2)]
        llm = AsyncMock()

        rules = await extract_design_rules(chunks, chip_id=1, llm=llm)

        llm.generate.assert_not_called()
        assert rules == []

    @pytest.mark.asyncio
    async def test_layout_keyword_triggers_extraction(self) -> None:
        chunks = [_make_chunk("Follow the layout guidelines to minimize EMI.", 3, "PCB Layout")]
        llm = AsyncMock()
        llm.generate.return_value = json.dumps([
            {"rule_type": "layout", "rule_text": "Minimize trace length for high-speed signals", "severity": "recommendation"}
        ])

        rules = await extract_design_rules(chunks, chip_id=2, llm=llm)

        assert rules[0]["rule_type"] == "layout"
        assert rules[0]["chip_id"] == 2

    @pytest.mark.asyncio
    async def test_llm_unparsable_skipped(self) -> None:
        chunks = [_make_chunk("ESD protection is important for GPIO pins.", 4)]
        llm = AsyncMock()
        llm.generate.return_value = "Here are the rules in prose..."  # Non-JSON

        rules = await extract_design_rules(chunks, chip_id=1, llm=llm)

        assert rules == []

    @pytest.mark.asyncio
    async def test_llm_failure_non_blocking(self) -> None:
        chunks = [_make_chunk("注意：推荐在电源引脚附近放置退耦电容。", 5)]
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        rules = await extract_design_rules(chunks, chip_id=1, llm=llm)

        # Should not raise, just return empty
        assert rules == []

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self) -> None:
        llm = AsyncMock()
        rules = await extract_design_rules([], chip_id=1, llm=llm)
        assert rules == []

    @pytest.mark.asyncio
    async def test_multiple_rules_from_single_chunk(self) -> None:
        chunks = [_make_chunk("Power sequence and thermal management are critical.", 6)]
        llm = AsyncMock()
        llm.generate.return_value = json.dumps([
            {"rule_type": "power_seq", "rule_text": "VDDIO before VDD", "severity": "mandatory"},
            {"rule_type": "thermal", "rule_text": "Keep junction temp below 85°C", "severity": "recommendation"},
        ])

        rules = await extract_design_rules(chunks, chip_id=3, llm=llm)

        assert len(rules) == 2
        assert {r["rule_type"] for r in rules} == {"power_seq", "thermal"}
