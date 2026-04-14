"""Reranker orchestration with graceful fallback (§2B3)."""

from __future__ import annotations

import logging

from src.core.types import RetrievalResult
from src.libs.reranker.base import BaseReranker, NoneReranker

logger = logging.getLogger(__name__)


class CoreReranker:
    """Wraps a primary reranker with automatic fallback to NoneReranker."""

    def __init__(
        self,
        reranker: BaseReranker,
        fallback: NoneReranker | None = None,
    ) -> None:
        self._reranker = reranker
        self._fallback = fallback or NoneReranker()

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """Rerank candidates. Falls back to original order on error."""
        documents = [c.content for c in candidates]
        method = "primary"

        try:
            results = await self._reranker.rerank(query, documents, top_k=top_k)
        except Exception:
            logger.warning("Reranker failed, falling back to NoneReranker", exc_info=True)
            results = await self._fallback.rerank(query, documents, top_k=top_k)
            method = "fallback"

        # Map reranked scores back to RetrievalResult objects
        reranked: list[RetrievalResult] = []
        for r in results:
            if r.index < len(candidates):
                candidate = candidates[r.index]
                reranked.append(RetrievalResult(
                    chunk_id=candidate.chunk_id,
                    doc_id=candidate.doc_id,
                    content=candidate.content,
                    score=r.score,
                    source=candidate.source,
                    page_number=candidate.page_number,
                    metadata={**candidate.metadata, "rerank_method": method},
                ))

        logger.debug("Reranked %d → %d candidates (method=%s)", len(candidates), len(reranked), method)
        return reranked
