"""Memory governance API: episodes, user/project memories, approvals."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_db_pool
from src.api.middleware.auth import get_current_user
from src.api.schemas.auth import UserInfo
from src.core.episodic_memory import EpisodicMemoryStore
from src.core.memory_governance import VALID_STATUSES, GovernedMemory, MemoryGovernanceStore

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryCreateRequest(BaseModel):
    scope: str = Field(default="user", pattern="^(user|project)$")
    kind: str = "note"
    content: str = Field(..., min_length=1, max_length=5000)
    tags: list[str] = []
    status: str = Field(default="candidate", pattern="^(candidate|confirmed|rejected)$")
    metadata: dict[str, Any] = {}


class MemoryStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(candidate|confirmed|rejected)$")


def _user_key(user: UserInfo) -> str:
    return (user.sub or user.username or "anonymous").strip() or "anonymous"


def _require_db(db_pool: Any) -> Any:
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    return db_pool


@router.get("")
async def list_memories(
    scope: str | None = Query(None, pattern="^(user|project)$"),
    status: str | None = Query("confirmed", pattern="^(candidate|confirmed|rejected)$"),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """List confirmed/candidate/rejected memories visible to the current user."""
    store = MemoryGovernanceStore(_require_db(db_pool))
    records = await store.list_memories(
        scope=scope,
        owner_key=_user_key(current_user),
        status=status,
        limit=limit,
    )
    return {"memories": records, "total": len(records)}


@router.post("")
async def create_memory(
    req: MemoryCreateRequest,
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Create a governed memory. User-scoped memories are bound to current user."""
    owner_key = _user_key(current_user) if req.scope == "user" else None
    memory = GovernedMemory(
        scope=req.scope,
        owner_key=owner_key,
        kind=req.kind,
        content=req.content,
        tags=req.tags,
        source="manual",
        status=req.status,
        metadata=req.metadata,
    )
    memory_id = await MemoryGovernanceStore(_require_db(db_pool)).create_memory(memory)
    if memory_id is None:
        raise HTTPException(500, "Failed to create memory")
    return {"memory_id": memory_id, "status": req.status}


@router.patch("/{memory_id}/status")
async def update_memory_status(
    memory_id: str,
    req: MemoryStatusRequest,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Move a memory between candidate/confirmed/rejected states."""
    if req.status not in VALID_STATUSES:
        raise HTTPException(400, "Invalid memory status")
    ok = await MemoryGovernanceStore(_require_db(db_pool)).update_status(memory_id, req.status)
    if not ok:
        raise HTTPException(404, "Memory not found")
    return {"memory_id": memory_id, "status": req.status}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Delete a governed memory."""
    ok = await MemoryGovernanceStore(_require_db(db_pool)).delete_memory(memory_id)
    if not ok:
        raise HTTPException(404, "Memory not found")
    return {"memory_id": memory_id, "status": "deleted"}


@router.get("/episodes")
async def list_episodes(
    session_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """List recent query episodes for the current user."""
    episodes = await EpisodicMemoryStore(_require_db(db_pool)).list_episodes(
        user_key=_user_key(current_user),
        session_id=session_id,
        limit=limit,
    )
    return {"episodes": episodes, "total": len(episodes)}
