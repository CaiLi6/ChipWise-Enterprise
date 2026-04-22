"""Evaluation API router — dashboard + batch runs + outliers + compare.

Endpoints:
- GET  /api/v1/evaluations/summary     — windowed KPI cards
- GET  /api/v1/evaluations/aggregate   — time-series (for line charts)
- GET  /api/v1/evaluations/distribution — histogram for a metric
- GET  /api/v1/evaluations/compare     — A/B compare two time windows
- GET  /api/v1/evaluations/outliers    — records below/above a threshold
- GET  /api/v1/evaluations/by_trace/{id} — all evals for one trace
- GET  /api/v1/evaluations/runs        — list recent batches
- GET  /api/v1/evaluations/runs/{id}   — single batch with samples
- POST /api/v1/evaluations/run         — trigger a batch run
- POST /api/v1/evaluations/cleanup     — truncate eval log (admin)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from src.evaluation import aggregator
from src.evaluation.batch_runner import run_batch_from_traces, run_batch_on_golden
from src.evaluation.runner import DEFAULT_BATCH_METRICS, DEFAULT_GOLDEN_METRICS
from src.evaluation.storage import (
    EVAL_FILE,
    get_batch,
    load_batches,
    load_evaluations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


def _load_recent(limit: int = 20000, **filters: Any) -> list[dict[str, Any]]:
    return load_evaluations(limit=limit, **filters)


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def eval_summary() -> dict[str, Any]:
    """Windowed KPIs (24h / 7d / 30d) + 7d-vs-prev-7d trend delta."""
    records = _load_recent()
    return {
        "total": len(records),
        "windows": aggregator.windowed_summary(records),
        "trend_7d_delta": aggregator.trend_delta(records, window_sec=7 * 86400),
        "last_evaluated_at": max(
            (r.get("evaluated_at", 0) for r in records), default=0
        ),
    }


@router.get("/aggregate")
async def eval_aggregate(
    bucket_sec: int = Query(3600, ge=60, le=86400 * 7),
    window_sec: int = Query(7 * 86400, ge=3600, le=90 * 86400),
    mode: str | None = Query(None, description="online_sampled | offline_batch | golden"),
) -> dict[str, Any]:
    """Per-metric time series for the given window, bucketed."""
    now = time.time()
    since = now - window_sec
    records = _load_recent(since=since, mode=mode)
    series = aggregator.time_series(records, bucket_sec=bucket_sec, since=since, until=now)
    return {
        "bucket_sec": bucket_sec,
        "window_sec": window_sec,
        "series": series,
        "n": len(records),
    }


@router.get("/distribution")
async def eval_distribution(
    metric: str = Query(..., description="faithfulness, answer_relevancy, ..."),
    window_sec: int = Query(7 * 86400, ge=3600, le=90 * 86400),
    bins: int = Query(20, ge=5, le=50),
    mode: str | None = None,
) -> dict[str, Any]:
    if metric not in aggregator.METRIC_NAMES:
        raise HTTPException(400, f"unknown metric {metric}")
    since = time.time() - window_sec
    records = _load_recent(since=since, mode=mode)
    return aggregator.histogram(records, metric=metric, bins=bins)


@router.get("/compare")
async def eval_compare(
    a_from: float = Query(...),
    a_to: float = Query(...),
    b_from: float = Query(...),
    b_to: float = Query(...),
    mode: str | None = None,
) -> dict[str, Any]:
    records = _load_recent(mode=mode)
    ra = [r for r in records if a_from <= r.get("evaluated_at", 0) <= a_to]
    rb = [r for r in records if b_from <= r.get("evaluated_at", 0) <= b_to]
    return {
        "window_a": {"from": a_from, "to": a_to, "n": len(ra)},
        "window_b": {"from": b_from, "to": b_to, "n": len(rb)},
        "metrics": aggregator.compare(ra, rb),
    }


@router.get("/outliers")
async def eval_outliers(
    metric: str = Query(...),
    lt: float | None = None,
    gt: float | None = None,
    window_sec: int = Query(7 * 86400, ge=3600, le=90 * 86400),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    if metric not in aggregator.METRIC_NAMES:
        raise HTTPException(400, f"unknown metric {metric}")
    since = time.time() - window_sec
    records = _load_recent(since=since)
    rows = aggregator.outliers(records, metric=metric, lt=lt, gt=gt, limit=limit)
    return {"metric": metric, "lt": lt, "gt": gt, "n": len(rows), "rows": rows}


@router.get("/by_trace/{trace_id}")
async def eval_by_trace(trace_id: str) -> dict[str, Any]:
    records = _load_recent(trace_id=trace_id)
    if not records:
        return {"trace_id": trace_id, "evaluations": []}
    return {"trace_id": trace_id, "evaluations": records}


@router.get("/recent")
async def eval_recent(
    limit: int = Query(100, ge=1, le=500),
    mode: str | None = None,
) -> dict[str, Any]:
    records = _load_recent(mode=mode)
    records.sort(key=lambda r: r.get("evaluated_at", 0), reverse=True)
    return {"total": len(records), "rows": records[:limit]}


# ---------------------------------------------------------------------------
# Batch run endpoints
# ---------------------------------------------------------------------------


@router.get("/runs")
async def list_runs(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    rows = load_batches(limit=limit)
    rows.sort(key=lambda r: r.get("started_at", 0), reverse=True)
    return {"total": len(rows), "runs": rows[:limit]}


@router.get("/runs/{batch_id}")
async def get_run(batch_id: str) -> dict[str, Any]:
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(404, f"batch {batch_id} not found")
    records = _load_recent(batch_id=batch_id)
    return {"batch": batch, "n_samples": len(records), "samples": records}


class BatchRunRequest(BaseModel):
    kind: str = Field("traces", description="traces | golden")
    judge: str = Field("primary", description="primary | router")
    trace_ids: list[str] | None = None
    since: float | None = None
    until: float | None = None
    limit: int = 50
    metrics: list[str] | None = None
    concurrency: int = Field(1, ge=1, le=4)


# In-memory lookup of currently running batch tasks. Keyed by batch_id — we
# need this so /runs/{id}/status can report whether the task is alive.
_running_tasks: dict[str, asyncio.Task[Any]] = {}


async def _resolve_judge(kind: str) -> tuple[Any, str]:
    """Create an LM Studio LLM for the judge role and return (llm, name)."""
    from src.core.settings import load_settings
    from src.libs.llm.factory import LLMFactory

    settings = load_settings()
    cfg = settings.model_dump()
    role = "primary" if kind == "primary" else "router"
    llm = LLMFactory.create(cfg, role=role)
    model_name = cfg.get("llm", {}).get(role, {}).get("model", role)
    return llm, model_name


async def _resolve_orchestrator() -> Any:
    """Import lazily so evaluations router has no hard dep on query router."""
    from src.api.routers.query import _get_or_create_orchestrator

    return _get_or_create_orchestrator()


@router.post("/run")
async def trigger_run(req: BatchRunRequest = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Kick off a batch run as a background asyncio task. Returns immediately."""
    judge_llm, judge_name = await _resolve_judge(req.judge)
    if judge_llm is None:
        raise HTTPException(503, "judge LLM unavailable")

    metrics = tuple(req.metrics) if req.metrics else None

    async def _bg() -> None:
        try:
            if req.kind == "golden":
                orch = await _resolve_orchestrator()
                if orch is None:
                    logger.error("golden batch aborted: orchestrator unavailable")
                    return
                await run_batch_on_golden(
                    judge_llm,
                    orch,
                    judge_model_name=judge_name,
                    metrics=metrics or DEFAULT_GOLDEN_METRICS,
                    concurrency=req.concurrency,
                )
            else:
                await run_batch_from_traces(
                    judge_llm,
                    judge_model_name=judge_name,
                    trace_ids=req.trace_ids,
                    since=req.since,
                    until=req.until,
                    limit=req.limit,
                    metrics=metrics or DEFAULT_BATCH_METRICS,
                    concurrency=req.concurrency,
                )
        except Exception:  # noqa: BLE001
            logger.exception("batch run failed")

    task = asyncio.create_task(_bg())

    # Peek at the just-appended batch id by reading the tail of the batch log.
    # The runner appends a BatchRun *before* starting samples, so by the time
    # the task is scheduled the file has a row we can read back.
    await asyncio.sleep(0.05)
    batches = load_batches(limit=5)
    latest = batches[-1] if batches else None
    batch_id = latest.get("batch_id") if latest else None
    if batch_id:
        _running_tasks[batch_id] = task
    return {"batch_id": batch_id, "started": True, "judge": judge_name, "kind": req.kind}


@router.post("/cleanup")
async def cleanup_evals(
    confirm: bool = Query(False, description="Must be True"),
) -> dict[str, Any]:
    """Truncate the evaluation log. Dev-only."""
    if not confirm:
        raise HTTPException(400, "set confirm=true")
    if EVAL_FILE.exists():
        EVAL_FILE.unlink()
    return {"ok": True, "cleared": str(EVAL_FILE)}
