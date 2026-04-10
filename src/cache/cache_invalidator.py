"""CacheInvalidator — Redis PubSub listener for cache eviction (§2D3)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CacheInvalidator:
    """Subscribe to Redis PubSub for cache invalidation events.

    Listens on ``cache:invalidate:*`` channels and deletes matching buckets.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._running = False

    async def subscribe(self) -> None:
        """Start listening for invalidation messages (runs as background task)."""
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("cache:invalidate:*")
        self._running = True

        async for message in pubsub.listen():
            if not self._running:
                break
            if message["type"] == "pmessage":
                await self.on_message(message)

    async def on_message(self, message: dict[str, Any]) -> None:
        """Handle an invalidation message by scanning and deleting matching keys."""
        try:
            data = json.loads(message.get("data", "{}"))
            part_number = data.get("part_number", "")
            if not part_number:
                return

            # Scan all gptcache buckets and remove entries matching the part number
            cursor = "0"
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match="gptcache:bucket:*", count=100
                )
                for key in keys:
                    entries = await self._redis.lrange(key, 0, -1)
                    remaining = []
                    for raw in entries:
                        entry = json.loads(raw)
                        if part_number.lower() not in entry.get("query", "").lower():
                            remaining.append(raw)
                    if len(remaining) < len(entries):
                        async with self._redis.pipeline() as pipe:
                            await pipe.delete(key)
                            for r in remaining:
                                await pipe.rpush(key, r)
                            await pipe.execute()
                if cursor == "0" or cursor == 0:
                    break

            logger.info("Invalidated cache entries for chip %s", part_number)
        except Exception:
            logger.warning("Cache invalidation handler failed", exc_info=True)

    def stop(self) -> None:
        """Signal the subscriber loop to stop."""
        self._running = False
