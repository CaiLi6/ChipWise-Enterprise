"""ChipSelectTool — Chip selection with filtering + domestic alternatives (§4B1, §4B2)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)


class ChipSelectTool(BaseTool):
    """Filter and recommend chips based on structured criteria."""

    def __init__(
        self,
        db_pool: Any = None,
        llm: BaseLLM | None = None,
        graph_search: Any = None,
    ) -> None:
        self._pool = db_pool
        self._llm = llm
        self._graph = graph_search

    @property
    def name(self) -> str:
        return "chip_select"

    @property
    def description(self) -> str:
        return (
            "Find and recommend chips based on structured criteria "
            "(voltage, frequency, package, category). Includes domestic alternatives."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "criteria": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "vcc_min": {"type": "number"},
                        "vcc_max": {"type": "number"},
                        "freq_min": {"type": "number"},
                        "package": {"type": "string"},
                        "manufacturer": {"type": "string"},
                    },
                },
                "include_domestic": {"type": "boolean", "default": False},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["criteria"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        criteria: dict[str, Any] = kwargs.get("criteria", {})
        include_domestic: bool = kwargs.get("include_domestic", False)
        top_k: int = kwargs.get("top_k", 10)

        # Step 1: SQL filter
        candidates = await self._filter_chips(criteria, top_k)

        if not candidates:
            return {
                "candidates": [],
                "total": 0,
                "message": "No chips match the given criteria.",
            }

        # Step 2: Find domestic alternatives if requested
        if include_domestic:
            for c in candidates:
                alts = await self._find_domestic_alternatives(c.get("chip_id", 0))
                c["domestic_alternatives"] = alts

        # Step 3: LLM ranking summary
        summary = ""
        if self._llm and candidates:
            try:
                chip_list = "\n".join(
                    f"- {c['part_number']} ({c.get('manufacturer', '')})"
                    for c in candidates[:5]
                )
                prompt = (
                    f"Given these chip candidates matching the criteria:\n{chip_list}\n\n"
                    f"Criteria: {criteria}\n\n"
                    "Provide a brief recommendation summary."
                )
                summary = await self._llm.generate(
                    prompt, temperature=0.3, max_tokens=300
                )
            except Exception:
                logger.warning("LLM recommendation failed", exc_info=True)

        return {
            "candidates": candidates,
            "total": len(candidates),
            "ranked_summary": summary,
        }

    async def _filter_chips(
        self, criteria: dict[str, Any], top_k: int
    ) -> list[dict[str, Any]]:
        """Build parameterized SQL and query PG."""
        if not self._pool:
            return []

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if "category" in criteria:
            conditions.append(f"c.category = ${idx}")
            params.append(criteria["category"])
            idx += 1

        if "manufacturer" in criteria:
            conditions.append(f"c.manufacturer = ${idx}")
            params.append(criteria["manufacturer"])
            idx += 1

        if "package" in criteria:
            conditions.append(f"c.package ILIKE ${idx}")
            params.append(f"%{criteria['package']}%")
            idx += 1

        where = " AND ".join(conditions) if conditions else "TRUE"
        query = f"""
            SELECT c.chip_id, c.part_number, c.manufacturer, c.category, c.package, c.status
            FROM chips c
            WHERE {where}
            LIMIT ${idx}
        """
        params.append(top_k)

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [dict(r) for r in rows]
        except Exception:
            logger.exception("Chip filter query failed")
            return []

    async def _find_domestic_alternatives(
        self, chip_id: int
    ) -> list[dict[str, Any]]:
        """Query PG + Kùzu for domestic alternatives (§4B2)."""
        results: list[dict[str, Any]] = []

        # PG query
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT alt.part_number, alt.manufacturer, ca.compat_score, ca.key_differences "
                        "FROM chip_alternatives ca "
                        "JOIN chips alt ON ca.target_chip_id = alt.chip_id "
                        "WHERE ca.source_chip_id = $1 AND ca.is_domestic = true "
                        "ORDER BY ca.compat_score DESC LIMIT 3",
                        chip_id,
                    )
                    results.extend(dict(r) for r in rows)
            except Exception:
                logger.debug("PG domestic alt query failed", exc_info=True)

        # Graph query (deduplicated)
        if self._graph:
            try:
                graph_alts = await self._graph.find_alternatives(
                    str(chip_id), include_domestic=True
                )
                existing = {r["part_number"] for r in results}
                for ga in graph_alts:
                    if ga.get("part_number") not in existing:
                        results.append(ga)
            except Exception:
                logger.debug("Graph domestic alt query failed", exc_info=True)

        return results
