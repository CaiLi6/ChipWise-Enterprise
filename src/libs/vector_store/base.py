"""Abstract base class for vector store backends (§4.7)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.types import ChunkRecord, RetrievalResult


class BaseVectorStore(ABC):
    """Pluggable vector store abstraction.

    Implementations must support upsert, dense query, hybrid search,
    delete, and get-by-ids.
    """

    @abstractmethod
    async def upsert(self, records: list[ChunkRecord], collection: str = "datasheet_chunks") -> int:
        """Insert or update chunk records. Returns number of records upserted."""

    @abstractmethod
    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        """Dense vector search. Returns results sorted by descending score."""

    @abstractmethod
    async def hybrid_search(
        self,
        dense: list[float],
        sparse: dict[int, float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        collection: str = "datasheet_chunks",
    ) -> list[RetrievalResult]:
        """Hybrid (dense+sparse) vector search with RRF fusion."""

    @abstractmethod
    async def delete(self, ids: list[str], collection: str = "datasheet_chunks") -> int:
        """Delete records by chunk IDs. Returns number deleted."""

    @abstractmethod
    async def get_by_ids(self, ids: list[str], collection: str = "datasheet_chunks") -> list[dict[str, Any]]:
        """Retrieve records by chunk IDs."""

    async def health_check(self) -> bool:
        """Return True if the vector store is reachable."""
        return True

    async def close(self) -> None:  # noqa: B027
        """Release resources."""
