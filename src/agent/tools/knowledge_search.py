"""KnowledgeSearchTool — Search team knowledge notes (§5C2)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class KnowledgeSearchTool(BaseTool):
    """Search team knowledge notes for chip-related insights."""

    def __init__(self, hybrid_search: Any = None) -> None:
        self._search = hybrid_search

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search team knowledge notes and insights about chips."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "chip_id": {"type": "integer"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        chip_id = kwargs.get("chip_id")
        top_k = kwargs.get("top_k", 5)

        if not self._search:
            return {"results": [], "total": 0}

        try:
            filters = {}
            if chip_id:
                filters["chip_id"] = chip_id

            results = await self._search.search(
                query, top_k=top_k, collection="knowledge_notes",
                filters=filters or None,
            )
            return {
                "results": [
                    {
                        "content": r.content,
                        "doc_id": r.doc_id,
                        "score": r.score,
                        "source": "team_knowledge",
                        "metadata": r.metadata,
                    }
                    for r in results
                ],
                "total": len(results),
            }
        except Exception:
            logger.warning("Knowledge search failed", exc_info=True)
            return {"results": [], "total": 0}
