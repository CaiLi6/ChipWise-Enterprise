"""QueryRewriter — LLM-based coreference resolution for multi-turn queries (§2D2)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)

# Pronoun patterns that trigger rewriting (Chinese + English)
_PRONOUN_PATTERN = re.compile(
    r"\b(it|its|this|that|these|those|they|them|their)\b"
    r"|[它它们这个那个其该这些那些]",
    re.IGNORECASE,
)

_PROMPT_PATH = Path("config/prompts/query_rewriter.txt")


class QueryRewriter:
    """Rewrites queries to resolve pronouns/ellipsis using conversation context."""

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Given the conversation history and the current query, "
            "rewrite the query to replace pronouns with the actual entities. "
            "Return ONLY the rewritten query, nothing else.\n\n"
            "History:\n{history}\n\n"
            "Current query: {query}\n\n"
            "Rewritten query:"
        )

    @staticmethod
    def _needs_rewrite(query: str) -> bool:
        """Quick check whether the query contains pronouns."""
        return bool(_PRONOUN_PATTERN.search(query))

    async def rewrite(
        self, current_query: str, history: list[dict[str, str]]
    ) -> str:
        """Rewrite *current_query* using conversation *history*.

        Fast paths (0 LLM calls):
        - No history → return as-is.
        - No pronouns → return as-is.

        On LLM failure → return original query (graceful degradation).
        """
        if not history:
            return current_query

        if not self._needs_rewrite(current_query):
            return current_query

        # Format history for prompt
        hist_text = "\n".join(
            f"{turn['role']}: {turn['content']}" for turn in history[-5:]
        )
        prompt = self._prompt_template.format(history=hist_text, query=current_query)

        try:
            response = await self._llm.generate(
                prompt, temperature=0.0, max_tokens=100
            )
            rewritten = response.text.strip() if hasattr(response, "text") else str(response).strip()
            if rewritten:
                return rewritten
        except Exception:
            logger.warning("Query rewrite failed, using original", exc_info=True)

        return current_query
