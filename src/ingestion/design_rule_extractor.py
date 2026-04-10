"""Design rule extraction from datasheet chunks (§5B2)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.libs.llm.base import BaseLLM
from src.core.types import Chunk

logger = logging.getLogger(__name__)

_RULE_KEYWORDS = re.compile(
    r"decoupl|layout|退耦|布局|thermal|散热|power.?seq|电源时序|"
    r"注意|建议|recommend|caution|warning|ESD|clock|bypass",
    re.IGNORECASE,
)


async def extract_design_rules(
    chunks: list[Chunk], chip_id: int, llm: BaseLLM
) -> list[dict[str, Any]]:
    """Extract design rules from relevant chunks using LLM."""
    # Filter chunks that contain rule-related keywords
    relevant = [c for c in chunks if _RULE_KEYWORDS.search(c.content)]
    if not relevant:
        return []

    rules: list[dict[str, Any]] = []
    for chunk in relevant[:10]:  # Limit to 10 chunks
        try:
            prompt = (
                "Extract design rules from this text. Return a JSON array:\n"
                '[{"rule_type": "decoupling_cap|layout|thermal|power_seq|clock|esd|io_config", '
                '"rule_text": "...", "severity": "mandatory|recommendation|note"}]\n\n'
                f"Text:\n{chunk.content[:2000]}"
            )
            raw = await llm.generate(prompt, temperature=0, max_tokens=500)

            # Parse JSON
            code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
            text = code_block.group(1) if code_block else raw
            try:
                parsed = json.loads(text.strip())
                if isinstance(parsed, list):
                    for r in parsed:
                        r["chip_id"] = chip_id
                        r["source_page"] = chunk.page_number
                        r["source_section"] = chunk.metadata.get("section_title", "")
                    rules.extend(parsed)
            except json.JSONDecodeError:
                pass
        except Exception:
            logger.debug("Rule extraction failed for chunk %s", chunk.chunk_id)

    return rules
