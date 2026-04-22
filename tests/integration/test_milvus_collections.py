"""Integration test: verify Milvus collections and indexes.

Requires: docker-compose up -d (Milvus running)
"""

from __future__ import annotations

import pytest
from pymilvus import Collection, connections, utility

pytestmark = [pytest.mark.integration, pytest.mark.integration_nollm]


class TestMilvusCollections:
    """Verify Milvus collections exist with correct schema and indexes."""

    @pytest.fixture(autouse=True)
    def _connect(self) -> None:
        connections.connect("default", host="localhost", port=19530)
        yield
        connections.disconnect("default")

    def test_datasheet_chunks_exists(self) -> None:
        assert utility.has_collection("datasheet_chunks")

    def test_knowledge_notes_exists(self) -> None:
        assert utility.has_collection("knowledge_notes")

    def test_datasheet_chunks_field_count(self) -> None:
        col = Collection("datasheet_chunks")
        # 11 base fields + 1 BM25 sparse vector field added in Phase 12 (settings.retrieval.sparse_method=bm25)
        assert len(col.schema.fields) in (11, 12)

    def test_knowledge_notes_field_count(self) -> None:
        col = Collection("knowledge_notes")
        assert len(col.schema.fields) in (8, 9)

    def test_datasheet_chunks_dense_dim(self) -> None:
        col = Collection("datasheet_chunks")
        dense_field = next(f for f in col.schema.fields if f.name == "dense_vector")
        assert dense_field.params.get("dim") == 1024
