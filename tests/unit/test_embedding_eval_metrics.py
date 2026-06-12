"""Unit tests for the embedding-benchmark metrics + exact-cosine index.

Fast, model-free — validates ranking-metric correctness and that the faiss/numpy
index returns the right neighbours. Marked ``unit`` to run without Docker/models.
"""

from __future__ import annotations

import numpy as np
import pytest
from evaluation.embedding import index, metrics

pytestmark = pytest.mark.unit


def test_recall_and_hit_at_k():
    ranked = ["c2", "c0", "c4", "c1", "c3"]
    qrel = {"c2": 2.0, "c4": 1.0}
    assert metrics.recall_at_k(ranked, qrel, 1) == 0.5
    assert metrics.recall_at_k(ranked, qrel, 5) == 1.0
    assert metrics.hit_at_k(ranked, qrel, 1) == 1.0
    assert metrics.hit_at_k(["c0", "c1"], qrel, 2) == 0.0


def test_mrr_and_map():
    ranked = ["c1", "c0", "c2"]
    qrel = {"c0": 2.0}
    assert metrics.mrr_at_k(ranked, qrel, 10) == pytest.approx(0.5)
    # AP: relevant at rank 2 -> precision 1/2, single relevant -> AP = 0.5
    assert metrics.average_precision(ranked, qrel, 10) == pytest.approx(0.5)


def test_ndcg_graded_perfect_and_imperfect():
    qrel = {"a": 2.0, "b": 1.0}
    assert metrics.ndcg_at_k(["a", "b"], qrel, 10) == pytest.approx(1.0)
    # swapping order lowers nDCG below 1
    assert metrics.ndcg_at_k(["b", "a"], qrel, 10) < 1.0


def test_no_relevant_returns_nan():
    out = metrics.per_query_metrics(["x", "y"], {})
    assert all(np.isnan(v) for v in out.values())


def test_aggregate_skips_nan_and_reports_ci():
    pq = [
        {"ndcg@10": 1.0},
        {"ndcg@10": 0.0},
        {"ndcg@10": float("nan")},
    ]
    agg = metrics.aggregate(pq)
    assert agg["ndcg@10"]["n"] == 2
    assert agg["ndcg@10"]["mean"] == pytest.approx(0.5)
    assert agg["ndcg@10"]["ci_low"] <= agg["ndcg@10"]["mean"] <= agg["ndcg@10"]["ci_high"]


def test_aggregate_by_category():
    pq = [{"ndcg@10": 1.0}, {"ndcg@10": 0.5}]
    cats = ["numeric", "table_lookup"]
    out = metrics.aggregate_by_category(pq, cats, "ndcg@10")
    assert out["numeric"]["mean"] == 1.0
    assert out["table_lookup"]["mean"] == 0.5


def test_index_exact_cosine_topk():
    rng = np.random.default_rng(0)
    corpus = rng.normal(size=(6, 8)).astype("float32")
    corpus /= np.linalg.norm(corpus, axis=1, keepdims=True)
    # query identical to row 3 -> must rank row 3 first with score ~1.0
    q = corpus[3:4].copy()
    idx, scores = index.search(corpus, q, top_k=3)
    assert idx[0][0] == 3
    assert scores[0][0] == pytest.approx(1.0, abs=1e-4)
    ids = index.ranked_chunk_ids(idx, [f"c{i}" for i in range(6)])
    assert ids[0][0] == "c3"
