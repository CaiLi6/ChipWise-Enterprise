"""Unit tests for PDFTableExtractor (§3A1)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.pdf_extractor import PDFTableExtractor, ExtractedTable


@pytest.mark.unit
class TestExtractedTable:
    def test_num_rows(self) -> None:
        t = ExtractedTable(rows=[["a", "b"], ["c", "d"]], page=1, tier=1)
        assert t.num_rows == 2

    def test_num_cols(self) -> None:
        t = ExtractedTable(rows=[["a", "b", "c"]], page=1, tier=1)
        assert t.num_cols == 3

    def test_empty_table(self) -> None:
        t = ExtractedTable(rows=[], page=1, tier=1)
        assert t.num_rows == 0
        assert t.num_cols == 0


@pytest.mark.unit
class TestPDFTableExtractor:
    def test_quality_check_high(self) -> None:
        t = ExtractedTable(rows=[["a", "b"], ["c", "d"]], page=1, tier=1, quality_score=0.9)
        assert PDFTableExtractor._quality_check(t)

    def test_quality_check_low(self) -> None:
        t = ExtractedTable(rows=[["a", "b"]], page=1, tier=1, quality_score=0.3)
        assert not PDFTableExtractor._quality_check(t)

    def test_compute_quality_all_filled(self) -> None:
        rows = [["a", "b"], ["c", "d"]]
        assert PDFTableExtractor._compute_quality(rows) == 1.0

    def test_compute_quality_half_empty(self) -> None:
        rows = [["a", ""], ["", "d"]]
        q = PDFTableExtractor._compute_quality(rows)
        assert 0.4 < q < 0.6

    def test_compute_quality_empty(self) -> None:
        assert PDFTableExtractor._compute_quality([]) == 0.0

    def test_parse_html_table(self) -> None:
        html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
        rows = PDFTableExtractor._parse_html_table(html)
        assert len(rows) == 2
        assert rows[0] == ["A", "B"]

    def test_tier1_with_mock_page(self) -> None:
        extractor = PDFTableExtractor()
        page = MagicMock()
        page.extract_tables.return_value = [
            [["Name", "Value"], ["Freq", "168MHz"], ["Voltage", "3.3V"]]
        ]
        tables = extractor._tier1_pdfplumber(page, 1)
        assert len(tables) == 1
        assert tables[0].tier == 1
        assert tables[0].num_rows == 3

    def test_tier1_no_tables(self) -> None:
        extractor = PDFTableExtractor()
        page = MagicMock()
        page.extract_tables.return_value = []
        tables = extractor._tier1_pdfplumber(page, 1)
        assert tables == []

    def test_tier1_with_none_cells(self) -> None:
        extractor = PDFTableExtractor()
        page = MagicMock()
        page.extract_tables.return_value = [[["A", None], [None, "B"]]]
        tables = extractor._tier1_pdfplumber(page, 1)
        assert len(tables) == 1
        assert tables[0].rows[0] == ["A", ""]
