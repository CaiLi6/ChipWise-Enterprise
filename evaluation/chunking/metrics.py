"""Layer 1 retrieval-level metrics (no LLM needed)."""

from __future__ import annotations

import math
from typing import Any


def keyword_recall_at_k(
    chunks: list[dict[str, Any]],
    expected_keywords: list[str],
    k: int = 10,
) -> float:
    """Fraction of *expected_keywords* found in the top-*k* chunks' content."""
    if not expected_keywords:
        return 1.0
    combined = " ".join(c.get("content", "") for c in chunks[:k]).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
    return hits / len(expected_keywords)


def section_recall_at_k(
    chunks: list[dict[str, Any]],
    relevant_sections: list[str],
    k: int = 10,
) -> float:
    """Fraction of *relevant_sections* that appear in top-*k* chunk metadata."""
    if not relevant_sections:
        return 1.0
    found_sections: set[str] = set()
    for c in chunks[:k]:
        meta = c.get("metadata", {})
        title = meta.get("section_title", "") or meta.get("section", "")
        if title:
            found_sections.add(title.strip().lower())
    hits = sum(
        1 for s in relevant_sections if s.strip().lower() in found_sections
    )
    return hits / len(relevant_sections)


def mrr_at_k(
    chunks: list[dict[str, Any]],
    relevant_sections: list[str],
    k: int = 10,
) -> float:
    """Mean Reciprocal Rank based on section matching."""
    relevant_lower = {s.strip().lower() for s in relevant_sections}
    for i, c in enumerate(chunks[:k]):
        meta = c.get("metadata", {})
        title = (meta.get("section_title", "") or meta.get("section", "")).strip().lower()
        if title in relevant_lower:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(
    chunks: list[dict[str, Any]],
    relevant_sections: list[str],
    k: int = 10,
) -> float:
    """Normalized Discounted Cumulative Gain (section-based relevance)."""
    relevant_lower = {s.strip().lower() for s in relevant_sections}

    def _relevance(chunk: dict[str, Any]) -> int:
        meta = chunk.get("metadata", {})
        title = (meta.get("section_title", "") or meta.get("section", "")).strip().lower()
        return 1 if title in relevant_lower else 0

    dcg = sum(
        _relevance(c) / math.log2(i + 2) for i, c in enumerate(chunks[:k])
    )
    ideal = sorted([_relevance(c) for c in chunks[:k]], reverse=True)
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))

    return dcg / idcg if idcg > 0 else 0.0


def context_cost(chunks: list[dict[str, Any]], k: int = 10) -> dict[str, float]:
    """Compute cost proxy metrics for the top-*k* chunks."""
    top = chunks[:k]
    total_chars = sum(len(c.get("content", "")) for c in top)
    avg_chars = total_chars / len(top) if top else 0
    approx_tokens = total_chars / 4.0  # rough estimate
    return {
        "num_chunks": len(top),
        "total_chars": total_chars,
        "avg_chars_per_chunk": round(avg_chars, 1),
        "approx_total_tokens": round(approx_tokens, 1),
    }


def evaluate_retrieval(
    chunks: list[dict[str, Any]],
    qrel: dict[str, Any],
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Run all L1 metrics for a single query-qrel pair at multiple k values."""
    if k_values is None:
        k_values = [5, 10, 20]

    expected_keywords = qrel.get("expected_keywords", [])
    relevant_sections = qrel.get("relevant_sections", [])

    results: dict[str, Any] = {}
    for k in k_values:
        suffix = f"@{k}"
        results[f"keyword_recall{suffix}"] = keyword_recall_at_k(chunks, expected_keywords, k)
        results[f"section_recall{suffix}"] = section_recall_at_k(chunks, relevant_sections, k)
        results[f"mrr{suffix}"] = mrr_at_k(chunks, relevant_sections, k)
        results[f"ndcg{suffix}"] = ndcg_at_k(chunks, relevant_sections, k)

    results["cost"] = context_cost(chunks, k_values[-1])
    return results
