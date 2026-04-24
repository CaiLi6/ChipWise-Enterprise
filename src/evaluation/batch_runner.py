"""Batch evaluation runner — run judges over a group of samples.

Two sample sources:
- from ``logs/traces.jsonl`` — replay recent real queries
- from ``data/golden_qa.jsonl`` — re-run agent on golden questions, score with ground_truth

Both return a ``BatchRun`` and append each sample to ``evaluations.jsonl``.
The batch itself is tracked in ``logs/eval_batches.jsonl``; we update it via
``update_batch(batch_id, {...})`` as progress advances.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from collections import deque
from pathlib import Path
from typing import Any

from src.evaluation.aggregator import METRIC_NAMES
from src.evaluation.golden import list_golden
from src.evaluation.grounding import (
    RetrievalGateConfig,
    annotate_answer,
    check_grounding,
)
from src.evaluation.runner import (
    DEFAULT_BATCH_METRICS,
    DEFAULT_GOLDEN_METRICS,
    evaluate_and_store,
)
from src.evaluation.storage import BatchRun, append_batch, update_batch

logger = logging.getLogger(__name__)

TRACE_FILE = Path("logs/traces.jsonl")

# Concurrency — primary 35B is slow, do one at a time
_DEFAULT_CONCURRENCY = 1


# ---------------------------------------------------------------------------
# Trace loading helpers (mirror src/api/routers/traces.py logic)
# ---------------------------------------------------------------------------


def _load_traces_tail(max_lines: int = 5000) -> list[dict[str, Any]]:
    if not TRACE_FILE.exists():
        return []
    tail: deque[str] = deque(maxlen=max_lines)
    with TRACE_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            tail.append(line)
    out: list[dict[str, Any]] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _sample_from_trace(trace: dict[str, Any]) -> dict[str, Any] | None:
    stages = trace.get("stages") or []
    request_stage = next((s for s in stages if s.get("stage") == "request"), None)
    response_stage = next((s for s in stages if s.get("stage") == "response"), None)
    if not request_stage or not response_stage:
        return None

    q = request_stage.get("metadata", {}).get("query", "")
    rmeta = response_stage.get("metadata", {})
    answer = rmeta.get("answer", "") or ""
    citations_preview = rmeta.get("citations_preview") or []

    contexts: list[str] = []
    for c in citations_preview:
        content = c.get("content") or c.get("source") or ""
        if content and isinstance(content, str):
            contexts.append(content)

    return {
        "trace_id": trace.get("trace_id"),
        "query": q,
        "answer": answer,
        "contexts": contexts,
        "ground_truth": None,
        "citations": citations_preview,
        "duration_ms": trace.get("total_duration_ms"),
        "iterations": rmeta.get("iterations"),
    }


# ---------------------------------------------------------------------------
# Core batch runner
# ---------------------------------------------------------------------------


async def _run_one_sample(
    sample: dict[str, Any],
    judge_llm: Any,
    judge_model_name: str,
    metrics: tuple[str, ...],
    mode: str,
    batch_id: str,
) -> str | None:
    try:
        await evaluate_and_store(
            sample,
            judge_llm,
            metrics=metrics,
            judge_model_name=judge_model_name,
            mode=mode,
            batch_id=batch_id,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("batch eval failed trace=%s: %s", sample.get("trace_id"), exc)
        return str(exc)[:400]


async def _run_samples(
    samples: list[dict[str, Any]],
    judge_llm: Any,
    judge_model_name: str,
    metrics: tuple[str, ...],
    mode: str,
    batch: BatchRun,
    concurrency: int,
) -> BatchRun:
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(s: dict[str, Any]) -> str | None:
        async with sem:
            return await _run_one_sample(s, judge_llm, judge_model_name, metrics, mode, batch.batch_id)

    tasks = [asyncio.create_task(_bounded(s)) for s in samples]
    done = 0
    failed = 0
    for coro in asyncio.as_completed(tasks):
        err = await coro
        done += 1
        if err is not None:
            failed += 1
        if done % 3 == 0 or done == len(tasks):
            update_batch(batch.batch_id, {"n_done": done, "n_failed": failed})

    # Aggregate
    from src.evaluation.storage import load_evaluations

    evals = load_evaluations(batch_id=batch.batch_id)
    agg: dict[str, float] = {}
    for m in METRIC_NAMES:
        vals = [
            (r.get("metrics") or {}).get(m)
            for r in evals
            if isinstance((r.get("metrics") or {}).get(m), int | float)
        ]
        if vals:
            agg[m + "_mean"] = round(statistics.fmean(vals), 4)  # type: ignore[arg-type]
            agg[m + "_n"] = len(vals)

    batch.completed_at = time.time()
    batch.n_done = done
    batch.n_failed = failed
    batch.aggregate = agg
    batch.status = "succeeded" if failed < len(samples) else "failed"
    update_batch(batch.batch_id, {
        "completed_at": batch.completed_at,
        "n_done": batch.n_done,
        "n_failed": batch.n_failed,
        "aggregate": batch.aggregate,
        "status": batch.status,
    })
    return batch


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def run_batch_from_traces(
    judge_llm: Any,
    judge_model_name: str,
    trace_ids: list[str] | None = None,
    since: float | None = None,
    until: float | None = None,
    limit: int = 50,
    metrics: tuple[str, ...] = DEFAULT_BATCH_METRICS,
    concurrency: int = _DEFAULT_CONCURRENCY,
) -> BatchRun:
    """Run evaluations for a set of traces (by id list or time window)."""
    all_traces = _load_traces_tail(max_lines=10000)
    if trace_ids:
        id_set = set(trace_ids)
        traces = [t for t in all_traces if t.get("trace_id") in id_set]
    else:
        traces = all_traces
        if since is not None:
            traces = [
                t
                for t in traces
                if (t.get("stages") or [{}])[0].get("timestamp", 0) >= since
            ]
        if until is not None:
            traces = [
                t
                for t in traces
                if (t.get("stages") or [{}])[0].get("timestamp", 0) <= until
            ]
    traces = traces[-limit:]
    samples = [s for t in traces if (s := _sample_from_trace(t)) is not None]

    batch = BatchRun(
        judge_model=judge_model_name,
        mode="offline_batch",
        n_total=len(samples),
        target={
            "kind": "trace_ids" if trace_ids else "time_range",
            "ids": trace_ids,
            "since": since,
            "until": until,
            "limit": limit,
        },
    )
    append_batch(batch)
    return await _run_samples(
        samples, judge_llm, judge_model_name, metrics, "offline_batch", batch, concurrency
    )


def _build_grounding_config_standalone() -> RetrievalGateConfig | None:
    """Mirror src/api/routers/query.py::_build_grounding_config but without a Request."""
    try:
        from src.api.dependencies import get_settings

        dumped = get_settings().model_dump()
        cfg = dumped.get("grounding") or {}
        if not cfg.get("enabled", True):
            return None
        return RetrievalGateConfig(
            enabled=True,
            min_citations=int(cfg.get("min_citations", 2)),
            min_top_score=float(cfg.get("min_top_score", 0.35)),
            min_mean_score=float(cfg.get("min_mean_score", 0.25)),
            max_unsupported_ratio=float(cfg.get("max_unsupported_ratio", 0.40)),
            numeric_abstain_mode=str(cfg.get("numeric_abstain_mode", "warn")),
        )
    except Exception:  # noqa: BLE001
        logger.debug("grounding config load failed; batch will use defaults", exc_info=True)
        return RetrievalGateConfig()


async def run_batch_on_golden(
    judge_llm: Any,
    orchestrator: Any,
    judge_model_name: str,
    metrics: tuple[str, ...] = DEFAULT_GOLDEN_METRICS,
    concurrency: int = _DEFAULT_CONCURRENCY,
) -> BatchRun:
    """Replay the golden set through the agent, then score with ground_truth.

    Mirrors the HTTP /query path: after ``orchestrator.run()`` we run the same
    grounding gate + annotate_answer that the API applies, so batch metrics
    reflect what real users actually see (abstain template instead of empty
    string, etc.) rather than raw agent output.
    """
    golden = list_golden()
    batch = BatchRun(
        judge_model=judge_model_name,
        mode="golden",
        n_total=len(golden),
        target={"kind": "golden", "n": len(golden)},
    )
    append_batch(batch)

    from src.observability.trace_context import TraceContext

    grounding_cfg = _build_grounding_config_standalone()

    samples: list[dict[str, Any]] = []
    for g in golden:
        trace = TraceContext()
        try:
            result = await orchestrator.run(query=g["question"], trace=trace)
        except Exception as exc:  # noqa: BLE001
            logger.warning("golden orchestrator failed: %s", exc)
            continue

        contexts: list[str] = []
        citations: list[dict[str, Any]] = []
        for step in getattr(result, "tool_calls_log", []):
            for obs in getattr(step, "observations", []):
                if not isinstance(obs, dict):
                    continue
                for r in obs.get("results", []) or []:
                    if isinstance(r, dict) and r.get("content"):
                        contexts.append(r["content"])
                        citations.append({
                            "chunk_id": r.get("chunk_id"),
                            "content": r.get("content", ""),
                            "source": (r.get("metadata") or {}).get("part_number") or r.get("source"),
                            "page": r.get("page_number"),
                            "score": r.get("score"),
                        })

        raw_answer = result.answer or ""
        answer = raw_answer
        grounding_meta: dict[str, Any] = {"enabled": False}
        if grounding_cfg is not None:
            try:
                report = check_grounding(
                    raw_answer,
                    citations,
                    config=grounding_cfg,
                    stopped_reason=getattr(result, "stopped_reason", None),
                )
                answer = annotate_answer(raw_answer, report)
                grounding_meta = {
                    "enabled": True,
                    "abstained": report.abstain,
                    "reason": report.reason,
                    "coverage": round(report.coverage, 3),
                    "total": report.total,
                    "retrieval_score": round(report.retrieval_score, 3),
                    "retrieval_mean": round(report.retrieval_mean, 3),
                    "stopped_reason": getattr(result, "stopped_reason", None),
                }
                trace.record_stage("grounding", grounding_meta)
            except Exception:  # noqa: BLE001
                logger.warning("grounding check failed in golden batch", exc_info=True)

        samples.append({
            "trace_id": trace.trace_id,
            "query": g["question"],
            "answer": answer,
            "raw_answer": raw_answer,
            "contexts": contexts,
            "ground_truth": g.get("ground_truth_answer"),
            "citations": citations,
            "duration_ms": (time.time() - trace._start) * 1000,  # noqa: SLF001
            "iterations": getattr(result, "iterations", 0),
            "golden_id": g.get("id"),
            "grounding": grounding_meta,
        })

    return await _run_samples(
        samples, judge_llm, judge_model_name, metrics, "golden", batch, concurrency
    )
