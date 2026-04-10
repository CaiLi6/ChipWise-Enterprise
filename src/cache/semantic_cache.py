"""Semantic Cache — BGE-M3 embedding + Redis cosine similarity (§2D3)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from src.libs.embedding.base import BaseEmbedding

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.95
TTL_CONVERSATIONAL = 3600    # 1 hour
TTL_COMPARISON = 14400       # 4 hours
BUCKET_SIZE = 8              # LSH bucket capacity


@dataclass
class CachedResponse:
    """A cached query-response pair."""

    query: str
    response: dict[str, Any]
    tools_used: list[str]
    created_at: float
    similarity: float = 1.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _lsh_bucket_key(vec: list[float], n_bits: int = 8) -> str:
    """Simple LSH: sign of first n_bits dimensions → hex bucket key."""
    bits = "".join("1" if v >= 0 else "0" for v in vec[:n_bits])
    return hashlib.md5(bits.encode()).hexdigest()[:8]


class SemanticCache:
    """Embedding-based semantic cache backed by Redis.

    On ``get``: hash query embedding → LSH bucket → compare stored embeddings.
    On ``put``: store embedding + response in the matching bucket.
    Graceful degradation: Redis/embedding failures → cache miss / silent skip.
    """

    def __init__(self, embedding_client: BaseEmbedding, redis: Any) -> None:
        self._embedding = embedding_client
        self._redis = redis

    async def get(
        self, query: str, trace: Any | None = None
    ) -> Optional[CachedResponse]:
        """Look up a semantically similar cached response."""
        try:
            vec = await self._embedding.embed_query(query)
            bucket_key = _lsh_bucket_key(vec)
            redis_key = f"gptcache:bucket:{bucket_key}"

            raw_entries = await self._redis.lrange(redis_key, 0, -1)
            if not raw_entries:
                return None

            for raw in raw_entries:
                entry = json.loads(raw)
                sim = _cosine_similarity(vec, entry["vector"])
                if sim >= SIMILARITY_THRESHOLD:
                    if trace:
                        trace.record_stage("cache_hit", {"similarity": sim, "query": query})
                    return CachedResponse(
                        query=entry["query"],
                        response=entry["response"],
                        tools_used=entry.get("tools_used", []),
                        created_at=entry["created_at"],
                        similarity=sim,
                    )
            return None
        except Exception:
            logger.warning("Semantic cache get failed", exc_info=True)
            return None

    async def put(
        self,
        query: str,
        response: dict[str, Any],
        tools_used: list[str] | None = None,
    ) -> None:
        """Store a query-response pair in the cache."""
        try:
            vec = await self._embedding.embed_query(query)
            bucket_key = _lsh_bucket_key(vec)
            redis_key = f"gptcache:bucket:{bucket_key}"

            ttl = TTL_COMPARISON if tools_used and "chip_compare" in tools_used else TTL_CONVERSATIONAL

            entry = {
                "query": query,
                "vector": vec,
                "response": response,
                "tools_used": tools_used or [],
                "created_at": time.time(),
            }
            await self._redis.rpush(redis_key, json.dumps(entry, ensure_ascii=False))
            # Trim bucket + set TTL
            await self._redis.ltrim(redis_key, -BUCKET_SIZE, -1)
            await self._redis.expire(redis_key, ttl)
        except Exception:
            logger.warning("Semantic cache put failed", exc_info=True)

    async def invalidate_for_chip(self, part_number: str) -> None:
        """Publish a cache invalidation event for a specific chip."""
        try:
            await self._redis.publish(
                f"cache:invalidate:{part_number}",
                json.dumps({"part_number": part_number, "timestamp": time.time()}),
            )
        except Exception:
            logger.warning("Cache invalidation publish failed", exc_info=True)
