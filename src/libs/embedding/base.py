"""Abstract base class for embedding backends (§4.7)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmbeddingResult:
    """Result from an embedding encode call."""
    dense: list[list[float]] = field(default_factory=list)
    sparse: list[dict[int, float]] = field(default_factory=list)
    dimensions: int = 0


class BaseEmbedding(ABC):
    """Pluggable embedding abstraction.

    Implementations must produce dense vectors and optionally sparse vectors.
    """

    @abstractmethod
    async def encode(
        self,
        texts: list[str],
        return_sparse: bool = True,
    ) -> EmbeddingResult:
        """Encode texts into dense (and optionally sparse) vectors."""

    async def health_check(self) -> bool:
        return True
