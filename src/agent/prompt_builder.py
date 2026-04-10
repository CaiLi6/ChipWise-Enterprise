"""Agent system prompt builder placeholder (§4.8.1).

Full implementation in Phase 2 (task 2C2).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Constructs the system prompt for the Agent ReAct loop.

    Skeleton: returns a minimal system prompt. Phase 2 adds
    tool descriptions, conversation context, and persona templates.
    """

    def build_system_prompt(
        self,
        tools_schema: list[dict[str, Any]] | None = None,
        context: str | None = None,
    ) -> str:
        parts = [
            "You are ChipWise, a chip data intelligence assistant.",
            "Use the provided tools to answer user queries about semiconductor chips.",
        ]
        if context:
            parts.append(f"Context: {context}")
        return "\n".join(parts)
