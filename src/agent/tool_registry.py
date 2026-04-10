"""ToolRegistry — automatic discovery and registration of BaseTool subclasses (§4.8.2).

Provides:
- ``register(tool)``   — add a tool (raises on duplicate name)
- ``get(name)``        — retrieve by name (raises KeyError)
- ``discover(package)``— scan a package for BaseTool subclasses
- ``get_openai_tools_schema()`` — OpenAI function-calling JSON
- ``list_tools()``     — list registered tool names
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any

from src.agent.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for agent tools.

    Tools can be registered manually via :meth:`register` or
    bulk-discovered from the ``src.agent.tools`` package via
    :meth:`discover`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a single tool instance.

        Raises :class:`ValueError` if a tool with the same name is
        already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Use a unique name or unregister the existing tool first."
            )
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool by name. Raises :class:`KeyError` if not found."""
        if name not in self._tools:
            raise KeyError(name)
        del self._tools[name]
        logger.debug("Unregistered tool: %s", name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseTool:
        """Return the tool registered under *name*.

        Raises :class:`KeyError` if the name is not registered.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"No tool registered with name '{name}'. "
                f"Available: {', '.join(sorted(self._tools)) or '(none)'}"
            ) from None

    def get_tool(self, name: str) -> BaseTool | None:
        """Return the tool or ``None`` — backward-compatible accessor."""
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    # ------------------------------------------------------------------
    # Enumeration / Schema
    # ------------------------------------------------------------------

    def list_tools(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools.keys())

    def get_openai_tools_schema(self) -> list[dict[str, Any]]:
        """Return all registered tools in OpenAI function-calling format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    def discover(self, tools_package: str = "src.agent.tools") -> int:
        """Import all modules under *tools_package* and register any
        concrete :class:`BaseTool` subclasses found.

        Already-registered tool names are silently skipped (no error).
        Returns the number of **newly** registered tools.
        """
        count = 0
        try:
            package = importlib.import_module(tools_package)
        except ModuleNotFoundError:
            logger.warning("Package %s not found; skipping discover", tools_package)
            return 0

        pkg_path = getattr(package, "__path__", None)
        if pkg_path is None:
            return 0

        for _importer, modname, _ispkg in pkgutil.iter_modules(pkg_path):
            if modname.startswith("_") or modname == "base_tool":
                continue
            full_name = f"{tools_package}.{modname}"
            try:
                mod = importlib.import_module(full_name)
            except Exception:
                logger.warning("Failed to import %s", full_name, exc_info=True)
                continue

            for _attr_name, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and not inspect.isabstract(obj)
                ):
                    try:
                        instance = obj()
                    except Exception:
                        logger.warning("Could not instantiate %s", obj, exc_info=True)
                        continue

                    if instance.name in self._tools:
                        logger.debug("Skipping already-registered tool: %s", instance.name)
                        continue

                    self._tools[instance.name] = instance
                    logger.debug("Discovered tool: %s", instance.name)
                    count += 1

        logger.info("Discovered %d new tools from %s", count, tools_package)
        return count

    # Backward-compatible alias
    auto_discover = discover
