"""Unit tests for seed_data alternatives import (§4B3)."""

from __future__ import annotations

import pytest
from pathlib import Path

from scripts.seed_data import import_alternatives


@pytest.mark.unit
class TestSeedAlternatives:
    def test_csv_exists(self) -> None:
        assert Path("tests/fixtures/chip_alternatives_sample.csv").exists()

    def test_csv_has_headers(self) -> None:
        import csv
        with open("tests/fixtures/chip_alternatives_sample.csv") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            assert "original_part" in headers
            assert "alternative_part" in headers
            assert "compat_score" in headers
            assert "is_domestic" in headers

    def test_csv_has_rows(self) -> None:
        import csv
        with open("tests/fixtures/chip_alternatives_sample.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 3

    @pytest.mark.asyncio
    async def test_import_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            await import_alternatives("/nonexistent.csv", None)
