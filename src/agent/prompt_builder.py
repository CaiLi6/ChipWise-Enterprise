"""Agent system prompt builder (§4.8.1, task 2C2).

Constructs the system prompt for the ReAct loop by loading a template
from ``config/prompts/agent_system.txt`` and injecting tool descriptions.
Also builds the full message list with conversation history.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path("config/prompts")
_DEFAULT_TEMPLATE = "agent_system.txt"


class PromptBuilder:
    """Constructs system prompt and message lists for the Agent."""

    def __init__(self, prompts_dir: Path | str = _PROMPTS_DIR) -> None:
        self._prompts_dir = Path(prompts_dir)

    def build_system_prompt(
        self,
        tools_schema: list[dict[str, Any]] | None = None,
    ) -> str:
        """Load the agent system prompt template and inject tool descriptions."""
        template = self._load_template(_DEFAULT_TEMPLATE)
        tools_desc = self._format_tools_description(tools_schema or [])
        return template.replace("{tools_description}", tools_desc)

    def build_messages(
        self,
        system_prompt: str,
        conversation_history: list[dict[str, Any]],
        current_query: str,
    ) -> list[dict[str, Any]]:
        """Construct the full message list for the LLM.

        Order: system → history → current user query.
        """
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in conversation_history:
            messages.append(msg)
        messages.append({"role": "user", "content": current_query})
        return messages

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_template(self, filename: str) -> str:
        """Load a prompt template file, falling back to a built-in default."""
        path = self._prompts_dir / filename
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("Prompt template %s not found; using built-in default", path)
            return self._builtin_system_prompt()

    @staticmethod
    def _builtin_system_prompt() -> str:
        return (
            "You are ChipWise, a chip data intelligence assistant.\n"
            "Use the provided tools to answer user queries about semiconductor chips.\n"
            "\nAvailable tools:\n{tools_description}"
        )

    @staticmethod
    def _format_tools_description(tools_schema: list[dict[str, Any]]) -> str:
        """Format tool schemas into a human-readable list for the prompt."""
        if not tools_schema:
            return "(no tools available)"
        lines: list[str] = []
        for tool in tools_schema:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            props = params.get("properties", {})
            required = params.get("required", [])
            param_parts: list[str] = []
            for pname, pinfo in props.items():
                req = " (required)" if pname in required else ""
                param_parts.append(f"    - {pname}: {pinfo.get('type', 'any')}{req} — {pinfo.get('description', '')}")
            params_str = "\n".join(param_parts) if param_parts else "    (no parameters)"
            lines.append(f"- **{name}**: {desc}\n  Parameters:\n{params_str}")
        return "\n".join(lines)
