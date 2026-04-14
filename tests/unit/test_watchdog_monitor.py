"""Unit tests for DatasheetWatchdog (§3C2)."""

from __future__ import annotations

import time

import pytest
from src.ingestion.watchdog_monitor import DEBOUNCE_SECONDS, DatasheetWatchdog


@pytest.mark.unit
class TestDatasheetWatchdog:
    def test_filter_non_pdf(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd.on_file_created("/tmp/watch/doc.txt")
        assert len(wd._pending) == 0

    def test_filter_tmp_file(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd.on_file_created("/tmp/watch/~$doc.pdf")
        assert len(wd._pending) == 0

    def test_filter_part_file(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd.on_file_created("/tmp/watch/doc.pdf.part")
        assert len(wd._pending) == 0

    def test_accept_pdf(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd.on_file_created("/tmp/watch/STM32F407.pdf")
        assert "/tmp/watch/STM32F407.pdf" in wd._pending

    def test_debounce(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd.on_file_created("/tmp/watch/test.pdf")
        # Not yet debounced
        ready = wd.process_pending()
        assert len(ready) == 0

    def test_debounce_expired(self) -> None:
        wd = DatasheetWatchdog("/tmp/watch")
        wd._pending["/tmp/watch/old.pdf"] = time.time() - DEBOUNCE_SECONDS - 1
        ready = wd.process_pending()
        assert "/tmp/watch/old.pdf" in ready

    def test_detect_manufacturer(self) -> None:
        assert DatasheetWatchdog._detect_manufacturer("/data/documents/ST/doc.pdf") == "ST"
        assert DatasheetWatchdog._detect_manufacturer("/data/random/doc.pdf") == "unknown"
