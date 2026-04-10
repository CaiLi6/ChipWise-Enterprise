"""Agent Orchestrator — ReAct main loop skeleton (§4.8.1).

Implements the Thought → Tool Call → Observation → Final Answer cycle.
Phase 2 (task 2C2) fills in real LLM integration and advanced features.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.agent.tool_registry import ToolRegistry
from src.agent.safety.token_budget import TokenBudget

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_TOKENS = 8192


# ------------------------------------------------------------------
# LLM protocol — allows mocking in tests
# ------------------------------------------------------------------
class LLMClient(Protocol):
    """Minimal protocol a language model client must satisfy."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return an OpenAI-compatible chat completion response dict."""
        ...


# ------------------------------------------------------------------
# Data classes for the ReAct trace
# ------------------------------------------------------------------
@dataclass
class ToolCallRequest:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class Iteration:
    thought: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    answer: str
    iterations: list[Iteration] = field(default_factory=list)
    total_tokens: int = 0
    stopped_reason: str = "complete"


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
class AgentOrchestrator:
    """ReAct agent loop: Thought → Tool Calls → Observations → repeat or Final Answer."""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_iterations = max_iterations
        self.budget = TokenBudget(max_tokens)

    async def run(self, user_query: str, system_prompt: str = "") -> AgentResult:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_query})

        tools_schema = self.registry.get_openai_tools_schema()
        iterations: list[Iteration] = []

        for i in range(self.max_iterations):
            if self.budget.exhausted:
                logger.warning("Token budget exhausted at iteration %d", i)
                return AgentResult(
                    answer="I've used all available tokens. Here's what I found so far.",
                    iterations=iterations,
                    total_tokens=self.budget.used,
                    stopped_reason="token_budget_exhausted",
                )

            response = await self.llm.chat(messages, tools=tools_schema or None)
            usage = response.get("usage", {})
            self.budget.consume(usage.get("total_tokens", 0))

            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            iteration = Iteration(thought=message.get("content", "") or "")

            # Check for tool calls
            tool_calls_raw = message.get("tool_calls", [])
            if not tool_calls_raw or finish_reason == "stop":
                # Final answer
                iterations.append(iteration)
                return AgentResult(
                    answer=message.get("content", ""),
                    iterations=iterations,
                    total_tokens=self.budget.used,
                    stopped_reason="complete",
                )

            # Process tool calls
            messages.append(message)
            for tc in tool_calls_raw:
                func = tc.get("function", {})
                call_id = tc.get("id", "")
                tool_name = func.get("name", "")
                try:
                    arguments = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                tc_req = ToolCallRequest(
                    tool_name=tool_name,
                    arguments=arguments,
                    call_id=call_id,
                )
                iteration.tool_calls.append(tc_req)

                tool = self.registry.get_tool(tool_name)
                if tool is None:
                    observation = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        observation = await tool.execute(**arguments)
                    except Exception as exc:
                        logger.exception("Tool %s raised an error", tool_name)
                        observation = {"error": str(exc)}

                iteration.observations.append(observation)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(observation, ensure_ascii=False),
                })

            iterations.append(iteration)

        # Exhausted max iterations
        return AgentResult(
            answer="Reached maximum iterations. Returning partial results.",
            iterations=iterations,
            total_tokens=self.budget.used,
            stopped_reason="max_iterations",
        )
