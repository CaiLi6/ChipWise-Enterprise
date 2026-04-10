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
    extract_tables,
    extract_structured_params,
    chunk_text,
    embed_chunks,
    store_vectors,
    store_metadata,
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
        c = create_ingestion_chain("http://example.com/doc.pdf", "ST", user_id=1)
        assert c is not None

    def test_extract_text_skipped(self) -> None:
        result = extract_text.__wrapped__({"skipped": True})
        assert result["skipped"] is True
        assert "text" not in result

    def test_extract_tables_skipped(self) -> None:
        result = extract_tables.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_extract_structured_params_skipped(self) -> None:
        result = extract_structured_params.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_embed_chunks_skipped(self) -> None:
        result = embed_chunks.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_store_vectors_skipped(self) -> None:
        result = store_vectors.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_store_metadata_skipped(self) -> None:
        result = store_metadata.__wrapped__({"skipped": True})
        assert result["skipped"] is True

    def test_store_vectors_counts_chunks(self) -> None:
        doc_info = {"skipped": False, "chunks": [{"id": 1}, {"id": 2}]}
        result = store_vectors.__wrapped__(doc_info)
        assert result["vector_count"] == 2
