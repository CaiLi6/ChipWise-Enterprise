"""Append-only JSONL storage for evaluation records + batch runs.

Two files:
- ``logs/evaluations.jsonl``    — one line per (trace_id, metric_set) eval
- ``logs/eval_batches.jsonl``   — one line per batch run metadata
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVAL_FILE = Path("logs/evaluations.jsonl")
BATCH_FILE = Path("logs/eval_batches.jsonl")

_MAX_SCAN = 20000
_write_lock = threading.Lock()


@dataclass
class EvaluationRecord:
    """One evaluation row (one trace × one judge run)."""

    eval_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = ""
    query: str = ""
    answer: str = ""
    contexts: list[str] = field(default_factory=list)
    ground_truth: str | None = None
    metrics: dict[str, float | None] = field(default_factory=dict)
    judge_model: str = ""
    mode: str = "online_sampled"  # online_sampled | offline_batch | golden
    batch_id: str | None = None
    evaluated_at: float = field(default_factory=time.time)
    duration_ms_eval: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchRun:
    """One batch run — aggregate stats for a group of samples."""

    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    n_total: int = 0
    n_done: int = 0
    n_failed: int = 0
    judge_model: str = ""
    mode: str = "offline_batch"
    target: dict[str, Any] = field(default_factory=dict)
    aggregate: dict[str, float] = field(default_factory=dict)
    status: str = "running"  # running | succeeded | failed | cancelled
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _ensure_dir() -> None:
    EVAL_FILE.parent.mkdir(parents=True, exist_ok=True)


def append_evaluation(rec: EvaluationRecord) -> None:
    _ensure_dir()
    line = json.dumps(rec.to_json(), ensure_ascii=False) + "\n"
    with _write_lock, EVAL_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def load_evaluations(
    limit: int = _MAX_SCAN,
    since: float | None = None,
    until: float | None = None,
    trace_id: str | None = None,
    batch_id: str | None = None,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    if not EVAL_FILE.exists():
        return []
    tail: deque[str] = deque(maxlen=limit)
    with EVAL_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            tail.append(line)
    out: list[dict[str, Any]] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since is not None and rec.get("evaluated_at", 0) < since:
            continue
        if until is not None and rec.get("evaluated_at", 0) > until:
            continue
        if trace_id is not None and rec.get("trace_id") != trace_id:
            continue
        if batch_id is not None and rec.get("batch_id") != batch_id:
            continue
        if mode is not None and rec.get("mode") != mode:
            continue
        out.append(rec)
    return out


def append_batch(rec: BatchRun) -> None:
    _ensure_dir()
    line = json.dumps(rec.to_json(), ensure_ascii=False) + "\n"
    with _write_lock, BATCH_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def update_batch(batch_id: str, updates: dict[str, Any]) -> None:
    """Overwrite a batch record by rewriting the file — rare operation.

    Append-only files + occasional rewrite is the simplest way to reflect
    batch progress without a DB. Batches are append-ish: we rewrite only
    when a batch transitions state, which is 3-5 times per batch at most.
    """
    if not BATCH_FILE.exists():
        return
    rows: list[dict[str, Any]] = []
    with BATCH_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("batch_id") == batch_id:
                rec.update(updates)
            rows.append(rec)
    with _write_lock:
        tmp = BATCH_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(BATCH_FILE)


def load_batches(limit: int = 200) -> list[dict[str, Any]]:
    if not BATCH_FILE.exists():
        return []
    tail: deque[str] = deque(maxlen=limit)
    with BATCH_FILE.open("r", encoding="utf-8") as f:
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


def get_batch(batch_id: str) -> dict[str, Any] | None:
    for b in reversed(load_batches(limit=_MAX_SCAN)):
        if b.get("batch_id") == batch_id:
            return b
    return None
