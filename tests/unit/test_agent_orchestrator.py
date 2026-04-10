"""Unit tests for Agent Orchestrator ReAct loop."""

from __future__ import annotations

import json
import pytest
from typing import Any

from src.agent.orchestrator import AgentOrchestrator, AgentResult
from src.agent.tool_registry import ToolRegistry
from src.agent.tools.base_tool import BaseTool


# ------------------------------------------------------------------
# Mock Tool
# ------------------------------------------------------------------
class MockSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_search"

    @property
    def description(self) -> str:
        return "Search for chip data"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return {"result": f"Found data for: {kwargs.get('query', '')}"}


class ErrorTool(BaseTool):
    @property
    def name(self) -> str:
        return "error_tool"

    @property
    def description(self) -> str:
        return "A tool that always fails"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Tool failure!")


# ------------------------------------------------------------------
# Mock LLM
# ------------------------------------------------------------------
class MockLLM:
    """Controllable mock LLM for testing the ReAct loop."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = _final_answer("Fallback answer")
        self._call_count += 1
        return resp


def _tool_call_response(tool_name: str, arguments: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
    return {
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"total_tokens": 100},
    }


def _final_answer(text: str) -> dict[str, Any]:
    return {
        "choices": [{
            "message": {"content": text},
            "finish_reason": "stop",
        }],
        "usage": {"total_tokens": 50},
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
@pytest.mark.unit
class TestAgentOrchestrator:
    def _make_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register(MockSearchTool())
        reg.register(ErrorTool())
        return reg

    @pytest.mark.asyncio
    async def test_direct_answer(self) -> None:
        """LLM returns final answer without tool calls."""
        llm = MockLLM([_final_answer("STM32F4 runs at 168 MHz.")])
        orch = AgentOrchestrator(llm, self._make_registry())
        result = await orch.run("What is the clock speed of STM32F4?")
        assert isinstance(result, AgentResult)
        assert "168 MHz" in result.answer
        assert result.stopped_reason == "complete"
        assert len(result.iterations) == 1

    @pytest.mark.asyncio
    async def test_tool_call_then_answer(self) -> None:
        """LLM calls a tool, gets observation, then answers."""
        llm = MockLLM([
            _tool_call_response("mock_search", {"query": "STM32F4 clock"}),
            _final_answer("Based on search: 168 MHz."),
        ])
        orch = AgentOrchestrator(llm, self._make_registry())
        result = await orch.run("Clock speed of STM32F4?")
        assert result.stopped_reason == "complete"
        assert len(result.iterations) == 2
        assert result.iterations[0].tool_calls[0].tool_name == "mock_search"
        assert "Found data" in json.dumps(result.iterations[0].observations[0])

    @pytest.mark.asyncio
    async def test_unknown_tool(self) -> None:
        """LLM requests a tool that doesn't exist."""
        llm = MockLLM([
            _tool_call_response("nonexistent_tool", {}),
            _final_answer("I couldn't find that tool."),
        ])
        orch = AgentOrchestrator(llm, self._make_registry())
        result = await orch.run("test")
        assert "error" in result.iterations[0].observations[0]

    @pytest.mark.asyncio
    async def test_tool_error_handled(self) -> None:
        """Tool raises exception; agent continues gracefully."""
        llm = MockLLM([
            _tool_call_response("error_tool", {}),
            _final_answer("Tool failed, but I can still answer."),
        ])
        orch = AgentOrchestrator(llm, self._make_registry())
        result = await orch.run("trigger error")
        assert "error" in result.iterations[0].observations[0]
        assert result.stopped_reason == "complete"

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self) -> None:
        """Agent stops when max iterations reached."""
        responses = [
            _tool_call_response("mock_search", {"query": "q"}, f"call_{i}")
            for i in range(10)
        ]
        llm = MockLLM(responses)
        orch = AgentOrchestrator(llm, self._make_registry(), max_iterations=3)
        result = await orch.run("test max iter")
        assert result.stopped_reason == "max_iterations"
        assert len(result.iterations) == 3

    @pytest.mark.asyncio
    async def test_token_budget_exhaustion(self) -> None:
        """Agent stops when token budget is exhausted."""
        resp_high_usage = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "c1",
                        "function": {"name": "mock_search", "arguments": '{"query":"x"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"total_tokens": 5000},
        }
        llm = MockLLM([resp_high_usage, resp_high_usage, _final_answer("done")])
        orch = AgentOrchestrator(llm, self._make_registry(), max_tokens=8000)
        result = await orch.run("big query")
        assert result.stopped_reason == "token_budget_exhausted"

    @pytest.mark.asyncio
    async def test_token_tracking(self) -> None:
        """Tokens are accumulated across iterations."""
        llm = MockLLM([
            _tool_call_response("mock_search", {"query": "a"}),
            _final_answer("answer"),
        ])
        orch = AgentOrchestrator(llm, self._make_registry())
        result = await orch.run("test")
        assert result.total_tokens == 150  # 100 + 50
