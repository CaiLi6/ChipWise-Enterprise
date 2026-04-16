"""Unit tests for HybridSearch BM25 mode — mock embedding + vector store."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.core.types import RetrievalResult
from src.libs.embedding.base import BaseEmbedding, EmbeddingResult
from src.libs.vector_store.base import BaseVectorStore
from src.retrieval.hybrid_search import HybridSearch


def _make_results(n: int = 3) -> list[RetrievalResult]:
    return [
        RetrievalResult(chunk_id=f"c{i}", doc_id=f"d{i}", content=f"text{i}", score=0.9 - i * 0.1)
        for i in range(n)
    ]


@pytest.mark.unit
class TestHybridSearchBM25:
    @pytest.fixture
    def mock_embedding(self) -> AsyncMock:
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(
            dense=[[0.1] * 1024],
            sparse=[],
            dimensions=1024,
        )
        return emb

    @pytest.fixture
    def mock_store(self) -> AsyncMock:
        store = AsyncMock(spec=BaseVectorStore)
        store.hybrid_search.return_value = _make_results(3)
        store.query.return_value = _make_results(3)
        return store

    @pytest.mark.asyncio
    async def test_bm25_passes_raw_text(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        hs = HybridSearch(mock_embedding, mock_store, sparse_method="bm25")
        results = await hs.search("STM32F407 clock speed", top_k=10)
        assert len(results) == 3
        mock_store.hybrid_search.assert_called_once()
        kw = mock_store.hybrid_search.call_args.kwargs
        assert kw["sparse_text"] == "STM32F407 clock speed"
        assert kw["sparse_method"] == "bm25"

    @pytest.mark.asyncio
    async def test_bm25_does_not_request_sparse_embedding(
        self, mock_embedding: AsyncMock, mock_store: AsyncMock,
    ) -> None:
        hs = HybridSearch(mock_embedding, mock_store, sparse_method="bm25")
        await hs.search("test query")
        mock_embedding.encode.assert_called_once_with(["test query"], return_sparse=False)

    @pytest.mark.asyncio
    async def test_bm25_fallback_to_dense(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        mock_store.hybrid_search.side_effect = RuntimeError("bm25 field missing")
        hs = HybridSearch(mock_embedding, mock_store, sparse_method="bm25")
        results = await hs.search("test query")
        assert len(results) == 3
        mock_store.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_bm25_empty_embedding_returns_empty(self, mock_store: AsyncMock) -> None:
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(dense=[], sparse=[], dimensions=0)
        hs = HybridSearch(emb, mock_store, sparse_method="bm25")
        results = await hs.search("test")
        assert results == []
        mock_store.hybrid_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_bgem3_default_unchanged(self, mock_store: AsyncMock) -> None:
        """Default sparse_method='bgem3' still works as before."""
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(
            dense=[[0.1] * 1024],
            sparse=[{1: 0.5, 2: 0.3}],
            dimensions=1024,
        )
        hs = HybridSearch(emb, mock_store)
        results = await hs.search("test query")
        assert len(results) == 3
        emb.encode.assert_called_once_with(["test query"], return_sparse=True)
        mock_store.hybrid_search.assert_called_once()
        kw = mock_store.hybrid_search.call_args.kwargs
        assert kw.get("sparse_method", "bgem3") == "bgem3"

    @pytest.mark.asyncio
    async def test_bm25_filters_passed_through(
        self, mock_embedding: AsyncMock, mock_store: AsyncMock,
    ) -> None:
        hs = HybridSearch(mock_embedding, mock_store, sparse_method="bm25")
        await hs.search("query", filters={"part_number": "STM32F407"})
        kw = mock_store.hybrid_search.call_args.kwargs
        assert kw["filters"] == {"part_number": "STM32F407"}

    @pytest.mark.asyncio
    async def test_bm25_top_k_passed_through(
        self, mock_embedding: AsyncMock, mock_store: AsyncMock,
    ) -> None:
        hs = HybridSearch(mock_embedding, mock_store, sparse_method="bm25")
        await hs.search("query", top_k=5)
        kw = mock_store.hybrid_search.call_args.kwargs
        assert kw["top_k"] == 5
