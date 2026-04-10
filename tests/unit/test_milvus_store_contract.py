"""Contract tests for MilvusStore — mocks pymilvus to verify interface shape."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from src.core.types import ChunkRecord, RetrievalResult
from src.libs.vector_store.base import BaseVectorStore


# ------------------------------------------------------------------
# Lightweight in-memory BaseVectorStore for contract testing
# ------------------------------------------------------------------
class InMemoryVectorStore(BaseVectorStore):
    """Trivial in-memory implementation for verifying the contract."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def upsert(self, records: list[ChunkRecord], collection: str = "datasheet_chunks") -> int:
        for r in records:
            self._data[r.chunk_id] = {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "content": r.content,
                "dense_vector": r.dense_vector,
                "sparse_vector": r.sparse_vector,
            }
        return len(records)

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        results = []
        for cid, data in list(self._data.items())[:top_k]:
            results.append(RetrievalResult(
                chunk_id=data["chunk_id"],
                doc_id=data["doc_id"],
                content=data["content"],
                score=0.9,
            ))
        return results

    async def hybrid_search(
        self,
        dense: list[float],
        sparse: dict[int, float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        return await self.query(dense, top_k, filters, collection)

    async def delete(self, ids: list[str], collection: str = "datasheet_chunks") -> int:
        count = 0
        for cid in ids:
            if cid in self._data:
                del self._data[cid]
                count += 1
        return count

    async def get_by_ids(self, ids: list[str], collection: str = "datasheet_chunks") -> list[dict[str, Any]]:
        return [self._data[cid] for cid in ids if cid in self._data]


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------
def _make_records(n: int = 3, dim: int = 8) -> list[ChunkRecord]:
    return [
        ChunkRecord(
            chunk_id=f"chunk_{i}",
            doc_id=f"doc_{i}",
            content=f"Content {i}",
            dense_vector=[float(i)] * dim,
            sparse_vector={i: 1.0},
        )
        for i in range(n)
    ]


@pytest.mark.unit
class TestBaseVectorStoreContract:
    """Verify the abstract interface contract via InMemoryVectorStore."""

    @pytest.fixture
    def store(self) -> InMemoryVectorStore:
        return InMemoryVectorStore()

    @pytest.mark.asyncio
    async def test_isinstance(self, store: InMemoryVectorStore) -> None:
        assert isinstance(store, BaseVectorStore)

    @pytest.mark.asyncio
    async def test_upsert_returns_count(self, store: InMemoryVectorStore) -> None:
        records = _make_records(5)
        count = await store.upsert(records)
        assert count == 5

    @pytest.mark.asyncio
    async def test_query_returns_retrieval_results(self, store: InMemoryVectorStore) -> None:
        await store.upsert(_make_records(3))
        results = await store.query([0.0] * 8, top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_results(self, store: InMemoryVectorStore) -> None:
        await store.upsert(_make_records(3))
        results = await store.hybrid_search([0.0] * 8, {0: 1.0}, top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_delete_returns_count(self, store: InMemoryVectorStore) -> None:
        await store.upsert(_make_records(3))
        count = await store.delete(["chunk_0", "chunk_1"])
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store: InMemoryVectorStore) -> None:
        count = await store.delete(["does_not_exist"])
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_by_ids(self, store: InMemoryVectorStore) -> None:
        await store.upsert(_make_records(3))
        results = await store.get_by_ids(["chunk_0", "chunk_2"])
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)

    @pytest.mark.asyncio
    async def test_get_by_ids_empty(self, store: InMemoryVectorStore) -> None:
        results = await store.get_by_ids(["nonexistent"])
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_default(self, store: InMemoryVectorStore) -> None:
        assert await store.health_check() is True

    @pytest.mark.asyncio
    async def test_upsert_then_query_roundtrip(self, store: InMemoryVectorStore) -> None:
        records = _make_records(5)
        await store.upsert(records)
        results = await store.query([0.0] * 8, top_k=5)
        assert len(results) == 5
        chunk_ids = {r.chunk_id for r in results}
        assert "chunk_0" in chunk_ids

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, store: InMemoryVectorStore) -> None:
        await store.upsert(_make_records(1))
        results = await store.query([0.0] * 8, top_k=1)
        r = results[0]
        assert hasattr(r, "chunk_id")
        assert hasattr(r, "doc_id")
        assert hasattr(r, "content")
        assert hasattr(r, "score")


@pytest.mark.unit
class TestMilvusStoreConnectionError:
    """MilvusStore should raise readable ConnectionError."""

    def test_connection_failure_message(self) -> None:
        with patch("pymilvus.connections") as mock_conn:
            mock_conn.connect.side_effect = Exception("refused")
            with pytest.raises(ConnectionError, match="Cannot connect to Milvus"):
                from src.libs.vector_store.milvus_store import MilvusStore
                MilvusStore(host="bad_host", port=99999)


@pytest.mark.unit
class TestVectorStoreFactory:
    def test_unknown_backend_raises(self) -> None:
        from src.libs.vector_store.factory import VectorStoreFactory
        with pytest.raises(ValueError, match="Unknown vector store backend"):
            VectorStoreFactory.create({"vector_store": {"backend": "qdrant"}})
