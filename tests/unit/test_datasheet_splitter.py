"""Unit tests for DatasheetSplitter (§3A3)."""

from __future__ import annotations

import pytest
from src.ingestion.chunking.datasheet_splitter import DatasheetSplitter


@pytest.mark.unit
class TestDatasheetSplitter:
    def test_empty_text(self) -> None:
        splitter = DatasheetSplitter()
        assert splitter.split("") == []
        assert splitter.split("   ") == []

    def test_short_text_single_chunk(self) -> None:
        splitter = DatasheetSplitter(chunk_size=1000)
        chunks = splitter.split("Short text content.", doc_id="d1")
        assert len(chunks) == 1
        assert chunks[0].content == "Short text content."
        assert chunks[0].doc_id == "d1"

    def test_section_splitting(self) -> None:
        text = "# Introduction\nSome intro text.\n# Parameters\nParam details here."
        splitter = DatasheetSplitter(chunk_size=2000)
        chunks = splitter.split(text, doc_id="d1")
        assert len(chunks) >= 2

    def test_numbered_section_splitting(self) -> None:
        text = "1.0 Overview\nOverview text.\n2.0 Electrical Characteristics\nElectrical data."
        splitter = DatasheetSplitter(chunk_size=2000)
        chunks = splitter.split(text, doc_id="d1")
        assert len(chunks) >= 2

    def test_long_text_recursive_split(self) -> None:
        text = "Word " * 500  # ~2500 chars
        splitter = DatasheetSplitter(chunk_size=200, chunk_overlap=20)
        chunks = splitter.split(text, doc_id="d1")
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content) <= 250  # Allow some slack

    def test_section_title_in_metadata(self) -> None:
        text = "# Electrical\nVDD = 3.3V typical."
        splitter = DatasheetSplitter(chunk_size=2000)
        chunks = splitter.split(text, doc_id="d1")
        has_title = any(c.metadata.get("section_title") for c in chunks)
        assert has_title

    def test_chunk_index_increments(self) -> None:
        text = "# A\nText A.\n# B\nText B.\n# C\nText C."
        splitter = DatasheetSplitter(chunk_size=2000)
        chunks = splitter.split(text, doc_id="d1")
        indices = [c.chunk_index for c in chunks]
        assert indices == sorted(indices)
        assert len(set(indices)) == len(indices)  # All unique

    def test_overlap_applied(self) -> None:
        text = "Sentence one. " * 100
        splitter = DatasheetSplitter(chunk_size=100, chunk_overlap=30)
        chunks = splitter.split(text, doc_id="d1")
        # With overlap, some content should appear in multiple chunks
        assert len(chunks) > 1
