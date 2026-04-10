"""ConversationManager — Redis-backed multi-turn session management (§2D1)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 minutes
MAX_TURNS = 10


class ConversationManager:
    """Manages per-user conversation history in Redis.

    Key format: ``session:{user_id}:{session_id}`` — stores a JSON list of turns.
    Each turn: ``{"role": "user"|"assistant", "content": "..."}``.
    Auto-truncates to MAX_TURNS and refreshes TTL on every write.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    def _key(self, user_id: int, session_id: str) -> str:
        return f"session:{user_id}:{session_id}"

    async def get_history(self, user_id: int, session_id: str) -> list[dict[str, str]]:
        """Return conversation history (up to MAX_TURNS most recent)."""
        raw = await self._redis.get(self._key(user_id, session_id))
        if raw is None:
            return []
        try:
            turns: list[dict[str, str]] = json.loads(raw)
            return turns[-MAX_TURNS:]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt session data for %s:%s", user_id, session_id)
            return []

    async def append_turn(
        self, user_id: int, session_id: str, role: str, content: str
    ) -> None:
        """Append a turn and truncate to MAX_TURNS. Refreshes TTL."""
        key = self._key(user_id, session_id)
        history = await self.get_history(user_id, session_id)
        history.append({"role": role, "content": content})
        history = history[-MAX_TURNS:]
        await self._redis.set(key, json.dumps(history, ensure_ascii=False), ex=SESSION_TTL)

    async def clear_session(self, user_id: int, session_id: str) -> None:
        """Delete a session."""
        await self._redis.delete(self._key(user_id, session_id))
