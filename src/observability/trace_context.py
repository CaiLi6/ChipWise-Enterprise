"""TraceContext — per-request trace recording (§4.8.1).

Every HTTP request gets a unique ``trace_id``. Each processing stage
calls ``trace.record_stage(stage_name, metadata)`` to log its progress.
Traces are written to ``logs/traces.jsonl``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TRACE_DIR = Path("logs")


@dataclass
class StageRecord:
    """A single recorded stage within a trace."""
    stage: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None


class TraceContext:
    """Accumulates stage records for a single request.

    Usage::

        trace = TraceContext()
        trace.record_stage("retrieval", {"top_k": 10, "hits": 7})
        trace.record_stage("rerank", {"reranked": 5})
        trace.flush()          # writes to logs/traces.jsonl
    """

    def __init__(
        self,
        trace_id: str | None = None,
        trace_dir: Path | str = _DEFAULT_TRACE_DIR,
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self._trace_dir = Path(trace_dir)
        self._stages: list[StageRecord] = []
        self._start = time.time()

    def record_stage(self, stage: str, metadata: dict[str, Any] | None = None) -> None:
        """Append a stage record to the trace."""
        record = StageRecord(
            stage=stage,
            metadata=metadata or {},
            timestamp=time.time(),
        )
        self._stages.append(record)

    @property
    def stages(self) -> list[StageRecord]:
        return list(self._stages)

    def to_dict(self) -> dict[str, Any]:
        elapsed = time.time() - self._start
        return {
            "trace_id": self.trace_id,
            "total_duration_ms": round(elapsed * 1000, 2),
            "stages": [
                {
                    "stage": s.stage,
                    "metadata": s.metadata,
                    "timestamp": s.timestamp,
                }
                for s in self._stages
            ],
        }

    def flush(self) -> None:
        """Write the trace to ``logs/traces.jsonl``."""
        try:
            self._trace_dir.mkdir(parents=True, exist_ok=True)
            path = self._trace_dir / "traces.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("Failed to flush trace %s", self.trace_id, exc_info=True)
