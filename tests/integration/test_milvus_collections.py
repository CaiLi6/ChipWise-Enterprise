"""Integration test: verify Milvus collections and indexes.

Requires: docker-compose up -d (Milvus running)
"""

from __future__ import annotations

import pytest
from pymilvus import Collection, connections, utility


@pytest.mark.integration
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
        assert len(col.schema.fields) == 11

    def test_knowledge_notes_field_count(self) -> None:
        col = Collection("knowledge_notes")
        assert len(col.schema.fields) == 8

    def test_datasheet_chunks_dense_dim(self) -> None:
        col = Collection("datasheet_chunks")
        dense_field = next(f for f in col.schema.fields if f.name == "dense_vector")
        assert dense_field.params.get("dim") == 1024
