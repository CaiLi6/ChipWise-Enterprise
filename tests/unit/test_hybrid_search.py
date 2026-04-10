"""Unit tests for HybridSearch — mock embedding + vector store."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from typing import Any

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
class TestHybridSearch:
    @pytest.fixture
    def mock_embedding(self) -> AsyncMock:
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(
            dense=[[0.1] * 1024],
            sparse=[{1: 0.5, 2: 0.3}],
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
    async def test_hybrid_search_normal(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        hs = HybridSearch(mock_embedding, mock_store)
        results = await hs.search("STM32F4 clock speed", top_k=10)
        assert len(results) == 3
        mock_store.hybrid_search.assert_called_once()
        mock_store.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_dense_on_hybrid_error(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        mock_store.hybrid_search.side_effect = RuntimeError("hybrid failed")
        hs = HybridSearch(mock_embedding, mock_store)
        results = await hs.search("test query")
        assert len(results) == 3
        mock_store.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_dense_only_when_no_sparse(self, mock_store: AsyncMock) -> None:
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(dense=[[0.1] * 1024], sparse=[], dimensions=1024)
        hs = HybridSearch(emb, mock_store)
        results = await hs.search("test")
        mock_store.query.assert_called_once()
        mock_store.hybrid_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_embedding(self, mock_store: AsyncMock) -> None:
        emb = AsyncMock(spec=BaseEmbedding)
        emb.encode.return_value = EmbeddingResult(dense=[], sparse=[], dimensions=0)
        hs = HybridSearch(emb, mock_store)
        results = await hs.search("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_filters_passed_through(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        hs = HybridSearch(mock_embedding, mock_store)
        await hs.search("query", filters={"part_number": "STM32F407"})
        call_kwargs = mock_store.hybrid_search.call_args.kwargs
        assert call_kwargs.get("filters") == {"part_number": "STM32F407"}

    @pytest.mark.asyncio
    async def test_top_k_passed_through(self, mock_embedding: AsyncMock, mock_store: AsyncMock) -> None:
        hs = HybridSearch(mock_embedding, mock_store)
        await hs.search("query", top_k=5)
        call_kwargs = mock_store.hybrid_search.call_args.kwargs
        assert call_kwargs.get("top_k") == 5
