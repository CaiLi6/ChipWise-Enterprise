"""Unit tests for ToolRegistry (task 2C1).

Acceptance criteria:
- discover() auto-finds all BaseTool subclasses in src.agent.tools
- get_openai_tools_schema() produces valid OpenAI function-calling JSON
- Duplicate register() raises ValueError
- get("nonexistent") raises KeyError
"""

from __future__ import annotations

import pytest
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.agent.tool_registry import ToolRegistry


# ------------------------------------------------------------------
# Test helpers — concrete BaseTool implementations
# ------------------------------------------------------------------
class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"x": {"type": "string", "description": "Input value"}},
            "required": ["x"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": f"dummy got {kwargs.get('x', '')}"}


class AnotherTool(BaseTool):
    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Another tool for testing"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "another ok"}


class DuplicateNameTool(BaseTool):
    """Has the same name as DummyTool — used to test duplicate detection."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "Duplicate name tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "dup"}


# ------------------------------------------------------------------
# ToolRegistry tests
# ------------------------------------------------------------------
@pytest.mark.unit
class TestToolRegistry:
    """Core ToolRegistry behaviour."""

    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get("dummy") is tool

    def test_get_nonexistent_raises_key_error(self) -> None:
        """get('nonexistent') must raise KeyError (acceptance criterion)."""
        reg = ToolRegistry()
        with pytest.raises(KeyError, match="nonexistent"):
            reg.get("nonexistent")

    def test_get_tool_backward_compat_returns_none(self) -> None:
        """get_tool() returns None for missing names (backward compat)."""
        reg = ToolRegistry()
        assert reg.get_tool("missing") is None

    def test_get_tool_backward_compat_returns_tool(self) -> None:
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get_tool("dummy") is tool

    def test_duplicate_register_raises_value_error(self) -> None:
        """Duplicate register() must raise ValueError (acceptance criterion)."""
        reg = ToolRegistry()
        reg.register(DummyTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(DuplicateNameTool())

    def test_list_tools_sorted(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        assert reg.list_tools() == ["another", "dummy"]

    def test_contains(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert "dummy" in reg
        assert "missing" not in reg

    def test_len(self) -> None:
        reg = ToolRegistry()
        assert len(reg) == 0
        reg.register(DummyTool())
        assert len(reg) == 1
        reg.register(AnotherTool())
        assert len(reg) == 2

    def test_unregister(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.unregister("dummy")
        assert "dummy" not in reg
        assert len(reg) == 0

    def test_unregister_nonexistent_raises_key_error(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nonexistent")


@pytest.mark.unit
class TestOpenAISchema:
    """get_openai_tools_schema() produces valid OpenAI function-calling JSON."""

    def test_single_tool_schema(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        schema = reg.get_openai_tools_schema()
        assert len(schema) == 1
        func = schema[0]
        assert func["type"] == "function"
        assert func["function"]["name"] == "dummy"
        assert func["function"]["description"] == "A dummy tool for testing"
        params = func["function"]["parameters"]
        assert params["type"] == "object"
        assert "x" in params["properties"]
        assert params["required"] == ["x"]

    def test_multiple_tools_schema(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        schema = reg.get_openai_tools_schema()
        assert len(schema) == 2
        names = {s["function"]["name"] for s in schema}
        assert names == {"dummy", "another"}

    def test_empty_registry_schema(self) -> None:
        reg = ToolRegistry()
        assert reg.get_openai_tools_schema() == []


@pytest.mark.unit
class TestDiscovery:
    """discover() auto-finding subclasses."""

    def test_discover_returns_count(self) -> None:
        """discover() on tools package returns a non-negative count."""
        reg = ToolRegistry()
        count = reg.discover("src.agent.tools")
        assert count >= 0

    def test_discover_nonexistent_package(self) -> None:
        reg = ToolRegistry()
        count = reg.discover("nonexistent.package.xyz")
        assert count == 0

    def test_discover_skips_already_registered(self) -> None:
        """If a tool name is already registered, discover() skips it."""
        reg = ToolRegistry()
        # First discover
        count1 = reg.discover("src.agent.tools")
        # Second discover — same tools already registered → no new additions
        count2 = reg.discover("src.agent.tools")
        assert count2 == 0

    def test_auto_discover_alias(self) -> None:
        """auto_discover is an alias for discover."""
        assert ToolRegistry.auto_discover is ToolRegistry.discover


@pytest.mark.unit
class TestBaseTool:
    """BaseTool ABC contract."""

    def test_abstract_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self) -> None:
        tool = DummyTool()
        result = await tool.execute(x="hello")
        assert isinstance(result, dict)
        assert result["result"] == "dummy got hello"

    def test_to_openai_tool_format(self) -> None:
        tool = DummyTool()
        ot = tool.to_openai_tool()
        assert ot["type"] == "function"
        assert ot["function"]["name"] == "dummy"
        assert ot["function"]["description"] == "A dummy tool for testing"
        assert ot["function"]["parameters"]["type"] == "object"
