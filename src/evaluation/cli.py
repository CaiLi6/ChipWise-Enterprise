"""Command-line interface for the RAG evaluation harness.

Usage::

    python -m src.evaluation.cli run --golden                  # replay full golden set
    python -m src.evaluation.cli run --golden --limit 50       # subset
    python -m src.evaluation.cli run --traces --limit 100      # replay recent traces
    python -m src.evaluation.cli run --traces --trace-ids id1 id2

Both modes write each per-sample evaluation to ``logs/evaluations.jsonl`` and
the batch metadata + aggregates to ``logs/eval_batches.jsonl``. Use
``--judge router|primary`` to switch which LM Studio model judges (router =
qwen3-1.7b, primary = qwen3-35b).

Example::

    python -m src.evaluation.cli run --golden --judge router

The CLI mirrors what ``POST /api/v1/evaluations/run`` does but is convenient
for headless cron / pre-deploy A/B sweeps.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger("chipwise.eval.cli")


def _resolve_judge_llm(judge: str) -> tuple[Any, str]:
    """Return ``(judge_llm, judge_model_name)`` from settings.

    ``judge`` selects which slot in ``llm:`` block to use ("router" or "primary").
    """
    from src.api.dependencies import get_settings
    from src.libs.llm.factory import LLMFactory

    settings = get_settings()
    cfg = settings.llm.router if judge == "router" else settings.llm.primary
    llm = LLMFactory.create(cfg.model_dump())
    return llm, cfg.model


async def _run_golden(judge: str, limit: int | None) -> dict[str, Any]:
    from src.agent.orchestrator import AgentConfig, AgentOrchestrator
    from src.agent.prompt_builder import PromptBuilder
    from src.agent.tool_registry import ToolRegistry
    from src.api.dependencies import get_settings
    from src.evaluation.batch_runner import run_batch_on_golden
    from src.libs.llm.factory import LLMFactory

    settings = get_settings()
    judge_llm, judge_name = _resolve_judge_llm(judge)

    primary_llm = LLMFactory.create(settings.llm.primary.model_dump())
    registry = ToolRegistry()
    registry.discover()
    PromptBuilder()
    orch = AgentOrchestrator(
        llm=primary_llm,
        tool_registry=registry,
        config=AgentConfig(
            max_iterations=settings.agent.max_iterations,
            max_total_tokens=settings.agent.max_total_tokens,
        ),
    )
    batch = await run_batch_on_golden(
        judge_llm=judge_llm,
        orchestrator=orch,
        judge_model_name=judge_name,
    )
    if limit:
        logger.info("(limit=%s ignored — golden runs full set)", limit)
    return batch.__dict__


async def _run_traces(
    judge: str, limit: int, trace_ids: list[str] | None
) -> dict[str, Any]:
    from src.evaluation.batch_runner import run_batch_from_traces

    judge_llm, judge_name = _resolve_judge_llm(judge)
    batch = await run_batch_from_traces(
        judge_llm=judge_llm,
        judge_model_name=judge_name,
        trace_ids=trace_ids,
        limit=limit,
    )
    return batch.__dict__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.evaluation.cli",
        description="ChipWise Enterprise RAG evaluation CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run a batch evaluation")
    src_group = run.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "--golden", action="store_true",
        help="Replay the full golden QA set through the agent",
    )
    src_group.add_argument(
        "--traces", action="store_true",
        help="Replay recent trace_ids (judges existing answers, no agent rerun)",
    )
    run.add_argument(
        "--judge", choices=["router", "primary"], default="router",
        help="Which LM Studio model judges (default: router = qwen3-1.7b)",
    )
    run.add_argument(
        "--limit", type=int, default=100,
        help="Max samples for --traces (--golden runs full set)",
    )
    run.add_argument(
        "--trace-ids", nargs="*", default=None,
        help="Specific trace_ids (--traces only); overrides --limit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _build_parser().parse_args(argv)

    if args.cmd != "run":
        return 1

    if args.golden:
        result = asyncio.run(_run_golden(args.judge, args.limit))
    else:
        result = asyncio.run(
            _run_traces(args.judge, args.limit, args.trace_ids)
        )
    json.dump(result, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
