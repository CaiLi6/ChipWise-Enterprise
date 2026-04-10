"""Unit tests for ToolRegistry."""

from __future__ import annotations

import pytest
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.agent.tool_registry import ToolRegistry


class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "ok"}


class AnotherTool(BaseTool):
    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Another tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": "another ok"}


@pytest.mark.unit
class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get_tool("dummy") is tool

    def test_get_unknown_returns_none(self) -> None:
        reg = ToolRegistry()
        assert reg.get_tool("nonexistent") is None

    def test_list_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        assert sorted(reg.list_tools()) == ["another", "dummy"]

    def test_overwrite_on_re_register(self) -> None:
        reg = ToolRegistry()
        t1 = DummyTool()
        t2 = DummyTool()
        reg.register(t1)
        reg.register(t2)
        assert reg.get_tool("dummy") is t2

    def test_openai_tools_schema(self) -> None:
        reg = ToolRegistry()
        reg.register(DummyTool())
        schema = reg.get_openai_tools_schema()
        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "dummy"
        assert "parameters" in schema[0]["function"]

    def test_to_openai_tool_format(self) -> None:
        tool = DummyTool()
        ot = tool.to_openai_tool()
        assert ot["type"] == "function"
        assert ot["function"]["name"] == "dummy"
        assert ot["function"]["description"] == "A dummy tool for testing"

    def test_auto_discover_no_crash(self) -> None:
        """auto_discover on the tools package should not crash."""
        reg = ToolRegistry()
        count = reg.auto_discover("src.agent.tools")
        # No concrete tools exist yet (base_tool is skipped)
        assert count >= 0

    def test_auto_discover_nonexistent_package(self) -> None:
        reg = ToolRegistry()
        count = reg.auto_discover("nonexistent.package")
        assert count == 0


@pytest.mark.unit
class TestBaseTool:
    def test_abstract_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self) -> None:
        tool = DummyTool()
        result = await tool.execute(x="hello")
        assert isinstance(result, dict)
        assert result["result"] == "ok"
