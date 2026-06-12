"""Speed + memory measurement helpers (executed inside each model subprocess).

Memory is reported with several complementary numbers because no single figure
is fair on its own: cold-load vs steady-state vs peak-encode, RSS vs PSS, plus
on-disk weight size and GPU allocation when present.
"""

from __future__ import annotations

import contextlib
import gc
import logging
import os
import resource
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── memory ──────────────────────────────────────────────────────────────────
def _rss_mb(proc: Any) -> float:
    return proc.memory_info().rss / (1024 * 1024)


def _pss_mb() -> float | None:
    """Proportional Set Size from /proc/self/smaps_rollup (Linux only)."""
    try:
        for line in Path("/proc/self/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                return float(line.split()[1]) / 1024.0
    except Exception:  # noqa: BLE001
        return None
    return None


class MemorySampler:
    """Background thread that tracks peak RSS (self + children) while active."""

    def __init__(self, interval: float = 0.05) -> None:
        import psutil

        self._proc = psutil.Process(os.getpid())
        self._interval = interval
        self._peak = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> float:
        import psutil

        total = self._proc.memory_info().rss
        for child in self._proc.children(recursive=True):
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                total += child.memory_info().rss
        return total / (1024 * 1024)

    def __enter__(self) -> MemorySampler:
        self._peak = self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._peak = max(self._peak, self._sample())

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    @property
    def peak_mb(self) -> float:
        return round(self._peak, 1)


def disk_weight_mb(hf_id: str) -> float | None:
    """On-disk size of the *loaded* model weights (safetensors / pytorch bin).

    Sums only the weight files actually used, ignoring onnx/openvino/ggml export
    variants that bloat some repos (e.g. e5-large ships ~9 GB of extra formats).
    Falls back to the full snapshot size if no weight file is found.
    """
    try:
        from huggingface_hub import snapshot_download

        snap = Path(snapshot_download(hf_id, local_files_only=True))
        all_files = [
            p for p in snap.rglob("*")
            if p.is_file() and "onnx" not in p.parts and "openvino" not in p.parts
        ]
        # Prefer safetensors; fall back to .bin only when no safetensors exist
        # (some repos ship both formats — counting both double-counts the weights).
        safet = [p for p in all_files if p.suffix == ".safetensors"]
        weight_files = safet or [p for p in all_files if p.suffix == ".bin"]
        if weight_files:
            return round(sum(p.stat().st_size for p in weight_files) / (1024 * 1024), 1)
        total = sum(p.stat().st_size for p in all_files)
        return round(total / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        return None


def gpu_peak_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        return None
    return None


@dataclass
class MemoryReport:
    baseline_rss_mb: float = 0.0
    post_load_rss_mb: float = 0.0
    load_delta_mb: float = 0.0
    peak_encode_rss_mb: float = 0.0
    pss_mb: float | None = None
    ru_maxrss_mb: float = 0.0
    gpu_peak_mb: float | None = None
    disk_weight_mb: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ── speed ─────────────────────────────────────────────────────────────────
@dataclass
class SpeedReport:
    query_latency_p50_ms: float = 0.0
    query_latency_p95_ms: float = 0.0
    query_latency_mean_ms: float = 0.0
    throughput: dict[int, float] = field(default_factory=dict)  # batch_size -> texts/sec
    corpus_encode_sec: float = 0.0
    corpus_texts_per_sec: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "query_latency_p50_ms": round(self.query_latency_p50_ms, 2),
            "query_latency_p95_ms": round(self.query_latency_p95_ms, 2),
            "query_latency_mean_ms": round(self.query_latency_mean_ms, 2),
            "throughput_texts_per_sec": {str(b): round(v, 1) for b, v in self.throughput.items()},
            "corpus_encode_sec": round(self.corpus_encode_sec, 2),
            "corpus_texts_per_sec": round(self.corpus_texts_per_sec, 1),
        }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(int(pct * len(sorted_vals)), len(sorted_vals) - 1)
    return sorted_vals[idx]


def measure_query_latency(
    encode_one: Callable[[list[str]], Any],
    queries: list[str],
    warmup: int = 3,
    reps: int = 3,
) -> tuple[float, float, float]:
    """Single-query (batch=1) latency p50/p95/mean in ms over reps × queries."""
    for q in queries[:warmup]:
        encode_one([q])
    samples: list[float] = []
    for _ in range(reps):
        for q in queries:
            t0 = time.perf_counter()
            encode_one([q])
            samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    mean = sum(samples) / len(samples) if samples else 0.0
    return _percentile(samples, 0.50), _percentile(samples, 0.95), mean


def measure_throughput(
    encode_batch: Callable[[list[str]], Any],
    texts: list[str],
    batch_sizes: tuple[int, ...] = (1, 8, 32, 64),
    warmup: int = 1,
    reps: int = 3,
) -> dict[int, float]:
    """texts/sec at each batch size (best of *reps*, after warmup)."""
    out: dict[int, float] = {}
    for bs in batch_sizes:
        batch = (texts * ((bs // max(len(texts), 1)) + 1))[:bs]
        for _ in range(warmup):
            encode_batch(batch)
        best = 0.0
        for _ in range(reps):
            t0 = time.perf_counter()
            encode_batch(batch)
            dt = time.perf_counter() - t0
            if dt > 0:
                best = max(best, bs / dt)
        out[bs] = best
    return out


def ru_maxrss_mb() -> float:
    """Peak RSS of this process via getrusage (KB on Linux, bytes on macOS)."""
    val = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes; assume KB (the project targets Linux).
    return round(val / 1024.0, 1)


def free_caches() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass
