"""Unit tests for Errata document parser (§5B3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from unittest.mock import AsyncMock

from src.ingestion.errata_parser import parse_errata_document


_FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_errata.txt"

_PARSED_ENTRIES = [
    {
        "errata_code": "ES0182-1",
        "title": "ADC wrong conversion result",
        "severity": "major",
        "status": "workaround",
        "affected_peripherals": ["ADC1", "ADC2", "ADC3"],
        "workaround": "Disable DMA after each conversion.",
    },
    {
        "errata_code": "ES0182-2",
        "title": "I2C FM+ issue",
        "severity": "minor",
        "status": "open",
        "affected_peripherals": ["I2C1"],
        "workaround": "Use standard mode.",
    },
]


@pytest.mark.unit
class TestErrataParser:
    def test_fixture_file_exists(self) -> None:
        assert _FIXTURE.exists(), f"Missing fixture: {_FIXTURE}"

    @pytest.mark.asyncio
    async def test_parse_returns_list_of_entries(self) -> None:
        text = _FIXTURE.read_text(encoding="utf-8")
        llm = AsyncMock()
        llm.generate.return_value = json.dumps(_PARSED_ENTRIES)

        entries = await parse_errata_document(text, chip_id=1, llm=llm)

        assert isinstance(entries, list)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_chip_id_injected_into_entries(self) -> None:
        text = "Errata ID: E1\nSeverity: Minor\nPeripherals: SPI"
        llm = AsyncMock()
        llm.generate.return_value = json.dumps([_PARSED_ENTRIES[0]])

        entries = await parse_errata_document(text, chip_id=42, llm=llm)

        assert all(e["chip_id"] == 42 for e in entries)

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self) -> None:
        llm = AsyncMock()
        entries = await parse_errata_document("", chip_id=1, llm=llm)

        llm.generate.assert_not_called()
        assert entries == []

    @pytest.mark.asyncio
    async def test_llm_code_block_output_parsed(self) -> None:
        text = "Errata text here"
        llm = AsyncMock()
        llm.generate.return_value = f"```json\n{json.dumps(_PARSED_ENTRIES)}\n```"

        entries = await parse_errata_document(text, chip_id=1, llm=llm)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_llm_unparsable_returns_empty(self) -> None:
        text = "Some errata text"
        llm = AsyncMock()
        llm.generate.return_value = "Here are the errata in prose form..."

        entries = await parse_errata_document(text, chip_id=1, llm=llm)
        assert entries == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM unavailable")

        entries = await parse_errata_document("Some errata text", chip_id=1, llm=llm)
        assert entries == []

    @pytest.mark.asyncio
    async def test_affected_peripherals_list(self) -> None:
        text = "Errata for ADC and I2C peripherals."
        llm = AsyncMock()
        entry = {
            "errata_code": "E1", "title": "ADC issue", "severity": "major",
            "status": "open", "affected_peripherals": ["ADC1", "ADC2"], "workaround": "None"
        }
        llm.generate.return_value = json.dumps([entry])

        entries = await parse_errata_document(text, chip_id=1, llm=llm)
        assert isinstance(entries[0]["affected_peripherals"], list)
        assert "ADC1" in entries[0]["affected_peripherals"]
