"""Episodic memory: structured records of query/tool/outcome events."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryEpisode:
    """One query episode suitable for replay, learning, and audit."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    user_key: str = ""
    session_id: str = ""
    trace_id: str = ""
    query_text: str = ""
    rewritten_query: str = ""
    tools_used: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    grounding: dict[str, Any] = field(default_factory=dict)
    eval_metrics: dict[str, float | None] = field(default_factory=dict)
    answer_preview: str = ""
    outcome: str = "success"
    created_at: float = field(default_factory=time.time)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


class EpisodicMemoryStore:
    """PostgreSQL-backed episodic memory with no-op degradation."""

    def __init__(self, db_pool: Any = None) -> None:
        self._pool = db_pool

    async def record_episode(self, episode: MemoryEpisode) -> str | None:
        if self._pool is None:
            return None
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_episodes
                        (id, user_key, session_id, trace_id, query_text, rewritten_query,
                         tools_used, citations, grounding, eval_metrics, answer_preview,
                         outcome)
                    VALUES
                        ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb,
                         $9::jsonb, $10::jsonb, $11, $12)
                    """,
                    episode.id,
                    episode.user_key,
                    episode.session_id,
                    episode.trace_id,
                    episode.query_text,
                    episode.rewritten_query,
                    json.dumps(episode.tools_used, ensure_ascii=False),
                    json.dumps(episode.citations[:20], ensure_ascii=False),
                    json.dumps(episode.grounding, ensure_ascii=False),
                    json.dumps(episode.eval_metrics, ensure_ascii=False),
                    episode.answer_preview[:1000],
                    episode.outcome,
                )
            return episode.id
        except Exception:
            logger.warning("Failed to record memory episode", exc_info=True)
            return None

    async def list_episodes(
        self,
        *,
        user_key: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self._pool is None:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if user_key:
            params.append(user_key)
            clauses.append(f"user_key = ${len(params)}")
        if session_id:
            params.append(session_id)
            clauses.append(f"session_id = ${len(params)}")
        params.append(limit)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT id, user_key, session_id, trace_id, query_text,
                           rewritten_query, tools_used, citations, grounding,
                           eval_metrics, answer_preview, outcome, created_at
                    FROM memory_episodes
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
            return [dict(row) for row in rows]
        except Exception:
            logger.warning("Failed to list memory episodes", exc_info=True)
            return []
