"""BaseTool — abstract interface for all Agent tools (§4.8.2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Every agent tool inherits from this base class.

    Subclasses must define *name*, *description*, *parameters_schema*
    and implement :meth:`execute`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (snake_case, e.g. ``rag_search``)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line human-readable description for the LLM system prompt."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema dict describing the tool's input parameters."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Run the tool with the given keyword arguments.

        Returns a dict with at least a ``"result"`` key.
        """

    def to_openai_tool(self) -> dict[str, Any]:
        """Serialise this tool to the OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
