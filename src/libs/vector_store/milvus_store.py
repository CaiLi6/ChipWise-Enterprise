"""Milvus vector store implementation (§4.7.2).

Wraps ``pymilvus`` SDK for dense/sparse upsert, query, hybrid search,
delete, and get-by-ids operations. Uses RRFRanker for hybrid search fusion.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.types import ChunkRecord, RetrievalResult

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class MilvusStore(BaseVectorStore):
    """Milvus Standalone vector store backend.

    Connects via ``pymilvus`` and caches ``Collection`` references.
    Connection settings come from ``settings.yaml`` / ``VectorStoreFactory``.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        default_collection: str = "datasheet_chunks",
    ) -> None:
        self._host = host
        self._port = port
        self._default_collection = default_collection
        self._connected = False
        self._connect()

    def _connect(self) -> None:
        from pymilvus import connections  # type: ignore[import-untyped]

        try:
            connections.connect(alias="default", host=self._host, port=str(self._port))
            self._connected = True
            logger.info("Connected to Milvus at %s:%s", self._host, self._port)
        except Exception as exc:
            self._connected = False
            raise ConnectionError(
                f"Cannot connect to Milvus at {self._host}:{self._port}: {exc}"
            ) from exc

    def _get_collection(self, name: str) -> Any:
        from pymilvus import Collection  # type: ignore[import-untyped]

        col = Collection(name)
        col.load()
        return col

    async def upsert(self, records: list[ChunkRecord], collection: str = "datasheet_chunks") -> int:
        from pymilvus import Collection  # type: ignore[import-untyped]

        col = Collection(collection)
        data = []
        for r in records:
            # The live schema keys the chunk to `chip_id` (INT64), not a
            # string `doc_id`. Coerce via metadata override, falling back
            # to parsing doc_id as int when possible.
            chip_id: int = int(r.metadata.get("chip_id", 0) or 0)
            if not chip_id:
                try:
                    chip_id = int(r.doc_id)
                except (TypeError, ValueError):
                    chip_id = 0
            row: dict[str, Any] = {
                "chunk_id": r.chunk_id,
                "chip_id": chip_id,
                "content": r.content,
                "dense_vector": r.dense_vector,
                "part_number": r.metadata.get("part_number", ""),
                "manufacturer": r.metadata.get("manufacturer", ""),
                "doc_type": r.metadata.get("doc_type", "datasheet"),
                "page": int(r.metadata.get("page", 0) or 0),
                "section": r.metadata.get("section", ""),
                "collection": r.metadata.get("collection", collection),
            }
            if r.sparse_vector:
                row["sparse_vector"] = r.sparse_vector
            data.append(row)

        result = col.upsert(data)
        return result.upsert_count if hasattr(result, "upsert_count") else len(records)

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        col = self._get_collection(collection)

        expr = self._build_filter_expr(filters) if filters else ""
        results = col.search(
            data=[vector],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=top_k,
            expr=expr or None,
            output_fields=["chunk_id", "chip_id", "part_number", "page", "section", "content"],
        )

        return self._parse_search_results(results)

    async def hybrid_search(
        self,
        dense: list[float],
        sparse: dict[int, float] | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
        *,
        sparse_text: str | None = None,
        sparse_method: str = "bgem3",
    ) -> list[RetrievalResult]:
        from pymilvus import AnnSearchRequest, RRFRanker  # type: ignore[import-untyped]

        col = self._get_collection(collection)

        expr = self._build_filter_expr(filters) if filters else ""

        dense_req = AnnSearchRequest(
            data=[dense],
            anns_field="dense_vector",
            param={"metric_type": "COSINE", "params": {"ef": 128}},
            limit=top_k,
            expr=expr or None,
        )

        if sparse_method == "bm25":
            if sparse_text is None:
                raise ValueError("sparse_text is required when sparse_method='bm25'")
            sparse_req = AnnSearchRequest(
                data=[sparse_text],
                anns_field="bm25_vector",
                param={"metric_type": "BM25"},
                limit=top_k,
                expr=expr or None,
            )
        else:
            if sparse is None:
                raise ValueError("sparse dict is required when sparse_method='bgem3'")
            sparse_req = AnnSearchRequest(
                data=[sparse],
                anns_field="sparse_vector",
                param={"metric_type": "IP", "params": {}},
                limit=top_k,
                expr=expr or None,
            )

        results = col.hybrid_search(
            reqs=[dense_req, sparse_req],
            rerank=RRFRanker(k=60),
            limit=top_k,
            output_fields=["chunk_id", "chip_id", "part_number", "page", "section", "content"],
        )

        return self._parse_search_results(results)

    async def delete(self, ids: list[str], collection: str = "datasheet_chunks") -> int:
        from pymilvus import Collection  # type: ignore[import-untyped]

        col = Collection(collection)
        expr = f'chunk_id in {ids}'
        result = col.delete(expr)
        return result.delete_count if hasattr(result, "delete_count") else len(ids)

    async def get_by_ids(self, ids: list[str], collection: str = "datasheet_chunks") -> list[dict[str, Any]]:
        from pymilvus import Collection  # type: ignore[import-untyped]

        col = Collection(collection)
        col.load()
        expr = f'chunk_id in {ids}'
        results = col.query(
            expr=expr,
            output_fields=["chunk_id", "chip_id", "part_number", "page", "section", "content"],
        )
        return results  # type: ignore[no-any-return]

    async def health_check(self) -> bool:
        try:
            from pymilvus import connections  # type: ignore[import-untyped]

            connections.connect(alias="default", host=self._host, port=str(self._port))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        from pymilvus import connections  # type: ignore[import-untyped]

        try:
            connections.disconnect("default")
            self._connected = False
        except Exception:
            pass

    @staticmethod
    def _build_filter_expr(filters: dict[str, Any]) -> str:
        parts = []
        for key, value in filters.items():
            if isinstance(value, str):
                parts.append(f'{key} == "{value}"')
            else:
                parts.append(f"{key} == {value}")
        return " and ".join(parts)

    @staticmethod
    def _parse_search_results(results: Any) -> list[RetrievalResult]:
        parsed: list[RetrievalResult] = []
        for hits in results:
            for hit in hits:
                entity = hit.entity if hasattr(hit, "entity") else {}
                fields = entity.fields if hasattr(entity, "fields") else (entity if isinstance(entity, dict) else {})
                page_val = fields.get("page")
                parsed.append(RetrievalResult(
                    chunk_id=fields.get("chunk_id", str(hit.id)),
                    doc_id=str(fields.get("chip_id", "") or fields.get("doc_id", "")),
                    content=fields.get("content", ""),
                    score=hit.score if hasattr(hit, "score") else 0.0,
                    source=fields.get("part_number", ""),
                    page_number=int(page_val) if page_val not in (None, "", 0) else None,  # type: ignore[arg-type]
                    metadata={
                        "part_number": fields.get("part_number", ""),
                        "section": fields.get("section", ""),
                    },
                ))
        return parsed
