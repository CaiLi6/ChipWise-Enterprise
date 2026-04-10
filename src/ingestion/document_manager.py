"""DocumentManager — cross-storage coordinated deletion (§3C4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeleteResult:
    """Result of a document deletion across all stores."""

    pg_deleted: int = 0
    milvus_deleted: int = 0
    graph_deleted: int = 0
    file_deleted: bool = False
    errors: list[str] = field(default_factory=list)


class DocumentManager:
    """Coordinate document lifecycle across PG, Milvus, Kùzu, and filesystem."""

    def __init__(
        self,
        db_pool: Any = None,
        vector_store: Any = None,
        graph_store: Any = None,
        redis: Any = None,
    ) -> None:
        self._pool = db_pool
        self._vector = vector_store
        self._graph = graph_store
        self._redis = redis

    async def delete_document(self, doc_id: int) -> DeleteResult:
        """Delete a document from all storage systems.

        Each step is independent — partial failures are recorded but don't block others.
        """
        result = DeleteResult()

        doc_info: dict[str, Any] = {}

        # Step 1: Get doc info from PG
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM documents WHERE doc_id = $1", doc_id
                    )
                    if row:
                        doc_info = dict(row)
                    else:
                        result.errors.append(f"Document {doc_id} not found in PG")
                        return result
            except Exception as e:
                result.errors.append(f"PG lookup failed: {e}")

        # Step 2: Delete from Milvus
        if self._vector and doc_info:
            try:
                chunk_ids = await self._get_chunk_ids(doc_id)
                if chunk_ids:
                    await self._vector.delete(chunk_ids)
                    result.milvus_deleted = len(chunk_ids)
            except Exception as e:
                result.errors.append(f"Milvus delete failed: {e}")

        # Step 3: Delete from Kùzu
        if self._graph:
            try:
                await self._graph.delete_node("Document", doc_id)
                result.graph_deleted = 1
            except Exception as e:
                result.errors.append(f"Graph delete failed: {e}")

        # Step 4: Delete from PG
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM chip_parameters WHERE chip_id IN "
                        "(SELECT chip_id FROM chip_documents WHERE doc_id = $1)",
                        doc_id,
                    )
                    await conn.execute(
                        "DELETE FROM documents WHERE doc_id = $1", doc_id
                    )
                    result.pg_deleted = 1
            except Exception as e:
                result.errors.append(f"PG delete failed: {e}")

        # Step 5: Delete file
        file_path = doc_info.get("file_path", "")
        if file_path:
            try:
                p = Path(file_path)
                if p.exists():
                    p.unlink()
                    result.file_deleted = True
            except Exception as e:
                result.errors.append(f"File delete failed: {e}")

        # Step 6: Cache invalidation
        part_number = doc_info.get("part_number", "")
        if part_number and self._redis:
            try:
                import json, time
                await self._redis.publish(
                    f"cache:invalidate:{part_number}",
                    json.dumps({"part_number": part_number, "timestamp": time.time()}),
                )
            except Exception:
                pass

        return result

    async def _get_chunk_ids(self, doc_id: int) -> list[str]:
        """Get chunk IDs associated with a document from PG."""
        if not self._pool:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chunk_id FROM chunks WHERE doc_id = $1", doc_id
            )
            return [row["chunk_id"] for row in rows]
