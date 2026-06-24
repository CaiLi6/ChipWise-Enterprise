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
    role = "router" if judge == "router" else "primary"
    cfg = settings.llm.router if role == "router" else settings.llm.primary
    llm = LLMFactory.create(settings.model_dump(), role=role)
    return llm, cfg.model


async def _run_golden(judge: str, limit: int | None) -> dict[str, Any]:
    from src.api.routers.query import _get_or_create_orchestrator
    from src.evaluation.batch_runner import run_batch_on_golden

    judge_llm, judge_name = _resolve_judge_llm(judge)
    orch = _get_or_create_orchestrator()
    if orch is None:
        raise RuntimeError(
            "Orchestrator unavailable — LM Studio / Milvus / embedding service must be reachable",
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
    graph = sub.add_parser("graph", help="Run deterministic GraphRAG evaluation")
    graph.add_argument(
        "--limit-per-type", type=int, default=20,
        help="Golden cases to build per graph case type (default: 20)",
    )
    graph.add_argument(
        "--output", default="reports/eval/graphrag_eval_latest.json",
        help="Output JSON report path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _build_parser().parse_args(argv)

    if args.cmd == "graph":
        result = asyncio.run(_run_graph(args.limit_per_type, args.output))
        json.dump(result, sys.stdout, indent=2, default=str, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

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


async def _run_graph(limit_per_type: int, output: str) -> dict[str, Any]:
    """Run deterministic GraphRAG evaluation against PG source + Kùzu graph."""
    import asyncpg  # type: ignore[import-untyped,import-not-found]

    from src.api.dependencies import get_settings
    from src.evaluation.graphrag import run_graphrag_evaluation, write_report
    from src.libs.graph_store.kuzu_store import KuzuGraphStore

    settings = get_settings()
    db = settings.database
    pool = await asyncpg.create_pool(
        host=db.host,
        port=db.port,
        database=db.database,
        user=db.user,
        password=db.password,
        min_size=1,
        max_size=2,
    )
    graph = KuzuGraphStore(settings.graph_store.kuzu.db_path, read_only=True)
    try:
        result = await run_graphrag_evaluation(pool, graph, limit_per_type=limit_per_type)
        path = write_report(result, output)
        payload = result.to_dict()
        payload["output"] = str(path)
        return payload
    finally:
        await pool.close()
        graph.close()


if __name__ == "__main__":
    sys.exit(main())
