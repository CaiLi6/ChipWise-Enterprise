"""Regression tests for document ingestion batching."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from src.api.routers import documents


class _FakeResponse:
    def __init__(self, size: int) -> None:
        self._size = size

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "dense": [[0.0] * 3 for _ in range(self._size)],
            "sparse": [{} for _ in range(self._size)],
        }


class _FakeAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.batches: list[int] = []

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
        del url
        batch_size = len(json["texts"])
        self.batches.append(batch_size)
        return _FakeResponse(batch_size)


class _FakeConn:
    def __init__(self) -> None:
        self.execute = AsyncMock()


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakePool:
    def __init__(self) -> None:
        self.conn = _FakeConn()

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.conn)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_one_batches_embedding_requests(monkeypatch, tmp_path) -> None:
    doc_dir = tmp_path / "Rockchip"
    doc_dir.mkdir()
    pdf_path = doc_dir / "RK3588_EVB1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake")

    pages = [(idx, f"Page {idx} " + ("X" * 80)) for idx in range(1, 66)]
    fake_client = _FakeAsyncClient()
    fake_pool = _FakePool()
    posted_batches: list[int] = []

    def fake_async_client(*args: Any, **kwargs: Any) -> _FakeAsyncClient:
        del args, kwargs
        return fake_client

    async def fake_upsert_chip_row(db_pool: Any, part_number: str, manufacturer: str, family: str) -> int:
        del db_pool, part_number, manufacturer, family
        return 123

    def fake_milvus_upsert(
        chip_id: int,
        part_number: str,
        manufacturer: str,
        doc_type: str,
        collection_name: str,
        chunks: list[dict[str, Any]],
        dense: list[list[float]],
        sparse_raw: list[Any],
    ) -> int:
        del chip_id, part_number, manufacturer, doc_type, collection_name
        assert len(chunks) == len(dense) == len(sparse_raw) == 65
        return len(chunks)

    async def fake_sync_kuzu(*args: Any, **kwargs: Any) -> dict[str, int]:
        del args, kwargs
        return {"nodes": 0, "edges": 0}

    async def fake_noop_async(*args: Any, **kwargs: Any) -> int:
        del args, kwargs
        return 0

    monkeypatch.setattr(documents.httpx, "AsyncClient", fake_async_client)
    monkeypatch.setattr(documents, "_extract_pdf_pages", lambda path: pages)
    monkeypatch.setattr(documents, "_extract_pdf_tables", lambda path: [])
    monkeypatch.setattr(documents, "_get_extractor_llm", lambda: None)
    monkeypatch.setattr(documents, "_upsert_chip_row", fake_upsert_chip_row)
    monkeypatch.setattr(documents, "_milvus_upsert", fake_milvus_upsert)
    monkeypatch.setattr(documents, "_sync_kuzu", fake_sync_kuzu)
    monkeypatch.setattr(documents, "_store_co_mentioned_chips", fake_noop_async)

    original_post = fake_client.post

    async def capture_post(url: str, json: dict[str, Any]) -> _FakeResponse:
        batch_size = len(json["texts"])
        posted_batches.append(batch_size)
        return await original_post(url, json)

    fake_client.post = capture_post  # type: ignore[assignment]

    result = await documents._ingest_one(
        {
            "id": 7,
            "file_path": str(pdf_path),
            "file_name": pdf_path.name,
            "doc_type": "datasheet",
            "collection": "default",
        },
        fake_pool,
    )

    assert result["chunks"] == 65
    assert posted_batches == [64, 1]
    assert fake_pool.conn.execute.await_count == 2
