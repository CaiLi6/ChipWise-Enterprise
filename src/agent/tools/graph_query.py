"""Graph Query Agent Tool — 4 query patterns + custom Cypher (§2C5)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.retrieval.graph_search import GraphSearch

logger = logging.getLogger(__name__)


class GraphQueryTool(BaseTool):
    """Query the Kùzu knowledge graph for chip relationships and properties."""

    def __init__(self, graph_search: GraphSearch) -> None:
        self._graph = graph_search

    @property
    def name(self) -> str:
        return "graph_query"

    @property
    def description(self) -> str:
        return (
            "Query the chip knowledge graph for alternative chips, errata, "
            "parameters, design rules, and sub-graphs."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "find_alternatives",
                        "find_errata_by_peripheral",
                        "chip_subgraph",
                        "param_range_search",
                        "custom_cypher",
                    ],
                },
                "part_number": {"type": "string"},
                "peripheral": {"type": "string"},
                "param_name": {"type": "string"},
                "min_val": {"type": "number"},
                "max_val": {"type": "number"},
                "cypher": {"type": "string"},
                "include_domestic": {"type": "boolean", "default": False},
            },
            "required": ["query_type"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query_type = kwargs.get("query_type", "")

        try:
            if query_type == "find_alternatives":
                results = await self._graph.find_alternatives(
                    kwargs.get("part_number", ""),
                    include_domestic=kwargs.get("include_domestic", False),
                )
            elif query_type == "find_errata_by_peripheral":
                results = await self._graph.find_errata_by_peripheral(
                    kwargs.get("part_number", ""),
                    kwargs.get("peripheral", ""),
                )
            elif query_type == "chip_subgraph":
                results = await self._graph.get_chip_subgraph(
                    kwargs.get("part_number", ""),
                    max_depth=kwargs.get("max_depth", 2),
                )
            elif query_type == "param_range_search":
                results = await self._graph.param_range_search(
                    kwargs.get("param_name", ""),
                    kwargs.get("min_val", 0),
                    kwargs.get("max_val", 999999),
                )
            elif query_type == "custom_cypher":
                results = await self._graph.execute_custom_cypher(
                    kwargs.get("cypher", "RETURN 0"),
                    kwargs.get("params"),
                )
            else:
                return {"error": f"Unknown query_type: {query_type}", "results": []}

            return {"results": results, "total": len(results)}
        except ValueError as e:
            return {"error": str(e), "results": []}
        except Exception:
            logger.exception("Graph query failed")
            return {"error": "Graph database unavailable", "results": []}
