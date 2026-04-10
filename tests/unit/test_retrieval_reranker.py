"""Unit tests for CoreReranker — mock reranker with fallback."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.types import RetrievalResult
from src.libs.reranker.base import BaseReranker, NoneReranker, RerankResult
from src.retrieval.reranker import CoreReranker


def _make_candidates(n: int = 5) -> list[RetrievalResult]:
    return [
        RetrievalResult(chunk_id=f"c{i}", doc_id=f"d{i}", content=f"content {i}", score=0.5)
        for i in range(n)
    ]


@pytest.mark.unit
class TestCoreReranker:
    @pytest.mark.asyncio
    async def test_primary_reranker_used(self) -> None:
        primary = AsyncMock(spec=BaseReranker)
        primary.rerank.return_value = [
            RerankResult(index=2, score=0.95, text="content 2"),
            RerankResult(index=0, score=0.80, text="content 0"),
        ]
        cr = CoreReranker(primary)
        results = await cr.rerank("query", _make_candidates(), top_k=2)
        assert len(results) == 2
        assert results[0].chunk_id == "c2"
        assert results[0].score == 0.95
        assert results[0].metadata["rerank_method"] == "primary"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self) -> None:
        primary = AsyncMock(spec=BaseReranker)
        primary.rerank.side_effect = ConnectionError("service down")
        cr = CoreReranker(primary)
        candidates = _make_candidates(3)
        results = await cr.rerank("query", candidates, top_k=3)
        assert len(results) == 3
        assert results[0].metadata["rerank_method"] == "fallback"

    @pytest.mark.asyncio
    async def test_top_k_respected(self) -> None:
        primary = AsyncMock(spec=BaseReranker)
        primary.rerank.return_value = [
            RerankResult(index=i, score=0.9 - i * 0.1, text=f"t{i}")
            for i in range(5)
        ]
        cr = CoreReranker(primary)
        results = await cr.rerank("q", _make_candidates(), top_k=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_empty_candidates(self) -> None:
        primary = AsyncMock(spec=BaseReranker)
        primary.rerank.return_value = []
        cr = CoreReranker(primary)
        results = await cr.rerank("q", [], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_preserves_metadata(self) -> None:
        primary = AsyncMock(spec=BaseReranker)
        primary.rerank.return_value = [RerankResult(index=0, score=0.9, text="t")]
        cr = CoreReranker(primary)
        candidates = [RetrievalResult(
            chunk_id="c0", doc_id="d0", content="text",
            source="vector", page_number=42, metadata={"extra": "val"},
        )]
        results = await cr.rerank("q", candidates, top_k=1)
        assert results[0].page_number == 42
        assert results[0].source == "vector"
