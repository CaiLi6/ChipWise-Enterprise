"""Smoke test: verify all chunking strategies can ingest + split text without error.

Marked @pytest.mark.integration — NOT run in default pytest.
"""

from __future__ import annotations

import pytest
from src.core.types import Chunk
from src.ingestion.chunking.factory import create_chunker

_SAMPLE_TEXT = """\
# 1.0 Overview
The STM32F407 is a high-performance microcontroller with ARM Cortex-M4 core.
It features 168 MHz maximum frequency, 1 MB Flash, and 192 KB SRAM.

# 2.0 Electrical Characteristics
Supply voltage: 1.8V to 3.6V. Operating temperature: -40°C to +85°C.
Maximum current consumption in Run mode: 150 mA.

# 3.0 Pin Configuration
The device is available in LQFP100 and LQFP144 packages.
GPIO pins support alternate functions including USART, SPI, and I2C.

# 4.0 ADC
12-bit successive approximation ADC with up to 24 channels.
Conversion time: 0.5 us at 12-bit resolution.
""" * 3  # Repeat for enough text


_STRATEGIES = ["datasheet", "fine", "coarse", "parent_child"]

pytestmark = [pytest.mark.integration, pytest.mark.integration_nollm]


class TestChunkingStrategiesSmoke:
    """Smoke tests: each strategy produces valid chunks from sample text."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_strategy_produces_chunks(self, strategy: str) -> None:
        chunker = create_chunker(strategy)
        chunks = chunker.split(_SAMPLE_TEXT, doc_id="smoke_test")
        assert len(chunks) > 0
        for c in chunks:
            assert isinstance(c, Chunk)
            assert c.content.strip()
            assert c.doc_id == "smoke_test"

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_strategy_empty_text(self, strategy: str) -> None:
        chunker = create_chunker(strategy)
        assert chunker.split("", doc_id="empty") == []
        assert chunker.split("   ", doc_id="empty") == []

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_chunk_indices_unique(self, strategy: str) -> None:
        chunker = create_chunker(strategy)
        chunks = chunker.split(_SAMPLE_TEXT, doc_id="idx_test")
        indices = [c.chunk_index for c in chunks]
        assert len(set(indices)) == len(indices), f"Duplicate indices in {strategy}"
