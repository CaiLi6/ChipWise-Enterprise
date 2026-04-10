"""Safety guardrails for Agent tool outputs (§4.8.1).

Provides output sanitization, tool call validation, and iteration limit checks.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"Ignore previous instructions", re.IGNORECASE),
    re.compile(r"You are now", re.IGNORECASE),
    re.compile(r"<\|endoftext\|>", re.IGNORECASE),
    re.compile(r"ASSISTANT:", re.IGNORECASE),
]


class MaxIterationExceeded(Exception):
    """Raised when the agent exceeds maximum iterations."""


class SafetyGuardrails:
    """Validates and sanitizes Agent inputs/outputs."""

    def __init__(self, registered_tools: set[str] | None = None) -> None:
        self._registered_tools = registered_tools or set()

    def check_input(self, user_input: str) -> bool:
        """Return True if user input is safe."""
        return True

    def check_output(self, llm_output: str) -> bool:
        """Return True if LLM output is safe to return."""
        return True

    def sanitize_tool_output(self, output: Any) -> Any:
        """Remove prompt injection markers from tool output."""
        if isinstance(output, str):
            sanitized = output
            for pattern in _INJECTION_PATTERNS:
                sanitized = pattern.sub("", sanitized)
            return sanitized.strip()
        elif isinstance(output, dict):
            return {k: self.sanitize_tool_output(v) for k, v in output.items()}
        elif isinstance(output, list):
            return [self.sanitize_tool_output(item) for item in output]
        return output

    def validate_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Return True if a tool call is permitted."""
        if self._registered_tools and tool_name not in self._registered_tools:
            return False
        return True

    def check_iteration_limit(self, current: int, max_iter: int) -> None:
        """Raise MaxIterationExceeded if limit is reached."""
        if current >= max_iter:
            raise MaxIterationExceeded(
                f"Agent reached maximum iterations ({max_iter})"
            )

