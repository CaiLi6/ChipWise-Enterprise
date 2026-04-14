"""Base chunker interface for pluggable chunking strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.types import Chunk


class BaseChunker(ABC):
    """Abstract base class for all text chunking strategies.

    Every chunker must implement ``split()`` with the same signature
    so that the factory can swap strategies without changing callers.
    """

    @abstractmethod
    def split(
        self,
        text: str,
        tables: list[Any] | None = None,
        doc_id: str = "",
    ) -> list[Chunk]:
        """Split *text* into a list of :class:`Chunk` objects.

        Args:
            text: Full extracted document text.
            tables: Optional pre-extracted table structures.
            doc_id: Document identifier used as chunk-ID prefix.

        Returns:
            Ordered list of chunks.
        """
        ...
