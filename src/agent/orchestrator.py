"""Agent Orchestrator — ReAct main loop (§4.8.1, task 2C2).

Drives the Thought → Tool Calls → Observation → Final Answer cycle.
Supports parallel tool execution, per-tool timeout, token budget, and
TraceContext recording.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.agent.prompt_builder import PromptBuilder
from src.agent.safety.token_budget import TokenBudget
from src.agent.tool_registry import ToolRegistry
from src.libs.llm.base import BaseLLM, LLMResponse, ToolCall
from src.observability.trace_context import TraceContext

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
@dataclass
class AgentConfig:
    """Runtime configuration for the Agent orchestrator."""
    max_iterations: int = 5
    max_total_tokens: int = 8192
    parallel_tool_calls: bool = True
    temperature: float = 0.1
    tool_timeout: float = 30.0
    llm_role: str = "primary"
    # Truncate JSON-serialized tool observations fed back into the next
    # ReAct round. RAG chunks are otherwise the dominant source of input
    # token bloat and quickly exhaust max_total_tokens.
    max_observation_chars: int = 4000


# ------------------------------------------------------------------
# Data classes for the ReAct trace
# ------------------------------------------------------------------
@dataclass
class ToolCallRequest:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class AgentStep:
    """One iteration of the ReAct loop."""
    thought: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    token_usage: int = 0


@dataclass
class AgentResult:
    """Final output of the orchestrator."""
    answer: str
    tool_calls_log: list[AgentStep] = field(default_factory=list)
    total_tokens: int = 0
    iterations: int = 0
    stopped_reason: str = "complete"


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
class AgentOrchestrator:
    """ReAct agent loop: Thought → Tool Calls → Observations → repeat or Final Answer."""

    def __init__(
        self,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        config: AgentConfig | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.llm = llm
        self.registry = tool_registry
        self.config = config or AgentConfig()
        self.prompt_builder = prompt_builder or PromptBuilder()

    async def run(
        self,
        query: str,
        conversation_history: list[dict[str, Any]] | None = None,
        trace: TraceContext | None = None,
    ) -> AgentResult:
        """Execute the ReAct loop for *query*."""
        budget = TokenBudget(self.config.max_total_tokens)
        tools_schema = self.registry.get_openai_tools_schema()

        # Build messages
        system_prompt = self.prompt_builder.build_system_prompt(tools_schema)
        messages = self.prompt_builder.build_messages(
            system_prompt,
            conversation_history or [],
            query,
        )

        steps: list[AgentStep] = []

        for i in range(self.config.max_iterations):
            # Check budget
            if budget.exhausted:
                logger.warning("Token budget exhausted at iteration %d", i)
                if trace:
                    trace.record_stage("budget_exhausted", {"iteration": i})
                return AgentResult(
                    answer=self._early_stop_answer(
                        "token_budget_exhausted", i, budget.used, steps,
                    ),
                    tool_calls_log=steps,
                    total_tokens=budget.used,
                    iterations=i,
                    stopped_reason="token_budget_exhausted",
                )

            # Call LLM
            llm_response: LLMResponse = await self.llm.chat(
                messages,
                tools=tools_schema or None,
                temperature=self.config.temperature,
            )
            token_count = llm_response.usage.get("total_tokens", 0)
            budget.consume(token_count)

            step = AgentStep(
                thought=llm_response.text or "",
                token_usage=token_count,
            )

            # No tool calls → final answer
            if not llm_response.tool_calls:
                steps.append(step)
                if trace:
                    trace.record_stage("final_answer", {
                        "iteration": i,
                        "tokens": token_count,
                    })
                return AgentResult(
                    answer=llm_response.text or "",
                    tool_calls_log=steps,
                    total_tokens=budget.used,
                    iterations=i + 1,
                    stopped_reason="complete",
                )

            # Process tool calls
            # Add assistant message with tool_calls to conversation
            assistant_msg = self._build_assistant_message(llm_response)
            messages.append(assistant_msg)

            # Execute tools (parallel or sequential)
            tc_requests, observations = await self._execute_tool_calls(
                llm_response.tool_calls,
            )
            step.tool_calls = tc_requests
            step.observations = observations

            # Append tool results to messages (truncated to keep prompt small)
            for tc, obs in zip(llm_response.tool_calls, observations, strict=False):
                content = json.dumps(obs, ensure_ascii=False)
                cap = self.config.max_observation_chars
                if cap and len(content) > cap:
                    content = (
                        content[:cap]
                        + f"\n…[truncated {len(content) - cap} chars to preserve token budget]"
                    )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                })

            steps.append(step)

            if trace:
                trace.record_stage("iteration", {
                    "index": i,
                    "thought": step.thought[:200],
                    "tool_calls": [t.tool_name for t in tc_requests],
                    "tokens": token_count,
                })

        # Exhausted max iterations
        if trace:
            trace.record_stage("max_iterations", {"iterations": self.config.max_iterations})

        return AgentResult(
            answer=self._early_stop_answer(
                "max_iterations", self.config.max_iterations, budget.used, steps,
            ),
            tool_calls_log=steps,
            total_tokens=budget.used,
            iterations=self.config.max_iterations,
            stopped_reason="max_iterations",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
    ) -> tuple[list[ToolCallRequest], list[dict[str, Any]]]:
        """Execute tool calls, respecting parallel_tool_calls and tool_timeout."""
        tc_requests: list[ToolCallRequest] = []
        for tc in tool_calls:
            tc_requests.append(ToolCallRequest(
                tool_name=tc.name,
                arguments=tc.arguments,
                call_id=tc.id,
            ))

        if self.config.parallel_tool_calls and len(tool_calls) > 1:
            observations = await self._execute_parallel(tool_calls)
        else:
            observations = await self._execute_sequential(tool_calls)

        return tc_requests, observations

    async def _execute_parallel(
        self,
        tool_calls: list[ToolCall],
    ) -> list[dict[str, Any]]:
        """Execute multiple tool calls concurrently with timeout."""
        tasks = [
            self._run_single_tool(tc.name, tc.arguments)
            for tc in tool_calls
        ]
        return list(await asyncio.gather(*tasks))

    async def _execute_sequential(
        self,
        tool_calls: list[ToolCall],
    ) -> list[dict[str, Any]]:
        """Execute tool calls one at a time."""
        results: list[dict[str, Any]] = []
        for tc in tool_calls:
            result = await self._run_single_tool(tc.name, tc.arguments)
            results.append(result)
        return results

    async def _run_single_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a single tool with timeout protection."""
        try:
            tool = self.registry.get(tool_name)
        except KeyError:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await asyncio.wait_for(
                tool.execute(**arguments),
                timeout=self.config.tool_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("Tool %s timed out after %.1fs", tool_name, self.config.tool_timeout)
            return {"error": f"Tool '{tool_name}' timed out after {self.config.tool_timeout}s"}
        except Exception as exc:
            logger.exception("Tool %s raised an error", tool_name)
            return {"error": str(exc)}

    @staticmethod
    def _early_stop_answer(
        reason: str, iterations: int, tokens_used: int, steps: list[AgentStep],
    ) -> str:
        """Render a Chinese, actionable message for early-stop exits.

        Downstream Grounding Gate further replaces/annotates this — but we
        still want a useful base string for callers that bypass grounding.
        """
        tool_names: list[str] = []
        for s in steps:
            for t in s.tool_calls:
                if t.tool_name not in tool_names:
                    tool_names.append(t.tool_name)
        tools_str = "、".join(tool_names) if tool_names else "无"
        reason_cn = {
            "token_budget_exhausted": (
                f"Agent 在检索过程中用尽了本次请求的 token 预算"
                f"（~{tokens_used} tokens，已跑 {iterations} 轮工具调用）"
            ),
            "max_iterations": f"Agent 达到最大迭代次数 {iterations}，仍未得出结论",
        }.get(reason, f"Agent 提前停止（{reason}）")
        return (
            "## 结论\n\n"
            "暂无法给出可靠答案。\n\n"
            "## 原因\n\n"
            f"{reason_cn}。已调用工具: **{tools_str}**。\n\n"
            "## 建议\n\n"
            "- 把问题拆成更具体的单点查询（例如：只问“用户 IO 总数”而非多参数一次问）\n"
            "- 指定参数类别关键词（`DSP 数量`、`PCIe Gen`、`封装引脚`）帮助 SQL 直达\n"
            "- 若确认问题已足够简短，请联系管理员扩大 `agent.max_total_tokens`"
        )

    @staticmethod
    def _build_assistant_message(response: LLMResponse) -> dict[str, Any]:
        """Build the assistant message dict for the conversation history."""
        msg: dict[str, Any] = {"role": "assistant", "content": response.text or None}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg
