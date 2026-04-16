"""Hybrid search: dense + sparse vector fusion via Milvus RRF (§2B1).

Supports two sparse methods, switchable via ``sparse_method``:
- ``bgem3``: BGE-M3 sparse embedding vectors (default)
- ``bm25``:  Milvus 2.5 native BM25 full-text search
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.types import RetrievalResult
from src.libs.embedding.base import BaseEmbedding
from src.libs.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class HybridSearch:
    """Combines BGE-M3 dense + sparse vectors with Milvus RRFRanker.

    Falls back to dense-only search if sparse encoding fails.
    """

    def __init__(
        self,
        embedding_client: BaseEmbedding,
        vector_store: BaseVectorStore,
        sparse_method: str = "bgem3",
    ) -> None:
        self._embedding = embedding_client
        self._vector_store = vector_store
        self._sparse_method = sparse_method

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        """Encode query and perform hybrid search."""

        if self._sparse_method == "bm25":
            return await self._search_bm25(query, top_k, filters, collection)

        return await self._search_bgem3(query, top_k, filters, collection)

    async def _search_bm25(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
        collection: str,
    ) -> list[RetrievalResult]:
        """BM25 mode: dense embedding + Milvus native BM25 on raw text."""
        embed_result = await self._embedding.encode([query], return_sparse=False)

        if not embed_result.dense:
            logger.warning("Empty embedding result for query: %s", query[:100])
            return []

        dense = embed_result.dense[0]

        try:
            return await self._vector_store.hybrid_search(
                dense=dense,
                top_k=top_k,
                filters=filters,
                collection=collection,
                sparse_text=query,
                sparse_method="bm25",
            )
        except Exception:
            logger.warning("BM25 hybrid search failed, falling back to dense-only", exc_info=True)
            return await self._vector_store.query(
                vector=dense, top_k=top_k, filters=filters, collection=collection,
            )

    async def _search_bgem3(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
        collection: str,
    ) -> list[RetrievalResult]:
        """BGE-M3 mode: dense + sparse embedding vectors (original path)."""
        embed_result = await self._embedding.encode([query], return_sparse=True)

        if not embed_result.dense:
            logger.warning("Empty embedding result for query: %s", query[:100])
            return []

        dense = embed_result.dense[0]
        sparse = embed_result.sparse[0] if embed_result.sparse else {}

        if sparse:
            try:
                return await self._vector_store.hybrid_search(
                    dense=dense,
                    sparse=sparse,
                    top_k=top_k,
                    filters=filters,
                    collection=collection,
                )
            except Exception:
                logger.warning("Hybrid search failed, falling back to dense-only", exc_info=True)

        # Dense-only fallback
        return await self._vector_store.query(
            vector=dense,
            top_k=top_k,
            filters=filters,
            collection=collection,
        )
