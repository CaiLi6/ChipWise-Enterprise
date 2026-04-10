"""Structured output validator placeholder (§2.9).

Full implementation in Phase 2 (task 2C3).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StructuredOutputValidator:
    """Validates LLM-generated structured output against Pydantic schemas.

    Skeleton: always passes. Phase 2 adds Pydantic validation,
    domain-rule constraints, and ``needs_review`` flagging.
    """

    def validate(self, data: dict[str, Any], schema_name: str | None = None) -> bool:
        """Return True if *data* conforms to the named schema."""
        return True

    def get_errors(self) -> list[str]:
        """Return validation error messages from the last :meth:`validate` call."""
        return []
