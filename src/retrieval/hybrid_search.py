"""Hybrid search: dense + sparse vector fusion via Milvus RRF (§2B1)."""

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
    ) -> None:
        self._embedding = embedding_client
        self._vector_store = vector_store

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        """Encode query and perform hybrid search."""
        embed_result = await self._embedding.encode([query], return_sparse=True)

        if not embed_result.dense:
            logger.warning("Empty embedding result for query: %s", query[:100])
            return []

        dense = embed_result.dense[0]
        sparse = embed_result.sparse[0] if embed_result.sparse else {}

        if sparse:
            try:
                results = await self._vector_store.hybrid_search(
                    dense=dense,
                    sparse=sparse,
                    top_k=top_k,
                    filters=filters,
                    collection=collection,
                )
                return results
            except Exception:
                logger.warning("Hybrid search failed, falling back to dense-only", exc_info=True)

        # Dense-only fallback
        return await self._vector_store.query(
            vector=dense,
            top_k=top_k,
            filters=filters,
            collection=collection,
        )
