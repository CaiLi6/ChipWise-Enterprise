"""LLM-based structured parameter extraction from tables (§3A2)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from src.libs.llm.base import BaseLLM
from src.agent.safety.output_validator import StructuredOutputValidator

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path("config/prompts/param_extraction.txt")


class ParamExtractor:
    """Extract structured chip parameters from table data using LLM."""

    def __init__(
        self,
        llm: BaseLLM,
        db_pool: Any = None,
        validator: StructuredOutputValidator | None = None,
    ) -> None:
        self._llm = llm
        self._pool = db_pool
        self._validator = validator
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Extract chip parameters from the following table.\n"
            "Return a JSON array where each element has:\n"
            '  {{"name": str, "category": str, "min_value": str|null, '
            '"typ_value": str|null, "max_value": str|null, '
            '"unit": str, "condition": str|null}}\n\n'
            "Chip: {chip_part_number}\n"
            "Table (page {page}):\n{table_text}\n\n"
            "JSON output:"
        )

    async def extract_from_table(
        self,
        table_rows: list[list[str]],
        chip_part_number: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """Extract parameters from a table using LLM."""
        table_text = "\n".join(
            " | ".join(row) for row in table_rows
        )
        prompt = self._prompt_template.format(
            chip_part_number=chip_part_number,
            page=page,
            table_text=table_text,
        )

        try:
            response = await self._llm.generate(
                prompt, temperature=0.0, max_tokens=2000
            )
            raw_output = response.text if hasattr(response, "text") else str(response)
            params = self._parse_llm_output(raw_output)

            # Validate with StructuredOutputValidator if available
            if self._validator and params:
                validated = []
                for p in params:
                    result = self._validator.validate_chip_param(p)
                    if result.get("valid"):
                        p["needs_review"] = bool(result.get("warnings"))
                    else:
                        logger.warning(
                            "Param validation failed: %s — %s",
                            p.get("name"), result.get("errors"),
                        )
                        p["needs_review"] = True
                    validated.append(p)
                return validated
            return params
        except Exception:
            logger.exception("LLM parameter extraction failed")
            # Retry once
            try:
                response = await self._llm.generate(
                    prompt, temperature=0.0, max_tokens=2000
                )
                raw_output = response.text if hasattr(response, "text") else str(response)
                return self._parse_llm_output(raw_output)
            except Exception:
                logger.exception("LLM param extraction retry also failed")
                return []

    @staticmethod
    def _parse_llm_output(output: str) -> list[dict[str, Any]]:
        """Robust JSON parsing: handles markdown code blocks, partial JSON."""
        # Strip markdown code block
        output = output.strip()
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", output, re.DOTALL)
        if code_block:
            output = code_block.group(1).strip()

        # Try direct parse
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "parameters" in data:
                return data["parameters"]
            return [data]
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in the output
        arr_match = re.search(r"\[.*\]", output, re.DOTALL)
        if arr_match:
            try:
                return json.loads(arr_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM output as JSON")
        return []

    async def store_params(
        self, params: list[dict[str, Any]], chip_id: int
    ) -> int:
        """Store parameters in PostgreSQL (ON CONFLICT UPDATE)."""
        if not self._pool or not params:
            return 0

        count = 0
        async with self._pool.acquire() as conn:
            for p in params:
                await conn.execute(
                    """
                    INSERT INTO chip_parameters
                        (chip_id, name, category, min_value, typ_value, max_value,
                         unit, condition, needs_review)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (chip_id, name) DO UPDATE SET
                        min_value = EXCLUDED.min_value,
                        typ_value = EXCLUDED.typ_value,
                        max_value = EXCLUDED.max_value,
                        unit = EXCLUDED.unit,
                        condition = EXCLUDED.condition,
                        needs_review = EXCLUDED.needs_review
                    """,
                    chip_id,
                    p.get("name", ""),
                    p.get("category", ""),
                    p.get("min_value"),
                    p.get("typ_value"),
                    p.get("max_value"),
                    p.get("unit", ""),
                    p.get("condition"),
                    p.get("needs_review", False),
                )
                count += 1
        return count
