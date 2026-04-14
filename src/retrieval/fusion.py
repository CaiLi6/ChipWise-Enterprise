"""Multi-source result fusion (§2B4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.core.types import RetrievalResult

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {"vector": 0.6, "sql": 0.2, "graph": 0.2}
GRAPH_BOOST_FACTOR = 1.15


@dataclass
class FusedResult:
    """Merged result from multiple retrieval sources."""
    content: str
    source: str
    score: float
    chunk_id: str = ""
    doc_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MultiSourceFusion:
    """Fuses vector, SQL, and graph query results with weighted scoring."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or DEFAULT_WEIGHTS.copy()

    def fuse(
        self,
        vector_results: list[RetrievalResult] | None = None,
        sql_results: list[dict[str, Any]] | None = None,
        graph_results: list[dict[str, Any]] | None = None,
    ) -> list[FusedResult]:
        """Merge, deduplicate, and score results from multiple sources."""
        seen: dict[str, FusedResult] = {}

        # Vector results
        for r in (vector_results or []):
            key = r.chunk_id or r.content[:100]
            if key not in seen or r.score * self._weights["vector"] > seen[key].score:
                seen[key] = FusedResult(
                    content=r.content,
                    source="vector",
                    score=r.score * self._weights["vector"],
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    metadata=r.metadata,
                )

        # SQL results
        for sr in (sql_results or []):
            key = sr.get("chunk_id", sr.get("content", "")[:100])
            score = float(sr.get("score", 0.5)) * self._weights["sql"]
            if key not in seen or score > seen[key].score:
                seen[key] = FusedResult(
                    content=sr.get("content", ""),
                    source="sql",
                    score=score,
                    chunk_id=sr.get("chunk_id", ""),
                    doc_id=sr.get("doc_id", ""),
                    metadata=sr,
                )

        # Graph results — also used for boosting
        graph_part_numbers: set[str] = set()
        for gr in (graph_results or []):
            pn = gr.get("part_number", "")
            if pn:
                graph_part_numbers.add(pn)
            key = gr.get("chunk_id", gr.get("part_number", str(gr)[:100]))
            score = float(gr.get("score", 0.5)) * self._weights["graph"]
            if key not in seen or score > seen[key].score:
                seen[key] = FusedResult(
                    content=gr.get("content", str(gr)),
                    source="graph",
                    score=score,
                    chunk_id=gr.get("chunk_id", ""),
                    doc_id=gr.get("doc_id", ""),
                    metadata=gr,
                )

        # Graph boost: if a result's part_number appears in graph_results, boost score
        if graph_part_numbers:
            for fused in seen.values():
                pn = fused.metadata.get("part_number", "")
                if pn in graph_part_numbers and fused.source != "graph":
                    fused.score *= GRAPH_BOOST_FACTOR

        # Sort by score descending, deterministic
        results = sorted(seen.values(), key=lambda x: (-x.score, x.chunk_id))
        return results
