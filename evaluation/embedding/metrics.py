"""Retrieval accuracy metrics with graded relevance, bootstrap CIs, per-category.

A qrel maps ``chunk_id -> gain`` (0 = irrelevant, 1 = partial, 2 = relevant).
``gain > 0`` is treated as binary-relevant for Recall/Hit/MRR/MAP; nDCG uses the
graded gain. All aggregate metrics report a mean and a bootstrap 95% CI, since
the test set is small (~80–100 queries).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

K_VALUES = (1, 5, 10, 20)


# ── per-query metrics ───────────────────────────────────────────────────────
def _rels(qrel: dict[str, float]) -> set[str]:
    return {cid for cid, g in qrel.items() if g > 0}


def recall_at_k(ranked: list[str], qrel: dict[str, float], k: int) -> float:
    rel = _rels(qrel)
    if not rel:
        return float("nan")
    hit = sum(1 for cid in ranked[:k] if cid in rel)
    return hit / len(rel)


def hit_at_k(ranked: list[str], qrel: dict[str, float], k: int) -> float:
    rel = _rels(qrel)
    if not rel:
        return float("nan")
    return 1.0 if any(cid in rel for cid in ranked[:k]) else 0.0


def mrr_at_k(ranked: list[str], qrel: dict[str, float], k: int) -> float:
    rel = _rels(qrel)
    if not rel:
        return float("nan")
    for i, cid in enumerate(ranked[:k]):
        if cid in rel:
            return 1.0 / (i + 1)
    return 0.0


def average_precision(ranked: list[str], qrel: dict[str, float], k: int) -> float:
    rel = _rels(qrel)
    if not rel:
        return float("nan")
    hits = 0
    score = 0.0
    for i, cid in enumerate(ranked[:k]):
        if cid in rel:
            hits += 1
            score += hits / (i + 1)
    return score / min(len(rel), k)


def ndcg_at_k(ranked: list[str], qrel: dict[str, float], k: int) -> float:
    if not any(g > 0 for g in qrel.values()):
        return float("nan")
    dcg = 0.0
    for i, cid in enumerate(ranked[:k]):
        gain = qrel.get(cid, 0.0)
        if gain > 0:
            dcg += (2**gain - 1) / math.log2(i + 2)
    ideal_gains = sorted((g for g in qrel.values() if g > 0), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal_gains))
    return dcg / idcg if idcg > 0 else 0.0


def per_query_metrics(ranked: list[str], qrel: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in K_VALUES:
        out[f"recall@{k}"] = recall_at_k(ranked, qrel, k)
        out[f"hit@{k}"] = hit_at_k(ranked, qrel, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranked, qrel, k)
    out["mrr@10"] = mrr_at_k(ranked, qrel, 10)
    out["map@10"] = average_precision(ranked, qrel, 10)
    return out


# ── aggregation ─────────────────────────────────────────────────────────────
@dataclass
class MetricSummary:
    mean: float
    ci_low: float
    ci_high: float
    n: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mean": round(self.mean, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "n": self.n,
        }


def _bootstrap_ci(values: list[float], iters: int = 2000, seed: int = 7) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(iters):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return (means[int(0.025 * iters)], means[int(0.975 * iters)])


def aggregate(per_query: list[dict[str, float]]) -> dict[str, dict[str, float | int]]:
    """Mean + bootstrap 95% CI for every metric, ignoring NaN queries."""
    if not per_query:
        return {}
    keys = list(per_query[0].keys())
    summary: dict[str, dict[str, float | int]] = {}
    for key in keys:
        vals = [q[key] for q in per_query if not _isnan(q.get(key))]
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        lo, hi = _bootstrap_ci(vals)
        summary[key] = MetricSummary(mean, lo, hi, len(vals)).as_dict()
    return summary


def aggregate_by_category(
    per_query: list[dict[str, float]],
    categories: list[str],
    metric: str = "ndcg@10",
) -> dict[str, dict[str, float | int]]:
    """Mean of *metric* within each category label."""
    buckets: dict[str, list[float]] = {}
    for row, cat in zip(per_query, categories, strict=False):
        v = row.get(metric)
        if not _isnan(v):
            buckets.setdefault(cat or "uncategorized", []).append(float(v))
    out: dict[str, dict[str, float | int]] = {}
    for cat, vals in sorted(buckets.items()):
        out[cat] = {"mean": round(sum(vals) / len(vals), 4), "n": len(vals)}
    return out


def _isnan(x: Any) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True
