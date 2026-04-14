"""RAG Search Agent Tool — hybrid + rerank + optional graph boost (§2C4)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.retrieval.graph_search import GraphSearch
from src.retrieval.hybrid_search import HybridSearch
from src.retrieval.reranker import CoreReranker

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """Retrieval-augmented search combining vector, reranker, and graph boost."""

    def __init__(
        self,
        hybrid_search: HybridSearch,
        reranker: CoreReranker,
        graph_search: GraphSearch | None = None,
    ) -> None:
        self._hybrid = hybrid_search
        self._reranker = reranker
        self._graph = graph_search

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return (
            "Search chip datasheets and documentation using hybrid vector search "
            "with optional graph-based relevance boosting."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "part_number": {"type": "string", "description": "Filter by chip part number"},
                "doc_type": {
                    "type": "string",
                    "enum": ["datasheet", "app_note", "errata"],
                    "description": "Filter by document type",
                },
                "top_k": {"type": "integer", "default": 10, "description": "Number of results"},
                "use_graph_boost": {"type": "boolean", "default": True},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        part_number = kwargs.get("part_number")
        doc_type = kwargs.get("doc_type")
        top_k = kwargs.get("top_k", 10)
        use_graph_boost = kwargs.get("use_graph_boost", True)

        # Build filters
        filters: dict[str, Any] = {}
        if part_number:
            filters["part_number"] = part_number
        if doc_type:
            filters["doc_type"] = doc_type

        # Step 1: Hybrid search (fetch more candidates for reranking)
        candidates = await self._hybrid.search(
            query, top_k=top_k * 3, filters=filters or None
        )

        if not candidates:
            return {"results": [], "total": 0}

        # Step 2: Rerank
        reranked = await self._reranker.rerank(query, candidates, top_k=top_k)

        # Step 3: Optional graph boost
        if use_graph_boost and part_number and self._graph:
            try:
                subgraph = await self._graph.get_chip_subgraph(part_number, max_depth=1)
                if subgraph:
                    for r in reranked:
                        r.score *= 1.15
            except Exception:
                logger.warning("Graph boost failed", exc_info=True)

        results = [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "content": r.content,
                "score": r.score,
                "page_number": r.page_number,
                "metadata": r.metadata,
            }
            for r in reranked
        ]
        return {"results": results, "total": len(results)}
