"""Layer 2 end-to-end evaluation — pass queries through AgentOrchestrator."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def evaluate_e2e(
    query: str,
    qrel: dict[str, Any],
) -> dict[str, Any]:
    """Run a single query through the AgentOrchestrator and measure quality + latency.

    Returns dict with:
      - answer_keyword_hit: fraction of expected_keywords in the answer
      - answer_snippet_similarity: cosine similarity of answer vs expected_answer_snippet
      - latency_ms: end-to-end latency in milliseconds
      - prompt_tokens / completion_tokens: token counts (if available)
    """
    expected_keywords = qrel.get("expected_keywords", [])
    expected_snippet = qrel.get("expected_answer_snippet", "")

    start = time.perf_counter()
    answer, metadata = _run_query(query)
    latency_ms = (time.perf_counter() - start) * 1000

    # Keyword hit (zero LLM cost)
    answer_lower = answer.lower()
    kw_hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower) if expected_keywords else 0
    kw_recall = kw_hits / len(expected_keywords) if expected_keywords else 1.0

    # Snippet similarity via BGE-M3
    snippet_sim = _compute_similarity(answer, expected_snippet) if expected_snippet else 0.0

    return {
        "answer_keyword_hit": round(kw_recall, 4),
        "answer_snippet_similarity": round(snippet_sim, 4),
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": metadata.get("prompt_tokens", 0),
        "completion_tokens": metadata.get("completion_tokens", 0),
        "answer_preview": answer[:200],
    }


def _run_query(query: str) -> tuple[str, dict[str, Any]]:
    """Execute query through the orchestrator."""
    try:
        from src.agent.orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        result = orch.run(query)
        answer = result.get("answer", "") if isinstance(result, dict) else str(result)
        metadata = result if isinstance(result, dict) else {}
        return answer, metadata
    except Exception as e:
        logger.error("Orchestrator query failed: %s", e)
        return "", {}


def _compute_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity using BGE-M3 embeddings."""
    if not text_a or not text_b:
        return 0.0
    try:
        from src.libs.embedding.factory import create_embedding

        embedder = create_embedding()
        vecs = embedder.embed([text_a, text_b])
        if len(vecs) < 2:
            return 0.0
        dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
        norm_a = sum(a * a for a in vecs[0]) ** 0.5
        norm_b = sum(b * b for b in vecs[1]) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
    except Exception:
        return 0.0
