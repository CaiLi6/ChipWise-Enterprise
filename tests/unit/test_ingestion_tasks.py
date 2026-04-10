"""Unit tests for Ingestion tasks (§3B2)."""

from __future__ import annotations

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ingestion.tasks import (
    validate_and_dedup,
    extract_text,
    chunk_text,
    create_ingestion_chain,
)


@pytest.mark.unit
class TestIngestionTasks:
    def test_validate_and_dedup_file_not_found(self) -> None:
        result = validate_and_dedup.__wrapped__({"file_path": "/nonexistent"})
        assert result["skipped"] is True
        assert "error" in result

    def test_validate_and_dedup_success(self, tmp_path: Path) -> None:
        f = tmp_path / "test.pdf"
        f.write_text("dummy content")
        result = validate_and_dedup.__wrapped__({"file_path": str(f)})
        assert result["skipped"] is False
        assert "file_hash" in result
        assert len(result["file_hash"]) == 64  # SHA256 hex

    def test_chunk_text_skipped(self) -> None:
        result = chunk_text.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_chunk_text_normal(self) -> None:
        doc_info = {
            "skipped": False,
            "text": "# Introduction\nThis is a test.\n# Parameters\nVDD = 3.3V",
            "file_hash": "abc123",
        }
        result = chunk_text.__wrapped__(doc_info)
        assert "chunks" in result
        assert len(result["chunks"]) >= 1

    def test_create_ingestion_chain(self) -> None:
        chain = create_ingestion_chain("http://example.com/doc.pdf", "ST", user_id=1)
        assert chain is not None
