"""Governed user/project memories with candidate/confirmed/rejected status."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

VALID_STATUSES = {"candidate", "confirmed", "rejected"}
VALID_SCOPES = {"user", "project"}

_EXPLICIT_MEMORY = re.compile(r"记住|请记住|以后|remember|from now on|going forward", re.IGNORECASE)


@dataclass
class GovernedMemory:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    scope: str = "user"
    owner_key: str | None = None
    kind: str = "note"
    content: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "manual"
    source_id: str | None = None
    status: str = "candidate"
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryGovernanceStore:
    """CRUD for governed memories. All methods degrade to empty/no-op without DB."""

    def __init__(self, db_pool: Any = None) -> None:
        self._pool = db_pool

    async def create_memory(self, memory: GovernedMemory) -> str | None:
        if self._pool is None:
            return None
        if memory.scope not in VALID_SCOPES or memory.status not in VALID_STATUSES:
            raise ValueError("Invalid memory scope or status")
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_records
                        (id, scope, owner_key, kind, content, tags, source,
                         source_id, status, metadata)
                    VALUES
                        ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    memory.id,
                    memory.scope,
                    memory.owner_key,
                    memory.kind,
                    memory.content,
                    json.dumps(memory.tags, ensure_ascii=False),
                    memory.source,
                    memory.source_id,
                    memory.status,
                    json.dumps(memory.metadata, ensure_ascii=False),
                )
            return memory.id
        except Exception:
            logger.warning("Failed to create governed memory", exc_info=True)
            return None

    async def list_memories(
        self,
        *,
        scope: str | None = None,
        owner_key: str | None = None,
        status: str | None = "confirmed",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self._pool is None:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if scope:
            params.append(scope)
            clauses.append(f"scope = ${len(params)}")
        if owner_key:
            params.append(owner_key)
            clauses.append(f"(owner_key = ${len(params)} OR scope = 'project')")
        if status:
            params.append(status)
            clauses.append(f"status = ${len(params)}")
        params.append(limit)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT id, scope, owner_key, kind, content, tags, source,
                           source_id, status, metadata, use_count, last_used_at,
                           created_at, updated_at
                    FROM memory_records
                    {where}
                    ORDER BY updated_at DESC
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
            return [dict(row) for row in rows]
        except Exception:
            logger.warning("Failed to list governed memories", exc_info=True)
            return []

    async def update_status(self, memory_id: str, status: str) -> bool:
        if self._pool is None:
            return False
        if status not in VALID_STATUSES:
            raise ValueError("Invalid memory status")
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE memory_records SET status=$1, updated_at=now() WHERE id=$2",
                    status,
                    memory_id,
                )
            return not str(result).endswith(" 0")
        except Exception:
            logger.warning("Failed to update governed memory", exc_info=True)
            return False

    async def delete_memory(self, memory_id: str) -> bool:
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute("DELETE FROM memory_records WHERE id=$1", memory_id)
            return not str(result).endswith(" 0")
        except Exception:
            logger.warning("Failed to delete governed memory", exc_info=True)
            return False


def explicit_memory_from_query(query: str, *, owner_key: str, trace_id: str) -> GovernedMemory | None:
    """Convert explicit user 'remember this' requests into confirmed user memories."""
    if not _EXPLICIT_MEMORY.search(query):
        return None
    content = query.strip()
    if not content:
        return None
    return GovernedMemory(
        scope="user",
        owner_key=owner_key,
        kind="preference" if any(word in content for word in ("以后", "默认", "prefer", "always")) else "note",
        content=content[:1000],
        tags=["explicit"],
        source="user_explicit",
        source_id=trace_id,
        status="confirmed",
        metadata={"captured_from": "query"},
    )
