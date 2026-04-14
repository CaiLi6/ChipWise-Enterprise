"""Unit tests for ParentChildChunker (small-to-big strategy)."""

from __future__ import annotations

import pytest
from src.ingestion.chunking.parent_child_chunker import ParentChildChunker


@pytest.mark.unit
class TestParentChildChunker:
    """Verify parent/child chunk creation and metadata."""

    def _sample_text(self) -> str:
        return (
            "# Overview\n"
            "The STM32F407 is a high-performance ARM Cortex-M4 microcontroller. "
            "It features 168 MHz, 1 MB Flash, and 192 KB SRAM. "
            "The device supports multiple communication interfaces.\n\n"
            "# Electrical\n"
            "Supply voltage: 1.8V to 3.6V. "
            "Operating temperature: -40C to +85C. "
            "Maximum current consumption in Run mode: 150 mA. "
            "Standby current is less than 2 uA.\n\n"
            "# Pinout\n"
            "Available in LQFP100 and LQFP144 packages. "
            "GPIO pins support USART, SPI, I2C alternate functions.\n"
        ) * 3  # Repeat to ensure enough text for parents

    def test_produces_parent_and_child_chunks(self) -> None:
        chunker = ParentChildChunker(child_size=64, parent_size=256, child_overlap=8)
        chunks = chunker.split(self._sample_text(), doc_id="pc-1")
        parents = [c for c in chunks if c.metadata.get("is_parent")]
        children = [c for c in chunks if not c.metadata.get("is_parent")]
        assert len(parents) >= 1, "Should produce at least one parent"
        assert len(children) >= 1, "Should produce at least one child"

    def test_child_references_parent(self) -> None:
        chunker = ParentChildChunker(child_size=64, parent_size=256, child_overlap=8)
        chunks = chunker.split(self._sample_text(), doc_id="pc-2")
        children = [c for c in chunks if not c.metadata.get("is_parent")]
        for child in children:
            assert "parent_id" in child.metadata, "Child must reference parent_id"

    def test_child_size_within_bounds(self) -> None:
        child_size = 100
        chunker = ParentChildChunker(child_size=child_size, parent_size=512, child_overlap=16)
        chunks = chunker.split(self._sample_text(), doc_id="pc-3")
        children = [c for c in chunks if not c.metadata.get("is_parent")]
        for child in children:
            # Allow some tolerance for word boundaries
            assert len(child.content) <= child_size * 2, (
                f"Child chunk too large: {len(child.content)} > {child_size * 2}"
            )

    def test_empty_text(self) -> None:
        chunker = ParentChildChunker()
        chunks = chunker.split("", doc_id="empty")
        assert chunks == []
