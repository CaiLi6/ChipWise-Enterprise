"""Unit tests for Agent Orchestrator ReAct loop (task 2C2).

Acceptance criteria:
- Mock LLM → tool_calls → FakeTool executed → Observation fed back → answer
- Iterations ≤ max_iterations
- parallel_tool_calls=True → asyncio.gather parallel execution
- Per-tool timeout (30s default) → timeout error, no blocking
- Trace records each iteration's thought/tool_calls/observations/tokens
"""

from __future__ import annotations

import asyncio
import json
import pytest
from typing import Any
from unittest.mock import AsyncMock

from src.agent.orchestrator import AgentOrchestrator, AgentConfig, AgentResult, AgentStep
from src.agent.prompt_builder import PromptBuilder
from src.agent.tool_registry import ToolRegistry
from src.agent.tools.base_tool import BaseTool
from src.libs.llm.base import BaseLLM, LLMResponse, ToolCall
from src.observability.trace_context import TraceContext


# ------------------------------------------------------------------
# Fake Tools
# ------------------------------------------------------------------
class FakeSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "fake_search"

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


class FakeSlowTool(BaseTool):
    """A tool that takes a long time — used to test timeout."""

    @property
    def name(self) -> str:
        return "slow_tool"

    @property
    def description(self) -> str:
        return "A slow tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(60)
        return {"result": "done"}


class FakeErrorTool(BaseTool):
    @property
    def name(self) -> str:
        return "error_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Tool failure!")


class FakeCounterTool(BaseTool):
    """Tracks how many times execute is called, for parallel testing."""

    def __init__(self) -> None:
        self._call_times: list[float] = []

    @property
    def name(self) -> str:
        return "counter"

    @property
    def description(self) -> str:
        return "Counter tool"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"id": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        import time
        self._call_times.append(time.monotonic())
        await asyncio.sleep(0.05)
        return {"result": f"counted {kwargs.get('id', '?')}"}


# ------------------------------------------------------------------
# Mock LLM using BaseLLM
# ------------------------------------------------------------------
class MockLLM(BaseLLM):
    """Controllable mock that returns pre-scripted LLMResponse objects."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return LLMResponse(text="generated")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = LLMResponse(text="Fallback answer", usage={"total_tokens": 10})
        self._call_count += 1
        return resp


# ------------------------------------------------------------------
# Helper factories
# ------------------------------------------------------------------
def _tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
    call_id: str = "call_1",
    tokens: int = 100,
) -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=arguments)],
        usage={"total_tokens": tokens},
    )


def _multi_tool_response(
    calls: list[tuple[str, dict[str, Any], str]],
    tokens: int = 100,
) -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=[
            ToolCall(id=cid, name=name, arguments=args)
            for name, args, cid in calls
        ],
        usage={"total_tokens": tokens},
    )


def _final_answer(text: str, tokens: int = 50) -> LLMResponse:
    return LLMResponse(text=text, usage={"total_tokens": tokens})


def _make_registry(*tools: BaseTool) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
@pytest.mark.unit
class TestAgentOrchestrator:
    """Core ReAct loop behavior."""

    @pytest.mark.asyncio
    async def test_direct_answer(self) -> None:
        """LLM returns final answer without tool calls."""
        llm = MockLLM([_final_answer("STM32F4 runs at 168 MHz.")])
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("What is the clock speed of STM32F4?")
        assert isinstance(result, AgentResult)
        assert "168 MHz" in result.answer
        assert result.stopped_reason == "complete"
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_tool_call_then_answer(self) -> None:
        """LLM calls a tool, gets observation, then answers."""
        llm = MockLLM([
            _tool_call_response("fake_search", {"query": "STM32F4 clock"}),
            _final_answer("Based on search: 168 MHz."),
        ])
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("Clock speed?")
        assert result.stopped_reason == "complete"
        assert result.iterations == 2
        assert len(result.tool_calls_log) == 2
        step0 = result.tool_calls_log[0]
        assert step0.tool_calls[0].tool_name == "fake_search"
        assert "Found data" in json.dumps(step0.observations[0])

    @pytest.mark.asyncio
    async def test_unknown_tool(self) -> None:
        """LLM requests a tool that doesn't exist."""
        llm = MockLLM([
            _tool_call_response("nonexistent_tool", {}),
            _final_answer("I couldn't find that tool."),
        ])
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("test")
        assert "error" in result.tool_calls_log[0].observations[0]

    @pytest.mark.asyncio
    async def test_tool_error_handled(self) -> None:
        """Tool raises exception; agent continues gracefully."""
        llm = MockLLM([
            _tool_call_response("error_tool", {}),
            _final_answer("Tool failed, but I can still answer."),
        ])
        orch = AgentOrchestrator(llm, _make_registry(FakeErrorTool()))
        result = await orch.run("trigger error")
        obs = result.tool_calls_log[0].observations[0]
        assert "error" in obs
        assert result.stopped_reason == "complete"

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self) -> None:
        """Agent stops when max iterations reached."""
        responses = [
            _tool_call_response("fake_search", {"query": "q"}, f"call_{i}")
            for i in range(10)
        ]
        llm = MockLLM(responses)
        config = AgentConfig(max_iterations=3)
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()), config=config)
        result = await orch.run("test max iter")
        assert result.stopped_reason == "max_iterations"
        assert result.iterations == 3

    @pytest.mark.asyncio
    async def test_token_budget_exhaustion(self) -> None:
        """Agent stops when token budget is exhausted."""
        llm = MockLLM([
            _tool_call_response("fake_search", {"query": "x"}, "c1", tokens=5000),
            _tool_call_response("fake_search", {"query": "y"}, "c2", tokens=5000),
        ])
        config = AgentConfig(max_total_tokens=8000)
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()), config=config)
        result = await orch.run("big query")
        assert result.stopped_reason == "token_budget_exhausted"

    @pytest.mark.asyncio
    async def test_token_tracking(self) -> None:
        """Tokens are accumulated across iterations."""
        llm = MockLLM([
            _tool_call_response("fake_search", {"query": "a"}, tokens=100),
            _final_answer("answer", tokens=50),
        ])
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("test")
        assert result.total_tokens == 150

    @pytest.mark.asyncio
    async def test_per_step_token_usage(self) -> None:
        """Each AgentStep records its own token_usage."""
        llm = MockLLM([
            _tool_call_response("fake_search", {"query": "a"}, tokens=120),
            _final_answer("done", tokens=80),
        ])
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("test")
        assert result.tool_calls_log[0].token_usage == 120
        assert result.tool_calls_log[1].token_usage == 80


@pytest.mark.unit
class TestParallelToolCalls:
    """Parallel tool execution via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        """Multiple tool calls run concurrently when parallel=True."""
        counter = FakeCounterTool()
        reg = _make_registry(counter)
        llm = MockLLM([
            _multi_tool_response([
                ("counter", {"id": "a"}, "c1"),
                ("counter", {"id": "b"}, "c2"),
                ("counter", {"id": "c"}, "c3"),
            ]),
            _final_answer("done"),
        ])
        config = AgentConfig(parallel_tool_calls=True)
        orch = AgentOrchestrator(llm, reg, config=config)
        result = await orch.run("test parallel")
        # All 3 calls should have been made
        assert len(result.tool_calls_log[0].observations) == 3
        # Call times should be very close (parallel, not sequential)
        times = counter._call_times
        assert len(times) == 3
        spread = max(times) - min(times)
        assert spread < 0.1  # All started within 100ms of each other

    @pytest.mark.asyncio
    async def test_sequential_execution(self) -> None:
        """When parallel=False, tools run sequentially."""
        counter = FakeCounterTool()
        reg = _make_registry(counter)
        llm = MockLLM([
            _multi_tool_response([
                ("counter", {"id": "a"}, "c1"),
                ("counter", {"id": "b"}, "c2"),
            ]),
            _final_answer("done"),
        ])
        config = AgentConfig(parallel_tool_calls=False)
        orch = AgentOrchestrator(llm, reg, config=config)
        result = await orch.run("test sequential")
        assert len(result.tool_calls_log[0].observations) == 2


@pytest.mark.unit
class TestToolTimeout:
    """Per-tool timeout handling."""

    @pytest.mark.asyncio
    async def test_tool_timeout(self) -> None:
        """A slow tool returns timeout error without blocking."""
        llm = MockLLM([
            _tool_call_response("slow_tool", {}),
            _final_answer("timed out tool"),
        ])
        config = AgentConfig(tool_timeout=0.1)  # 100ms timeout
        orch = AgentOrchestrator(llm, _make_registry(FakeSlowTool()), config=config)
        result = await orch.run("test timeout")
        obs = result.tool_calls_log[0].observations[0]
        assert "timed out" in obs.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_timeout_does_not_block_other_tools(self) -> None:
        """One tool timing out doesn't block parallel siblings."""
        slow = FakeSlowTool()
        search = FakeSearchTool()
        reg = ToolRegistry()
        reg.register(slow)
        reg.register(search)

        llm = MockLLM([
            _multi_tool_response([
                ("slow_tool", {}, "c_slow"),
                ("fake_search", {"query": "ok"}, "c_search"),
            ]),
            _final_answer("done"),
        ])
        config = AgentConfig(tool_timeout=0.1, parallel_tool_calls=True)
        orch = AgentOrchestrator(llm, reg, config=config)
        result = await orch.run("test")
        obs = result.tool_calls_log[0].observations
        # slow_tool timed out
        assert "timed out" in obs[0].get("error", "").lower()
        # fake_search succeeded
        assert "Found data" in obs[1].get("result", "")


@pytest.mark.unit
class TestTraceContext:
    """Trace recording per iteration."""

    @pytest.mark.asyncio
    async def test_trace_records_iterations(self) -> None:
        """Trace records each iteration's metadata."""
        llm = MockLLM([
            _tool_call_response("fake_search", {"query": "x"}),
            _final_answer("answer"),
        ])
        trace = TraceContext(trace_id="test-trace")
        orch = AgentOrchestrator(llm, _make_registry(FakeSearchTool()))
        result = await orch.run("test", trace=trace)

        stages = trace.stages
        assert len(stages) >= 2
        iteration_stage = next(s for s in stages if s.stage == "iteration")
        assert "tool_calls" in iteration_stage.metadata
        assert "fake_search" in iteration_stage.metadata["tool_calls"]
        final_stage = next(s for s in stages if s.stage == "final_answer")
        assert final_stage.metadata["iteration"] == 1

    @pytest.mark.asyncio
    async def test_trace_not_required(self) -> None:
        """Orchestrator works fine without a trace."""
        llm = MockLLM([_final_answer("ok")])
        orch = AgentOrchestrator(llm, _make_registry())
        result = await orch.run("test")
        assert result.stopped_reason == "complete"


@pytest.mark.unit
class TestPromptBuilder:
    """PromptBuilder builds system prompt and message list."""

    def test_build_system_prompt_loads_template(self) -> None:
        builder = PromptBuilder()
        prompt = builder.build_system_prompt([])
        assert "ChipWise" in prompt

    def test_build_system_prompt_injects_tools(self) -> None:
        builder = PromptBuilder()
        schema = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"q": {"type": "string", "description": "query"}},
                    "required": ["q"],
                },
            },
        }]
        prompt = builder.build_system_prompt(schema)
        assert "test_tool" in prompt
        assert "A test tool" in prompt

    def test_build_messages_order(self) -> None:
        builder = PromptBuilder()
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        msgs = builder.build_messages("system prompt", history, "new question")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "system prompt"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "hello"
        assert msgs[2]["role"] == "assistant"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "new question"

    def test_build_messages_no_history(self) -> None:
        builder = PromptBuilder()
        msgs = builder.build_messages("sys", [], "query")
        assert len(msgs) == 2
        assert msgs[0]["content"] == "sys"
        assert msgs[1]["content"] == "query"

    def test_fallback_when_template_missing(self, tmp_path: Any) -> None:
        builder = PromptBuilder(prompts_dir=tmp_path / "nonexistent")
        prompt = builder.build_system_prompt([])
        assert "ChipWise" in prompt


@pytest.mark.unit
class TestAgentConfig:
    def test_defaults(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_iterations == 5
        assert cfg.max_total_tokens == 8192
        assert cfg.parallel_tool_calls is True
        assert cfg.temperature == 0.1
        assert cfg.tool_timeout == 30.0
        assert cfg.llm_role == "primary"

    def test_custom_values(self) -> None:
        cfg = AgentConfig(max_iterations=10, tool_timeout=60.0, parallel_tool_calls=False)
        assert cfg.max_iterations == 10
        assert cfg.tool_timeout == 60.0
        assert cfg.parallel_tool_calls is False
