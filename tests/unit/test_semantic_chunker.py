"""Unit tests for SemanticChunker (embedding-based breakpoints)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from src.ingestion.chunking.semantic_chunker import SemanticChunker


@pytest.mark.unit
class TestSemanticChunker:
    """Verify semantic chunker embedding breakpoint logic."""

    def _make_chunker(self, **kwargs) -> SemanticChunker:
        return SemanticChunker(**kwargs)

    def test_fallback_when_embedding_unavailable(self) -> None:
        """When embedding service is down, fallback split by size."""
        chunker = self._make_chunker(min_size=50, max_size=200)
        text = "Sentence one. " * 30  # ~420 chars
        with patch.object(chunker, "_embed_sentences", return_value=[]):
            chunks = chunker.split(text, doc_id="doc-1")
        assert len(chunks) >= 1
        for c in chunks:
            assert c.doc_id == "doc-1"

    def test_breakpoints_with_mock_embeddings(self) -> None:
        """Mock embeddings with low similarity at index 2 → expect a break."""
        chunker = self._make_chunker(similarity_threshold=0.5, min_size=10, max_size=5000)
        sentences = [
            "The STM32F407 runs at 168 MHz.",
            "It has 1 MB Flash and 192 KB SRAM.",
            "Supply voltage ranges from 1.8V to 3.6V.",
            "Maximum current is 150 mA in Run mode.",
        ]
        text = " ".join(sentences)

        # Simulate embeddings: first two similar, then a break
        mock_embeddings = [
            [1.0, 0.0, 0.0],  # sentence 0
            [0.95, 0.05, 0.0],  # sentence 1 — similar to 0
            [0.0, 0.0, 1.0],  # sentence 2 — dissimilar (break here)
            [0.05, 0.0, 0.95],  # sentence 3 — similar to 2
        ]
        with patch.object(chunker, "_embed_sentences", return_value=mock_embeddings):
            chunks = chunker.split(text, doc_id="doc-sem")
        assert len(chunks) >= 2, f"Expected >=2 chunks from breakpoint, got {len(chunks)}"

    def test_empty_text_returns_empty(self) -> None:
        chunker = self._make_chunker()
        chunks = chunker.split("", doc_id="empty")
        assert chunks == []

    def test_single_sentence_no_break(self) -> None:
        chunker = self._make_chunker(min_size=5, max_size=5000)
        text = "Only one sentence here."
        with patch.object(chunker, "_embed_sentences", return_value=[[1.0, 0.0]]):
            chunks = chunker.split(text, doc_id="single")
        assert len(chunks) == 1
