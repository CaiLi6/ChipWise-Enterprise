"""Errata document parser (§5B3)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)


async def parse_errata_document(
    text: str, chip_id: int, llm: BaseLLM
) -> list[dict[str, Any]]:
    """Parse errata text into structured entries using LLM."""
    if not text.strip():
        return []

    prompt = (
        "Parse this errata document and extract all errata entries as JSON array.\n"
        "Each entry: {\"errata_code\": str, \"title\": str, \"severity\": "
        "\"critical|major|minor\", \"status\": \"open|workaround|fixed\", "
        "\"affected_peripherals\": [str], \"workaround\": str}\n\n"
        f"Errata text:\n{text[:4000]}"
    )

    try:
        raw = await llm.generate(prompt, temperature=0, max_tokens=2000)
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", str(raw), re.DOTALL)
        output = code_block.group(1) if code_block else str(raw)

        try:
            entries = json.loads(output.strip())
            if isinstance(entries, list):
                for e in entries:
                    e["chip_id"] = chip_id
                return entries
        except json.JSONDecodeError:
            pass
    except Exception:
        logger.exception("Errata parsing failed")

    return []
