"""PDF 3-tier table extraction: pdfplumber → Camelot → PaddleOCR (§3A1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """A table extracted from a PDF page."""

    rows: list[list[str]]
    page: int
    tier: int  # 1=pdfplumber, 2=camelot, 3=paddleocr
    quality_score: float = 0.0
    bbox: tuple[float, ...] = ()

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return len(self.rows[0]) if self.rows else 0


class PDFTableExtractor:
    """Three-tier progressive PDF table extractor.

    Tier 1 (pdfplumber): Line-based detection, covers ~70% of tables.
    Tier 2 (Camelot): Lattice + stream modes, covers ~20%.
    Tier 3 (PaddleOCR): PP-Structure OCR for scanned images, covers ~10%.
    """

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._paddleocr_engine = None  # Lazy-loaded

    def extract_tables(self, pdf_path: str) -> list[ExtractedTable]:
        """Extract all tables from a PDF using progressive tiers."""
        all_tables: list[ExtractedTable] = []

        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed")
            return all_tables

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_tables = self._extract_page_tables(page, page_num, pdf_path)
                    all_tables.extend(page_tables)
        except Exception:
            logger.exception("Failed to process PDF: %s", pdf_path)

        return all_tables

    def _extract_page_tables(
        self, page: Any, page_num: int, pdf_path: str
    ) -> list[ExtractedTable]:
        """Try each tier for a single page until quality threshold is met."""
        # Tier 1: pdfplumber
        tables = self._tier1_pdfplumber(page, page_num)
        if tables and all(self._quality_check(t) for t in tables):
            return tables

        # Tier 2: Camelot
        tables_t2 = self._tier2_camelot(pdf_path, page_num)
        if tables_t2 and all(self._quality_check(t) for t in tables_t2):
            return tables_t2

        # Tier 3: PaddleOCR (lazy load)
        tables_t3 = self._tier3_paddleocr(pdf_path, page_num)
        if tables_t3:
            return tables_t3

        # Return best-effort Tier 1 results if nothing else worked
        return tables if tables else []

    def _tier1_pdfplumber(self, page: Any, page_num: int) -> list[ExtractedTable]:
        """Tier 1: pdfplumber line-based table detection."""
        tables: list[ExtractedTable] = []
        try:
            raw_tables = page.extract_tables()
            if not raw_tables:
                return tables
            for raw in raw_tables:
                rows = [
                    [cell if cell is not None else "" for cell in row]
                    for row in raw
                    if row
                ]
                if not rows:
                    continue
                table = ExtractedTable(
                    rows=rows, page=page_num, tier=1,
                    quality_score=self._compute_quality(rows),
                )
                tables.append(table)
        except Exception:
            logger.debug("Tier 1 extraction failed for page %d", page_num)
        return tables

    def _tier2_camelot(self, pdf_path: str, page_num: int) -> list[ExtractedTable]:
        """Tier 2: Camelot lattice + stream modes."""
        tables: list[ExtractedTable] = []
        try:
            import camelot
        except ImportError:
            logger.debug("Camelot not installed, skipping Tier 2")
            return tables

        for flavor in ("lattice", "stream"):
            try:
                result = camelot.read_pdf(
                    pdf_path, pages=str(page_num), flavor=flavor
                )
                for t in result:
                    df = t.df
                    rows = df.values.tolist()
                    if not rows:
                        continue
                    table = ExtractedTable(
                        rows=rows, page=page_num, tier=2,
                        quality_score=t.accuracy / 100.0 if hasattr(t, "accuracy") else 0.5,
                    )
                    tables.append(table)
                if tables:
                    break
            except Exception:
                logger.debug("Tier 2 %s failed for page %d", flavor, page_num)
        return tables

    def _tier3_paddleocr(self, pdf_path: str, page_num: int) -> list[ExtractedTable]:
        """Tier 3: PaddleOCR PP-Structure (lazy-loaded)."""
        try:
            if self._paddleocr_engine is None:
                from paddleocr import PPStructure
                self._paddleocr_engine = PPStructure(show_log=False)

            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            page = doc[page_num - 1]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            doc.close()

            import numpy as np
            from PIL import Image
            import io
            img = np.array(Image.open(io.BytesIO(img_bytes)))

            result = self._paddleocr_engine(img)
            tables: list[ExtractedTable] = []
            for item in result:
                if item.get("type") == "table":
                    html = item.get("res", {}).get("html", "")
                    rows = self._parse_html_table(html)
                    if rows:
                        tables.append(ExtractedTable(
                            rows=rows, page=page_num, tier=3,
                            quality_score=0.6,
                        ))
            return tables
        except ImportError:
            logger.debug("PaddleOCR/PyMuPDF not installed, skipping Tier 3")
            return []
        except Exception:
            logger.debug("Tier 3 failed for page %d", page_num, exc_info=True)
            return []

    @staticmethod
    def _parse_html_table(html: str) -> list[list[str]]:
        """Parse an HTML table string into rows."""
        import re
        rows: list[list[str]] = []
        for tr_match in re.finditer(r"<tr>(.*?)</tr>", html, re.DOTALL):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr_match.group(1), re.DOTALL)
            if cells:
                rows.append([c.strip() for c in cells])
        return rows

    @staticmethod
    def _compute_quality(rows: list[list[str]]) -> float:
        """Quality = 1 - (empty cell ratio)."""
        total = sum(len(row) for row in rows)
        if total == 0:
            return 0.0
        empty = sum(1 for row in rows for cell in row if not cell.strip())
        return 1.0 - (empty / total)

    @staticmethod
    def _quality_check(table: ExtractedTable) -> bool:
        """Table passes if empty-cell rate < 30% or quality > 0.7."""
        return table.quality_score > 0.7
