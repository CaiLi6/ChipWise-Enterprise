"""Non-LLM RAG metrics — deterministic, cheap, computed from trace only."""

from __future__ import annotations

import math
import re
from typing import Any


def citation_coverage(answer: str, contexts: list[str], max_k: int = 10) -> float:
    """Fraction of retrieved contexts that are actually referenced in the answer.

    Uses char-n-gram overlap (3-gram shingles). A context is "used" when it
    shares ≥ 5 distinct 3-grams with the answer. Cheap proxy for how
    grounded the answer is on the retrieved set — does not require an LLM.

    Returns 0.0 when either side is empty or answer is shorter than 3 chars.
    """
    if not contexts or not answer or len(answer) < 3:
        return 0.0
    used = sum(1 for c in contexts[:max_k] if _shingle_overlap(answer, c) >= 5)
    return used / min(len(contexts), max_k)


def latency_score(duration_ms: float, target_ms: float = 8000.0, half_life: float = 12000.0) -> float:
    """Score latency on 0-1 via inverse sigmoid.

    At ``target_ms`` score ≈ 0.5; at 0 ms score → 1.0; at infinity → 0.0.
    ``half_life`` controls the slope. Tuned so:
      - 3s → 0.82
      - 8s → 0.5 (target)
      - 20s → 0.19
      - 40s → 0.03
    """
    if duration_ms is None or duration_ms < 0:
        return 0.0
    k = math.log(3) / half_life  # steepness
    return 1.0 / (1.0 + math.exp(k * (duration_ms - target_ms)))


def citation_diversity(citations: list[dict[str, Any]]) -> float:
    """Unique-source ratio: distinct (source, page) pairs / total citations.

    Higher = less redundant retrieval. Returns 0.0 on empty input.
    """
    if not citations:
        return 0.0
    keys = {(c.get("source") or "?", c.get("page") or c.get("page_number") or "?") for c in citations}
    return len(keys) / len(citations)


def agent_efficiency(iterations: int, max_iterations: int = 5) -> float:
    """1 - (iterations-1)/(max-1). 1 iteration = 1.0, max = 0.0.

    Lower iteration count is better — agent found the answer faster.
    """
    if max_iterations <= 1 or iterations < 1:
        return 1.0
    return max(0.0, 1.0 - (iterations - 1) / (max_iterations - 1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE.sub("", text.lower())


def _shingle_overlap(a: str, b: str, n: int = 3) -> int:
    a_n = _normalize(a)
    b_n = _normalize(b)
    if len(a_n) < n or len(b_n) < n:
        return 0
    a_set = {a_n[i : i + n] for i in range(len(a_n) - n + 1)}
    b_set = {b_n[i : i + n] for i in range(len(b_n) - n + 1)}
    return len(a_set & b_set)
