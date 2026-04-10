"""Abstract base class for reranker backends (§4.7)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankResult:
    """Single reranked document with score."""
    index: int
    score: float
    text: str


class BaseReranker(ABC):
    """Pluggable reranker abstraction."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query. Returns top_k results sorted by score desc."""

    async def health_check(self) -> bool:
        return True


class NoneReranker(BaseReranker):
    """Pass-through reranker — returns original order. Used as fallback."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        return [
            RerankResult(index=i, score=1.0 - i * 0.001, text=doc)
            for i, doc in enumerate(documents[:top_k])
        ]
