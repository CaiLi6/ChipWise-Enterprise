"""Trace viewer API — reads logs/traces.jsonl for the trace-viewer UI.

For each trace we derive:
- a short summary (query, answer preview, citation count, latency)
- a timeline of stages with per-stage durations (computed from timestamps)
- per-stage metadata (agent iterations include tool calls + thought)

Traces are written append-only by ``TraceContext.flush()``. The list endpoint
reads the tail of the file (up to MAX_SCAN_LINES lines) for cheap access.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])

TRACE_FILE = Path("logs/traces.jsonl")
MAX_SCAN_LINES = 5000


def _load_raw_traces(limit: int = 5000) -> list[dict[str, Any]]:
    if not TRACE_FILE.exists():
        return []
    # Keep only the last N lines
    tail: deque[str] = deque(maxlen=limit)
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


def _summarize(trace: dict[str, Any]) -> dict[str, Any]:
    stages = trace.get("stages") or []
    request_stage = next((s for s in stages if s.get("stage") == "request"), None)
    response_stage = next((s for s in stages if s.get("stage") == "response"), None)
    error_stage = next((s for s in stages if s.get("stage") == "error"), None)

    query = (request_stage or {}).get("metadata", {}).get("query", "")
    user = (request_stage or {}).get("metadata", {}).get("user")
    started_at = (stages[0].get("timestamp") if stages else None)

    status_val = "ok"
    answer_preview = ""
    citation_count = 0
    iterations = 0
    if response_stage:
        md = response_stage.get("metadata", {})
        answer_preview = md.get("answer", "")[:200]
        citation_count = md.get("citation_count", 0)
        iterations = md.get("iterations", 0)
    elif error_stage:
        status_val = "error"
        answer_preview = error_stage.get("metadata", {}).get("detail", "")[:200]

    return {
        "trace_id": trace.get("trace_id"),
        "status": status_val,
        "query": query,
        "user": user,
        "started_at": started_at,
        "duration_ms": trace.get("total_duration_ms"),
        "answer_preview": answer_preview,
        "citation_count": citation_count,
        "iterations": iterations,
        "stage_count": len(stages),
    }


def _compute_stage_durations(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add per-stage duration_ms based on timestamp gaps between adjacent stages."""
    out: list[dict[str, Any]] = []
    for idx, s in enumerate(stages):
        ts = s.get("timestamp")
        next_ts = stages[idx + 1]["timestamp"] if idx + 1 < len(stages) else None
        duration_ms = None
        if ts is not None and next_ts is not None:
            duration_ms = round((next_ts - ts) * 1000, 1)
        out.append({
            "index": idx,
            "stage": s.get("stage"),
            "timestamp": ts,
            "duration_ms": duration_ms,
            "metadata": s.get("metadata", {}),
        })
    return out


@router.get("")
async def list_traces(
    limit: int = Query(50, ge=1, le=500),
    q: str | None = Query(None, description="Substring match on query text"),
    status_filter: str | None = Query(None, alias="status", description="ok | error"),
) -> dict[str, Any]:
    """Return a reverse-chronological summary list of recent traces."""
    raw = _load_raw_traces(MAX_SCAN_LINES)
    summaries = [_summarize(t) for t in raw]
    summaries.reverse()  # newest first
    if q:
        ql = q.lower()
        summaries = [s for s in summaries if ql in (s.get("query") or "").lower()]
    if status_filter in ("ok", "error"):
        summaries = [s for s in summaries if s.get("status") == status_filter]
    return {"total": len(summaries), "traces": summaries[:limit]}


@router.get("/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """Return a single trace with full stage timeline."""
    raw = _load_raw_traces(MAX_SCAN_LINES)
    match = next((t for t in reversed(raw) if t.get("trace_id") == trace_id), None)
    if match is None:
        raise HTTPException(404, f"Trace {trace_id} not found in recent history")
    return {
        "trace_id": match.get("trace_id"),
        "duration_ms": match.get("total_duration_ms"),
        "summary": _summarize(match),
        "stages": _compute_stage_durations(match.get("stages") or []),
    }
