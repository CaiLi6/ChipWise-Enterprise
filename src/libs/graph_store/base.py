"""Abstract base class for graph store backends (§4.7.4)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseGraphStore(ABC):
    """Pluggable graph store abstraction.

    Implementations must support openCypher queries, node/edge CRUD,
    sub-graph retrieval, and a health check endpoint.
    """

    @abstractmethod
    def execute_cypher(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute an openCypher query and return result rows as dicts."""

    @abstractmethod
    def upsert_node(self, label: str, properties: dict[str, Any], key_field: str = "id") -> None:
        """Insert or update a node (MERGE semantics). Idempotent."""

    @abstractmethod
    def upsert_edge(
        self,
        rel_type: str,
        from_label: str,
        from_key: Any,
        to_label: str,
        to_key: Any,
        properties: dict[str, Any] | None = None,
        from_key_field: str = "id",
        to_key_field: str = "id",
    ) -> None:
        """Insert or update a relationship. Idempotent."""

    @abstractmethod
    def get_subgraph(
        self,
        start_label: str,
        start_key: Any,
        max_hops: int = 2,
        key_field: str = "id",
    ) -> list[dict[str, Any]]:
        """Return the sub-graph reachable from a starting node within *max_hops*."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the graph store is reachable and operational."""

    def close(self) -> None:  # noqa: B027
        """Release resources. Override if the backend needs cleanup."""
