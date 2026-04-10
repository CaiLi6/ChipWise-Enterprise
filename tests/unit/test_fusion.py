"""Unit tests for MultiSourceFusion."""

from __future__ import annotations

import pytest
from typing import Any

from src.core.types import RetrievalResult
from src.retrieval.fusion import MultiSourceFusion, FusedResult


@pytest.mark.unit
class TestMultiSourceFusion:
    def test_vector_only(self) -> None:
        fusion = MultiSourceFusion()
        vector = [
            RetrievalResult(chunk_id="c1", doc_id="d1", content="text1", score=0.9),
            RetrievalResult(chunk_id="c2", doc_id="d2", content="text2", score=0.7),
        ]
        results = fusion.fuse(vector_results=vector)
        assert len(results) == 2
        assert results[0].score > results[1].score

    def test_sql_only(self) -> None:
        fusion = MultiSourceFusion()
        sql = [{"chunk_id": "s1", "content": "sql result", "score": 0.8, "doc_id": "d1"}]
        results = fusion.fuse(sql_results=sql)
        assert len(results) == 1
        assert results[0].source == "sql"

    def test_graph_only(self) -> None:
        fusion = MultiSourceFusion()
        graph = [{"part_number": "STM32", "content": "graph data", "score": 0.75}]
        results = fusion.fuse(graph_results=graph)
        assert len(results) == 1
        assert results[0].source == "graph"

    def test_three_source_fusion(self) -> None:
        fusion = MultiSourceFusion()
        vector = [RetrievalResult(chunk_id="v1", doc_id="d1", content="vec", score=0.9)]
        sql = [{"chunk_id": "s1", "content": "sql", "score": 0.8, "doc_id": "d2"}]
        graph = [{"chunk_id": "g1", "content": "graph", "score": 0.7, "doc_id": "d3"}]
        results = fusion.fuse(vector_results=vector, sql_results=sql, graph_results=graph)
        assert len(results) == 3
        # Sorted by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_dedup_by_chunk_id(self) -> None:
        fusion = MultiSourceFusion()
        vector = [RetrievalResult(chunk_id="c1", doc_id="d1", content="text", score=0.9)]
        sql = [{"chunk_id": "c1", "content": "text", "score": 0.5, "doc_id": "d1"}]
        results = fusion.fuse(vector_results=vector, sql_results=sql)
        assert len(results) == 1  # Deduped

    def test_graph_boost(self) -> None:
        fusion = MultiSourceFusion()
        vector = [RetrievalResult(
            chunk_id="v1", doc_id="d1", content="text", score=0.8,
            metadata={"part_number": "STM32F407"},
        )]
        graph = [{"part_number": "STM32F407", "content": "graph data", "score": 0.5}]
        results = fusion.fuse(vector_results=vector, graph_results=graph)
        # The vector result should be boosted because part_number appears in graph
        boosted = [r for r in results if r.chunk_id == "v1"]
        assert len(boosted) == 1
        assert boosted[0].score > 0.8 * 0.6  # Base score * vector_weight, boosted

    def test_deterministic_output(self) -> None:
        fusion = MultiSourceFusion()
        vector = [
            RetrievalResult(chunk_id="c1", doc_id="d1", content="a", score=0.5),
            RetrievalResult(chunk_id="c2", doc_id="d2", content="b", score=0.5),
        ]
        r1 = fusion.fuse(vector_results=vector)
        r2 = fusion.fuse(vector_results=vector)
        assert [r.chunk_id for r in r1] == [r.chunk_id for r in r2]

    def test_empty_all_sources(self) -> None:
        fusion = MultiSourceFusion()
        results = fusion.fuse()
        assert results == []

    def test_custom_weights(self) -> None:
        fusion = MultiSourceFusion(weights={"vector": 1.0, "sql": 0.0, "graph": 0.0})
        vector = [RetrievalResult(chunk_id="c1", doc_id="d1", content="t", score=0.5)]
        results = fusion.fuse(vector_results=vector)
        assert results[0].score == pytest.approx(0.5)  # 0.5 * 1.0
