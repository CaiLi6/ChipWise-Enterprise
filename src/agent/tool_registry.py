"""ToolRegistry — automatic discovery and registration of BaseTool subclasses (§4.8.2)."""

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
    :meth:`auto_discover`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Overwrites if name already exists."""
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_openai_tools_schema(self) -> list[dict[str, Any]]:
        """Return all registered tools in OpenAI function-calling format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def auto_discover(self, package_name: str = "src.agent.tools") -> int:
        """Import all modules under *package_name* and register any
        concrete :class:`BaseTool` subclasses found.

        Returns the number of newly registered tools.
        """
        count = 0
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning("Package %s not found; skipping auto-discover", package_name)
            return 0

        pkg_path = getattr(package, "__path__", None)
        if pkg_path is None:
            return 0

        for _importer, modname, _ispkg in pkgutil.iter_modules(pkg_path):
            if modname.startswith("_") or modname == "base_tool":
                continue
            full_name = f"{package_name}.{modname}"
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
                    and obj.name.fget is not None  # type: ignore[union-attr]
                ):
                    try:
                        instance = obj()
                        if instance.name not in self._tools:
                            self.register(instance)
                            count += 1
                    except Exception:
                        logger.warning("Could not instantiate %s", obj, exc_info=True)

        logger.info("Auto-discovered %d tools from %s", count, package_name)
        return count
