"""Unit tests for TableChunker (§3A4)."""

from __future__ import annotations

import pytest

from src.ingestion.chunking.table_chunker import TableChunker


@pytest.mark.unit
class TestTableChunker:
    def test_empty_table(self) -> None:
        chunker = TableChunker()
        assert chunker.chunk_table([]) == []

    def test_small_table_single_chunk(self) -> None:
        rows = [["Name", "Value"], ["Freq", "168MHz"], ["VDD", "3.3V"]]
        chunker = TableChunker(chunk_size=5000)
        chunks = chunker.chunk_table(rows, chip_name="STM32", section="Electrical", page=5, doc_id="d1")
        assert len(chunks) == 1
        assert chunks[0].metadata["is_table"] is True
        assert chunks[0].metadata["chip_name"] == "STM32"
        assert "| Name | Value |" in chunks[0].content

    def test_markdown_format(self) -> None:
        rows = [["A", "B"], ["1", "2"]]
        chunker = TableChunker()
        chunks = chunker.chunk_table(rows, doc_id="d1")
        content = chunks[0].content
        assert "| A | B |" in content
        assert "| --- | --- |" in content
        assert "| 1 | 2 |" in content

    def test_large_table_splits(self) -> None:
        header = ["Parameter", "Min", "Typ", "Max", "Unit"]
        data = [[f"Param{i}", "0", str(i), str(i * 2), "V"] for i in range(100)]
        rows = [header] + data
        chunker = TableChunker(chunk_size=300)
        chunks = chunker.chunk_table(rows, chip_name="X", doc_id="d1")
        assert len(chunks) > 1
        # Every chunk should contain the header
        for c in chunks:
            assert "| Parameter | Min | Typ | Max | Unit |" in c.content

    def test_metadata_page(self) -> None:
        rows = [["A"], ["B"]]
        chunker = TableChunker()
        chunks = chunker.chunk_table(rows, page=7, doc_id="d1")
        assert chunks[0].page_number == 7
        assert chunks[0].metadata["page"] == 7

    def test_to_markdown_uneven_columns(self) -> None:
        rows = [["A", "B", "C"], ["1"]]
        md = TableChunker._to_markdown_table(rows)
        # Second row should be padded
        assert "| 1 |  |  |" in md

    def test_chunk_index(self) -> None:
        rows = [["H1", "H2"]] + [[f"r{i}", f"v{i}"] for i in range(50)]
        chunker = TableChunker(chunk_size=200)
        chunks = chunker.chunk_table(rows, doc_id="d1", start_index=5)
        assert chunks[0].chunk_index == 5
