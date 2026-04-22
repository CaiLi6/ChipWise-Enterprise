"""Online sampling hook — fire-and-forget evaluation after a query.

Called from ``src/api/routers/query.py`` right after ``trace.flush()``. Uses
``asyncio.create_task`` so the response isn't blocked on judge latency.
Respects a sample rate (config.evaluation.online_sample_rate) and a hard
concurrency cap via a module-level semaphore so LM Studio isn't overloaded.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from src.evaluation.runner import DEFAULT_ONLINE_METRICS, evaluate_and_store

logger = logging.getLogger(__name__)

# Cap on concurrent online evals. Router 1.7B can handle ~4 in parallel on the
# test box; leave headroom for user queries.
_MAX_PARALLEL = 2
_sem: asyncio.Semaphore | None = None


def _get_sem() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(_MAX_PARALLEL)
    return _sem


async def _run_one(
    sample: dict[str, Any],
    judge_llm: Any,
    judge_model_name: str,
    metrics: tuple[str, ...],
) -> None:
    sem = _get_sem()
    async with sem:
        try:
            await evaluate_and_store(
                sample,
                judge_llm,
                metrics=metrics,
                judge_model_name=judge_model_name,
                mode="online_sampled",
            )
            logger.info("online-eval completed trace=%s", sample.get("trace_id"))
        except Exception:  # noqa: BLE001
            logger.warning(
                "online-eval failed trace=%s", sample.get("trace_id"), exc_info=True
            )


def maybe_evaluate(
    sample: dict[str, Any],
    judge_llm: Any,
    judge_model_name: str = "router",
    sample_rate: float = 0.1,
    metrics: tuple[str, ...] = DEFAULT_ONLINE_METRICS,
) -> asyncio.Task[Any] | None:
    """Non-blocking schedule of an evaluation with the given sample rate.

    Returns the spawned Task (for tests) or None if not sampled / no event loop.
    Failures are logged and swallowed — this must never affect the user request.
    """
    if sample_rate <= 0:
        return None
    if random.random() > sample_rate:
        return None
    if judge_llm is None:
        logger.debug("online-eval skipped: no judge LLM")
        return None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return None
    coro = _run_one(sample, judge_llm, judge_model_name, metrics)
    return loop.create_task(coro)
