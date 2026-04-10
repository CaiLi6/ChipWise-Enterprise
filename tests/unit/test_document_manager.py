"""Unit tests for DocumentManager (§3C4)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ingestion.document_manager import DocumentManager, DeleteResult


@pytest.mark.unit
class TestDocumentManager:
    @pytest.fixture
    def pool(self) -> MagicMock:
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "doc_id": 1,
            "file_path": "/tmp/test.pdf",
            "part_number": "STM32F407",
        }
        conn.fetch.return_value = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        conn.execute.return_value = None

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value = cm
        return pool

    @pytest.fixture
    def manager(self, pool: MagicMock) -> DocumentManager:
        vector = AsyncMock()
        graph = AsyncMock()
        redis = AsyncMock()
        return DocumentManager(pool, vector, graph, redis)

    @pytest.mark.asyncio
    async def test_delete_success(self, manager: DocumentManager) -> None:
        result = await manager.delete_document(1)
        assert isinstance(result, DeleteResult)
        assert result.pg_deleted == 1
        assert result.milvus_deleted == 2

    @pytest.mark.asyncio
    async def test_delete_not_found(self, pool: MagicMock) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow.return_value = None
        mgr = DocumentManager(pool)
        result = await mgr.delete_document(999)
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_milvus_failure_recorded(self, pool: MagicMock) -> None:
        vector = AsyncMock()
        vector.delete.side_effect = Exception("Milvus down")
        mgr = DocumentManager(pool, vector)
        result = await mgr.delete_document(1)
        assert any("Milvus" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_delete_result_defaults(self) -> None:
        r = DeleteResult()
        assert r.pg_deleted == 0
        assert r.file_deleted is False
        assert r.errors == []

    @pytest.mark.asyncio
    async def test_no_pool_returns_empty(self) -> None:
        mgr = DocumentManager()
        result = await mgr.delete_document(1)
        # No pool, can't look up doc
        assert result.pg_deleted == 0
