"""Design rule extraction from datasheet chunks (§5B2)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.core.types import Chunk
from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)

_RULE_KEYWORDS = re.compile(
    r"decoupl|layout|退耦|布局|thermal|散热|power.?seq|电源时序|"
    r"注意|建议|recommend|caution|warning|ESD|clock|bypass",
    re.IGNORECASE,
)


async def extract_design_rules(
    chunks: list[Chunk], chip_id: int, llm: BaseLLM
) -> list[dict[str, Any]]:
    """Extract design rules from relevant chunks using LLM, batched.

    Sends up to MAX_CHUNKS chunks to the LLM in batches of BATCH_SIZE so a
    single PDF needs only ceil(MAX_CHUNKS / BATCH_SIZE) LLM round-trips
    instead of one per chunk.
    """
    relevant = [c for c in chunks if _RULE_KEYWORDS.search(c.content)]
    if not relevant:
        return []

    MAX_CHUNKS = 10
    BATCH_SIZE = 5
    relevant = relevant[:MAX_CHUNKS]

    rules: list[dict[str, Any]] = []
    for batch_start in range(0, len(relevant), BATCH_SIZE):
        batch = relevant[batch_start : batch_start + BATCH_SIZE]
        prompt_body = "\n\n".join(
            f"[#{idx} page={c.page_number}]\n{c.content[:1800]}"
            for idx, c in enumerate(batch)
        )
        prompt = (
            "Extract design rules from the labeled chunks below. Each rule "
            "MUST include `chunk_index` referring to the chunk it came from. "
            "Return ONLY a JSON array (no prose):\n"
            '[{"chunk_index": int, '
            '"rule_type": "decoupling_cap|layout|thermal|power_seq|clock|esd|io_config", '
            '"rule_text": "...", '
            '"severity": "mandatory|recommendation|note"}]\n\n'
            f"Chunks:\n{prompt_body}"
        )
        try:
            response = await llm.generate(prompt, temperature=0, max_tokens=1500)
            raw = response.text if hasattr(response, "text") else str(response)
        except Exception:
            logger.debug("Rule extraction LLM call failed", exc_info=True)
            continue

        code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        text = code_block.group(1) if code_block else raw
        arr = re.search(r"\[.*\]", text, re.DOTALL)
        if not arr:
            continue
        try:
            parsed = json.loads(arr.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, list):
            continue
        for r in parsed:
            if not isinstance(r, dict):
                continue
            idx = r.get("chunk_index")
            src = batch[idx] if isinstance(idx, int) and 0 <= idx < len(batch) else batch[0]
            r["chip_id"] = chip_id
            r["source_page"] = src.page_number
            r["source_section"] = src.metadata.get("section_title", "")
            rules.append(r)

    return rules
