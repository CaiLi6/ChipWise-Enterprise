"""Retriever wrapper for evaluation — thin facade over MilvusStore + reranker."""

from __future__ import annotations

import logging
from typing import Any

from src.core.types import RetrievalResult

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    collection_name: str,
    top_k: int = 10,
    use_reranker: bool = True,
) -> list[RetrievalResult]:
    """Run hybrid search on *collection_name* and optionally rerank.

    Args:
        query: The user query.
        collection_name: Milvus collection to search.
        top_k: Number of results to return.
        use_reranker: Whether to apply bce-reranker.

    Returns:
        List of :class:`RetrievalResult` sorted by score descending.
    """
    try:
        from src.libs.embedding.factory import create_embedding

        embedder = create_embedding()
        query_embedding = embedder.embed([query])[0]

        from src.libs.vector_store.factory import create_vector_store

        store = create_vector_store()
        raw_results = store.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            top_k=top_k * 3 if use_reranker else top_k,
        )

        results = [
            RetrievalResult(
                chunk_id=r.get("chunk_id", ""),
                doc_id=r.get("doc_id", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                metadata=r.get("metadata", {}),
            )
            for r in raw_results
        ]

        if use_reranker and results:
            results = _rerank(query, results, top_k)

        return results[:top_k]

    except Exception as e:
        logger.error("Retrieval failed for collection %s: %s", collection_name, e)
        return []


def _rerank(
    query: str, results: list[RetrievalResult], top_k: int
) -> list[RetrievalResult]:
    """Apply bce-reranker to results."""
    try:
        from src.libs.reranker.factory import create_reranker

        reranker = create_reranker()
        passages = [r.content for r in results]
        scores = reranker.rerank(query, passages)

        for result, score in zip(results, scores):
            result.score = score

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]
    except Exception as e:
        logger.warning("Reranker unavailable: %s", e)
        return results[:top_k]
