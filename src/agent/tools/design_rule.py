"""DesignRuleCheckTool — Design rules + errata + app notes (§5B1)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)


class DesignRuleCheckTool(BaseTool):
    """Check design rules, errata, and app note recommendations for a chip."""

    def __init__(
        self,
        db_pool: Any = None,
        llm: BaseLLM | None = None,
        graph_search: Any = None,
        hybrid_search: Any = None,
    ) -> None:
        self._pool = db_pool
        self._llm = llm
        self._graph = graph_search
        self._search = hybrid_search

    @property
    def name(self) -> str:
        return "design_rule_check"

    @property
    def description(self) -> str:
        return "Check design rules, errata, and application note recommendations for a chip."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"chip_name": {"type": "string"}},
            "required": ["chip_name"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        chip_name = kwargs.get("chip_name", "")

        # Step 1: Design rules from PG
        rules = await self._get_design_rules(chip_name)

        # Step 2: Unfixed errata from PG
        errata = await self._get_errata(chip_name)

        # Step 3: Graph query for errata→peripheral
        _errata_peripherals: list[dict[str, Any]] = []
        if self._graph and errata:
            try:
                result = await self._graph.find_errata_by_peripheral(chip_name, "")
                _errata_peripherals = result
            except Exception:
                pass

        # Step 4: App note search
        app_notes: list[dict[str, Any]] = []
        if self._search:
            try:
                results = await self._search.search(
                    f"{chip_name} design notes layout decoupling", top_k=10
                )
                app_notes = [
                    {"content": r.content, "doc_id": r.doc_id, "score": r.score}
                    for r in results
                ]
            except Exception:
                pass

        # Step 5: LLM analysis
        analysis = ""
        if self._llm:
            try:
                prompt = (
                    f"Chip: {chip_name}\n"
                    f"Design rules ({len(rules)}): {rules[:5]}\n"
                    f"Active errata ({len(errata)}): {errata[:5]}\n"
                    f"App notes ({len(app_notes)}): {[n['content'][:100] for n in app_notes[:3]]}\n\n"
                    "Summarize the key design considerations, sorted by severity."
                )
                analysis = str(await self._llm.generate(prompt, temperature=0.3, max_tokens=500))
            except Exception:
                logger.warning("LLM analysis failed", exc_info=True)

        return {
            "design_rules": rules,
            "errata": errata,
            "app_note_citations": app_notes,
            "analysis": analysis,
            "chip_name": chip_name,
        }

    async def _get_design_rules(self, chip_name: str) -> list[dict[str, Any]]:
        if not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT dr.* FROM design_rules dr "
                    "JOIN chips c ON dr.chip_id = c.chip_id "
                    "WHERE c.part_number = $1", chip_name
                )
                return [dict(r) for r in rows]
        except Exception:
            return []

    async def _get_errata(self, chip_name: str) -> list[dict[str, Any]]:
        if not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT e.* FROM errata e "
                    "JOIN chips c ON e.chip_id = c.chip_id "
                    "WHERE c.part_number = $1 AND e.status != 'fixed'", chip_name
                )
                return [dict(r) for r in rows]
        except Exception:
            return []
