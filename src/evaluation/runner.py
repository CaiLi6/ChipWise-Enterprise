"""Evaluator orchestrator — run judges + custom metrics, write record.

Exposes two entry points:

- ``evaluate_sample(sample, judge_llm, metrics)``
    Evaluate one sample dict. Returns an ``EvaluationRecord``. Doesn't write.

- ``evaluate_and_store(sample, judge_llm, metrics, mode, batch_id, meta)``
    Evaluate and append to ``logs/evaluations.jsonl``.

A "sample" is the minimal context needed to judge an answer::

    {
        "trace_id": str,
        "query": str,
        "answer": str,
        "contexts": list[str],     # textual content of retrieved chunks
        "ground_truth": str | None,
        "citations": list[dict],   # for citation_diversity
        "duration_ms": float,
        "iterations": int,
    }
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.evaluation.custom_metrics import (
    agent_efficiency,
    citation_coverage,
    citation_diversity,
    latency_score,
)
from src.evaluation.judge import (
    judge_context_precision,
    judge_context_recall,
    judge_faithfulness,
    judge_relevancy,
)
from src.evaluation.storage import EvaluationRecord, append_evaluation
from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)

DEFAULT_ONLINE_METRICS = ("faithfulness", "answer_relevancy")
DEFAULT_BATCH_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "citation_coverage",
    "latency_score",
    "citation_diversity",
    "agent_efficiency",
)
DEFAULT_GOLDEN_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "citation_coverage",
)


async def _gather_judges(
    judge_llm: BaseLLM,
    sample: dict[str, Any],
    metrics: list[str],
) -> dict[str, float | None]:
    """Run LLM-based judges in parallel, best-effort.

    Judges that return None (no parse) are recorded as None so the UI can show
    "not scored" instead of assuming 0.
    """
    q = sample.get("query", "")
    a = sample.get("answer", "")
    ctx = sample.get("contexts") or []
    gt = sample.get("ground_truth")

    coros: dict[str, Any] = {}
    if "faithfulness" in metrics:
        coros["faithfulness"] = judge_faithfulness(judge_llm, q, a, ctx)
    if "answer_relevancy" in metrics:
        coros["answer_relevancy"] = judge_relevancy(judge_llm, q, a)
    if "context_precision" in metrics:
        coros["context_precision"] = judge_context_precision(judge_llm, q, ctx)
    if "context_recall" in metrics and gt:
        coros["context_recall"] = judge_context_recall(judge_llm, q, ctx, gt)

    if not coros:
        return {}

    keys = list(coros.keys())
    results = await asyncio.gather(*[coros[k] for k in keys], return_exceptions=True)
    out: dict[str, float | None] = {}
    for k, r in zip(keys, results, strict=True):
        if isinstance(r, BaseException):
            logger.warning("judge %s raised: %s", k, r)
            out[k] = None
        else:
            out[k] = r.score
    return out


def _custom_metrics(sample: dict[str, Any], metrics: list[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    if "citation_coverage" in metrics:
        out["citation_coverage"] = citation_coverage(
            sample.get("answer", ""), sample.get("contexts") or []
        )
    if "latency_score" in metrics:
        out["latency_score"] = latency_score(sample.get("duration_ms", 0) or 0)
    if "citation_diversity" in metrics:
        out["citation_diversity"] = citation_diversity(sample.get("citations") or [])
    if "agent_efficiency" in metrics:
        out["agent_efficiency"] = agent_efficiency(sample.get("iterations", 1) or 1)
    return out


async def evaluate_sample(
    sample: dict[str, Any],
    judge_llm: BaseLLM,
    metrics: tuple[str, ...] | list[str] = DEFAULT_ONLINE_METRICS,
    judge_model_name: str = "",
) -> EvaluationRecord:
    """Evaluate a single sample, return the record (not written)."""
    started = time.time()
    metric_list = list(metrics)
    # LLM judges in parallel
    judge_scores = await _gather_judges(judge_llm, sample, metric_list)
    # Deterministic metrics
    custom_scores = _custom_metrics(sample, metric_list)
    merged: dict[str, float | None] = {**judge_scores, **custom_scores}

    rec = EvaluationRecord(
        trace_id=sample.get("trace_id", ""),
        query=sample.get("query", "")[:500],
        answer=sample.get("answer", "")[:2000],
        contexts=[(c or "")[:2000] for c in (sample.get("contexts") or [])],
        ground_truth=sample.get("ground_truth"),
        metrics=merged,
        judge_model=judge_model_name,
        duration_ms_eval=round((time.time() - started) * 1000, 2),
        meta={
            "citation_count": len(sample.get("citations") or []),
            "iterations": sample.get("iterations"),
            "duration_ms_query": sample.get("duration_ms"),
        },
    )
    return rec


async def evaluate_and_store(
    sample: dict[str, Any],
    judge_llm: BaseLLM,
    metrics: tuple[str, ...] | list[str] = DEFAULT_ONLINE_METRICS,
    judge_model_name: str = "",
    mode: str = "online_sampled",
    batch_id: str | None = None,
    meta_extra: dict[str, Any] | None = None,
) -> EvaluationRecord:
    rec = await evaluate_sample(sample, judge_llm, metrics, judge_model_name)
    rec.mode = mode
    rec.batch_id = batch_id
    if meta_extra:
        rec.meta.update(meta_extra)
    append_evaluation(rec)
    return rec
