"""TestCaseGenTool — Auto-generate test cases from chip params (§5A1)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path("config/prompts/test_case_gen.txt")


class TestCaseGenTool(BaseTool):
    """Generate structured test cases from chip parameters and datasheets."""

    def __init__(self, db_pool: Any = None, llm: BaseLLM | None = None, hybrid_search: Any = None) -> None:
        self._pool = db_pool
        self._llm = llm
        self._search = hybrid_search
        self._prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Generate test cases for chip {chip_name} based on these parameters:\n"
            "{parameters}\n\nContext from datasheets:\n{context}\n\n"
            "Return a JSON array of test cases with fields: "
            "test_item, parameter, condition, expected_value, test_method, priority"
        )

    @property
    def name(self) -> str:
        return "test_case_gen"

    @property
    def description(self) -> str:
        return "Generate structured test cases for a chip based on its parameters."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chip_name": {"type": "string"},
            },
            "required": ["chip_name"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        chip_name = kwargs.get("chip_name", "")

        # Step 1: Get parameters
        params = await self._get_params(chip_name)
        if not params:
            return {"error": f"No parameters found for {chip_name}", "test_cases": ""}

        # Step 2: Get context from search
        context = ""
        if self._search:
            try:
                results = await self._search.search(f"{chip_name} test method verification", top_k=5)
                context = "\n".join(r.content for r in results[:5])
            except Exception:
                pass

        # Step 3: LLM generation
        if not self._llm:
            return {"error": "LLM not available", "test_cases": ""}

        param_text = "\n".join(f"- {p['name']}: {p.get('typ_value', 'N/A')} {p.get('unit', '')}" for p in params)
        prompt = self._prompt.format(chip_name=chip_name, parameters=param_text, context=context)

        try:
            raw = await self._llm.generate(prompt, temperature=0.3, max_tokens=4096)
            cases = self._parse_test_cases(str(raw))
            return {
                "test_cases": raw,
                "structured_cases": cases,
                "test_case_count": len(cases),
                "chip_name": chip_name,
            }
        except Exception:
            logger.exception("Test case generation failed")
            return {"error": "LLM generation failed", "test_cases": ""}

    async def _get_params(self, chip_name: str) -> list[dict[str, Any]]:
        if not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT p.name, p.typ_value, p.min_value, p.max_value, p.unit, p.category "
                    "FROM chip_parameters p JOIN chips c ON p.chip_id = c.chip_id "
                    "WHERE c.part_number = $1", chip_name
                )
                return [dict(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _parse_test_cases(raw: str) -> list[dict[str, str]]:
        """Parse LLM output into structured test cases."""
        # Try JSON parse
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        text = code_block.group(1) if code_block else raw
        try:
            data = json.loads(text.strip())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return []
