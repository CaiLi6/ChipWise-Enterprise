"""ChipCompareTool — Chip parameter comparison (§4A1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.libs.embedding.base import BaseEmbedding
from src.libs.llm.base import BaseLLM
from src.libs.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path("config/prompts/chip_comparison.txt")


class ChipCompareTool(BaseTool):
    """Compare parameters of 2-5 chips side by side."""

    def __init__(
        self,
        db_pool: Any = None,
        llm: BaseLLM | None = None,
        vector_store: BaseVectorStore | None = None,
        embedding: BaseEmbedding | None = None,
    ) -> None:
        self._pool = db_pool
        self._llm = llm
        self._vector_store = vector_store
        self._embedding = embedding
        self._prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Compare the following chips based on their parameters.\n"
            "Comparison table:\n{table}\n\n"
            "Provide a concise analysis of key differences and recommendations."
        )

    @property
    def name(self) -> str:
        return "chip_compare"

    @property
    def description(self) -> str:
        return "Compare parameters of 2-5 chips side by side with difference analysis."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chip_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 5,
                    "description": "Chip part numbers to compare",
                },
                "dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by parameter categories (electrical, timing, thermal)",
                },
            },
            "required": ["chip_names"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        chip_names: list[str] = kwargs.get("chip_names", [])
        dimensions: list[str] | None = kwargs.get("dimensions")

        if len(chip_names) < 2:
            return {"error": "At least 2 chips required for comparison"}

        # Fetch parameters for each chip
        chip_params: dict[str, dict[str, Any]] = {}
        for name in chip_names:
            params = await self._fetch_chip_params(name, dimensions)
            if params is None:
                return {"error": f"Chip not found: {name}"}
            chip_params[name] = params

        # Build comparison table
        comparison_table = self._build_comparison_table(chip_params)

        # LLM analysis (graceful degradation)
        analysis_text = ""
        if self._llm:
            try:
                table_str = self._format_table(comparison_table, chip_names)
                prompt = self._prompt.format(table=table_str)
                analysis_text = str(await self._llm.generate(
                    prompt, temperature=0.3, max_tokens=500
                ))
            except Exception:
                logger.warning("LLM comparison analysis failed", exc_info=True)

        # Milvus retrieval for per-chip design notes (graceful degradation)
        citations = await self._fetch_citations(chip_names)

        return {
            "comparison_table": comparison_table,
            "analysis": analysis_text,
            "chips": chip_names,
            "citations": citations,
        }

    async def _fetch_citations(
        self, chip_names: list[str], top_k: int = 3
    ) -> list[dict[str, Any]]:
        """Retrieve top-k design notes per chip from Milvus (optional)."""
        if not self._vector_store or not self._embedding:
            return []

        citations: list[dict[str, Any]] = []
        for name in chip_names:
            try:
                query_text = f"{name} design considerations errata"
                emb = await self._embedding.encode([query_text], return_sparse=False)
                if not emb.dense:
                    continue
                results = await self._vector_store.query(
                    vector=emb.dense[0],
                    top_k=top_k,
                    filters={"part_number": name},
                )
                for r in results:
                    citations.append(
                        {
                            "chip": name,
                            "chunk_id": getattr(r, "chunk_id", None),
                            "text": getattr(r, "text", ""),
                            "score": getattr(r, "score", 0.0),
                            "source": getattr(r, "source", ""),
                        }
                    )
            except Exception:
                logger.warning("Citation fetch failed for %s", name, exc_info=True)
        return citations

    async def _fetch_chip_params(
        self, part_number: str, dimensions: list[str] | None = None
    ) -> dict[str, Any] | None:
        """Fetch chip parameters from PG."""
        if not self._pool:
            # Return mock data for testing without DB
            return {}

        try:
            async with self._pool.acquire() as conn:
                chip = await conn.fetchrow(
                    "SELECT chip_id FROM chips WHERE part_number = $1",
                    part_number,
                )
                if not chip:
                    return None

                query = (
                    "SELECT name, category, typ_value, min_value, max_value, unit"
                    " FROM chip_parameters WHERE chip_id = $1"
                )
                args: list[Any] = [chip["chip_id"]]

                if dimensions:
                    placeholders = ", ".join(f"${i+2}" for i in range(len(dimensions)))
                    query += f" AND category IN ({placeholders})"
                    args.extend(dimensions)

                rows = await conn.fetch(query, *args)
                return {
                    row["name"]: {
                        "typ": row["typ_value"],
                        "min": row["min_value"],
                        "max": row["max_value"],
                        "unit": row["unit"],
                        "category": row["category"],
                    }
                    for row in rows
                }
        except Exception:
            logger.exception("Failed to fetch params for %s", part_number)
            return {}

    @staticmethod
    def _build_comparison_table(
        chip_params: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Align parameters across all chips."""
        all_params: set[str] = set()
        for params in chip_params.values():
            all_params.update(params.keys())

        table: dict[str, dict[str, Any]] = {}
        for param in sorted(all_params):
            table[param] = {}
            for chip, params in chip_params.items():
                table[param][chip] = params.get(param)

        return table

    @staticmethod
    def _format_table(
        table: dict[str, dict[str, Any]], chips: list[str]
    ) -> str:
        """Format comparison table as text for LLM."""
        lines = [f"| Parameter | {' | '.join(chips)} |"]
        lines.append("| --- " * (len(chips) + 1) + "|")
        for param, values in table.items():
            row = [param]
            for chip in chips:
                v = values.get(chip)
                if v:
                    row.append(f"{v.get('typ', '-')} {v.get('unit', '')}")
                else:
                    row.append("N/A")
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)
