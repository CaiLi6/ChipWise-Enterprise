"""Exact cosine retrieval for the apples-to-apples accuracy comparison.

Vectors are L2-normalized upstream, so cosine == inner product. Exact (flat)
search isolates embedding quality from ANN-index error. faiss is used when
available; otherwise a pure-numpy fallback gives identical results.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _try_faiss() -> Any | None:
    try:
        import faiss

        return faiss
    except Exception:  # noqa: BLE001
        return None


def search(
    corpus_vecs: np.ndarray,
    query_vecs: np.ndarray,
    top_k: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (indices, scores) of the top-*k* corpus rows per query.

    Args:
        corpus_vecs: (N, dim) float32, L2-normalized.
        query_vecs:  (Q, dim) float32, L2-normalized.
        top_k: neighbours per query.

    Returns:
        indices: (Q, top_k) int64 — row indices into ``corpus_vecs``.
        scores:  (Q, top_k) float32 — cosine similarities (descending).
    """
    corpus_vecs = np.ascontiguousarray(corpus_vecs, dtype=np.float32)
    query_vecs = np.ascontiguousarray(query_vecs, dtype=np.float32)
    top_k = min(top_k, corpus_vecs.shape[0])

    faiss = _try_faiss()
    if faiss is not None:
        index = faiss.IndexFlatIP(corpus_vecs.shape[1])
        index.add(corpus_vecs)
        scores, indices = index.search(query_vecs, top_k)
        return indices, scores

    # numpy fallback: full similarity matrix, then top-k via argpartition
    sims = query_vecs @ corpus_vecs.T  # (Q, N)
    idx_part = np.argpartition(-sims, top_k - 1, axis=1)[:, :top_k]
    part_scores = np.take_along_axis(sims, idx_part, axis=1)
    order = np.argsort(-part_scores, axis=1)
    indices = np.take_along_axis(idx_part, order, axis=1)
    scores = np.take_along_axis(part_scores, order, axis=1)
    return indices, scores


def ranked_chunk_ids(
    indices: np.ndarray,
    chunk_ids: list[str],
) -> list[list[str]]:
    """Map (Q, k) row indices to ranked chunk-id lists per query."""
    return [[chunk_ids[i] for i in row] for row in indices]
