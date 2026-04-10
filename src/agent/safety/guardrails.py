"""Safety guardrails placeholder (§4.8.1).

Full implementation in Phase 2 (task 2C3).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SafetyGuardrails:
    """Validates LLM inputs/outputs for safety constraints.

    Skeleton: always passes. Phase 2 adds content filtering,
    PII detection, and injection detection.
    """

    def check_input(self, user_input: str) -> bool:
        """Return True if user input is safe."""
        return True

    def check_output(self, llm_output: str) -> bool:
        """Return True if LLM output is safe to return."""
        return True

    def check_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Return True if a tool call is permitted."""
        return True
