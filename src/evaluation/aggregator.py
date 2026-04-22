"""Statistical aggregation over evaluation records.

All functions are pure — they take a list of raw evaluation dicts (as written
by ``storage.append_evaluation``) and return numbers/series suitable for
dashboard rendering.
"""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict
from typing import Any

METRIC_NAMES = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "citation_coverage",
    "latency_score",
    "citation_diversity",
    "agent_efficiency",
]


def _values_for(records: list[dict[str, Any]], metric: str) -> list[float]:
    vals: list[float] = []
    for r in records:
        v = (r.get("metrics") or {}).get(metric)
        if isinstance(v, int | float) and v is not None and not math.isnan(v):
            vals.append(float(v))
    return vals


def summary(records: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Per-metric summary: count, mean, median, p10, p90, stdev."""
    out: dict[str, dict[str, float | int]] = {}
    for m in METRIC_NAMES:
        vals = _values_for(records, m)
        if not vals:
            out[m] = {"count": 0, "mean": 0.0, "median": 0.0, "p10": 0.0, "p90": 0.0, "stdev": 0.0}
            continue
        vals_sorted = sorted(vals)
        out[m] = {
            "count": len(vals),
            "mean": round(statistics.fmean(vals), 4),
            "median": round(vals_sorted[len(vals) // 2], 4),
            "p10": round(vals_sorted[max(0, int(len(vals) * 0.1))], 4),
            "p90": round(vals_sorted[min(len(vals) - 1, int(len(vals) * 0.9))], 4),
            "stdev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        }
    return out


def windowed_summary(
    records: list[dict[str, Any]],
    now: float | None = None,
    windows_sec: tuple[int, ...] = (86400, 7 * 86400, 30 * 86400),
) -> dict[str, dict[str, dict[str, float | int]]]:
    """Group records into {window: {metric: summary}} for KPI cards."""
    now = now or time.time()
    out: dict[str, dict[str, dict[str, float | int]]] = {}
    for w in windows_sec:
        key = f"{w // 86400}d" if w % 86400 == 0 else f"{w}s"
        subset = [r for r in records if r.get("evaluated_at", 0) >= now - w]
        out[key] = summary(subset)
    return out


def trend_delta(
    records: list[dict[str, Any]],
    window_sec: int = 7 * 86400,
    now: float | None = None,
) -> dict[str, float]:
    """Mean Δ between current window and previous same-sized window."""
    now = now or time.time()
    curr = [r for r in records if r.get("evaluated_at", 0) >= now - window_sec]
    prev = [
        r
        for r in records
        if now - 2 * window_sec <= r.get("evaluated_at", 0) < now - window_sec
    ]
    out: dict[str, float] = {}
    for m in METRIC_NAMES:
        cv = _values_for(curr, m)
        pv = _values_for(prev, m)
        if not cv or not pv:
            out[m] = 0.0
            continue
        out[m] = round(statistics.fmean(cv) - statistics.fmean(pv), 4)
    return out


def time_series(
    records: list[dict[str, Any]],
    bucket_sec: int = 3600,
    since: float | None = None,
    until: float | None = None,
) -> dict[str, list[dict[str, float]]]:
    """Bucket records by time → per-metric mean series.

    Returns ``{metric: [{"ts": bucket_start, "value": mean, "n": count}, ...]}``
    sorted by ``ts`` ascending.
    """
    if not records:
        return {m: [] for m in METRIC_NAMES}
    if since is None:
        since = min(r.get("evaluated_at", 0) for r in records)
    if until is None:
        until = max(r.get("evaluated_at", 0) for r in records)

    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        ts = r.get("evaluated_at", 0)
        if ts < since or ts > until:
            continue
        bucket = int(ts // bucket_sec) * bucket_sec
        buckets[bucket].append(r)

    out: dict[str, list[dict[str, float]]] = {m: [] for m in METRIC_NAMES}
    for bucket in sorted(buckets.keys()):
        recs = buckets[bucket]
        for m in METRIC_NAMES:
            vals = _values_for(recs, m)
            if not vals:
                continue
            out[m].append({
                "ts": bucket,
                "value": round(statistics.fmean(vals), 4),
                "n": len(vals),
            })
    return out


def histogram(
    records: list[dict[str, Any]],
    metric: str,
    bins: int = 20,
    lo: float = 0.0,
    hi: float = 1.0,
) -> dict[str, Any]:
    """Bin metric values into ``bins`` buckets spanning [lo, hi]."""
    vals = _values_for(records, metric)
    if not vals:
        return {"metric": metric, "bins": [], "counts": [], "n": 0, "mean": 0.0}
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        idx = int((min(hi, max(lo, v)) - lo) / width)
        if idx == bins:
            idx = bins - 1
        counts[idx] += 1
    edges = [round(lo + i * width, 4) for i in range(bins + 1)]
    return {
        "metric": metric,
        "bin_edges": edges,
        "counts": counts,
        "n": len(vals),
        "mean": round(statistics.fmean(vals), 4),
        "median": round(sorted(vals)[len(vals) // 2], 4),
    }


def compare(
    records_a: list[dict[str, Any]],
    records_b: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> dict[str, dict[str, float | int]]:
    """Welch's t-test style comparison of two groups per metric.

    Returns ``{metric: {mean_a, mean_b, delta, n_a, n_b, t, p_approx}}``.
    p is approximated from |t| via a heuristic since we don't want to pull
    scipy; a proper cdf can be added later if needed.
    """
    metrics = metrics or METRIC_NAMES
    out: dict[str, dict[str, float | int]] = {}
    for m in metrics:
        va = _values_for(records_a, m)
        vb = _values_for(records_b, m)
        if len(va) < 2 or len(vb) < 2:
            out[m] = {
                "mean_a": statistics.fmean(va) if va else 0.0,
                "mean_b": statistics.fmean(vb) if vb else 0.0,
                "delta": 0.0,
                "n_a": len(va),
                "n_b": len(vb),
                "t": 0.0,
                "p_approx": 1.0,
            }
            continue
        ma, mb = statistics.fmean(va), statistics.fmean(vb)
        sa, sb = statistics.variance(va), statistics.variance(vb)
        na, nb = len(va), len(vb)
        se = math.sqrt(sa / na + sb / nb) or 1e-9
        t = (mb - ma) / se
        # Rough two-sided p — simple decay, not calibrated. Good enough for UI ranking.
        p = math.exp(-0.5 * t * t) if abs(t) < 5 else 0.0
        out[m] = {
            "mean_a": round(ma, 4),
            "mean_b": round(mb, 4),
            "delta": round(mb - ma, 4),
            "n_a": na,
            "n_b": nb,
            "t": round(t, 4),
            "p_approx": round(p, 4),
        }
    return out


def outliers(
    records: list[dict[str, Any]],
    metric: str,
    lt: float | None = None,
    gt: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Records whose metric value falls outside the given bounds."""
    out: list[dict[str, Any]] = []
    for r in records:
        v = (r.get("metrics") or {}).get(metric)
        if not isinstance(v, int | float):
            continue
        if lt is not None and v >= lt:
            continue
        if gt is not None and v <= gt:
            continue
        out.append(r)
    out.sort(key=lambda r: (r.get("metrics") or {}).get(metric, 0))
    return out[:limit]
