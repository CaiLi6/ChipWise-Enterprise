"""Golden QA dataset router — CRUD + one-shot batch trigger."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from src.evaluation.golden import (
    GoldenQA,
    add_golden,
    delete_golden,
    get_golden,
    list_golden,
    update_golden,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/golden", tags=["golden"])


class GoldenCreate(BaseModel):
    question: str
    ground_truth_answer: str
    ground_truth_contexts: list[str] = Field(default_factory=list)
    chip_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_by: str = ""


class GoldenUpdate(BaseModel):
    question: str | None = None
    ground_truth_answer: str | None = None
    ground_truth_contexts: list[str] | None = None
    chip_ids: list[str] | None = None
    tags: list[str] | None = None


@router.get("")
async def api_list_golden() -> dict[str, Any]:
    rows = list_golden()
    return {"total": len(rows), "rows": rows}


@router.get("/{gid}")
async def api_get_golden(gid: str) -> dict[str, Any]:
    row = get_golden(gid)
    if not row:
        raise HTTPException(404, f"golden {gid} not found")
    return row


@router.post("")
async def api_add_golden(body: GoldenCreate = Body(...)) -> dict[str, Any]:  # noqa: B008
    rec = GoldenQA(
        question=body.question,
        ground_truth_answer=body.ground_truth_answer,
        ground_truth_contexts=body.ground_truth_contexts,
        chip_ids=body.chip_ids,
        tags=body.tags,
        created_by=body.created_by,
    )
    add_golden(rec)
    return rec.to_json()


@router.patch("/{gid}")
async def api_patch_golden(
    gid: str, body: GoldenUpdate = Body(...)  # noqa: B008
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    rec = update_golden(gid, updates)
    if rec is None:
        raise HTTPException(404, f"golden {gid} not found")
    return rec


@router.delete("/{gid}")
async def api_delete_golden(gid: str) -> dict[str, Any]:
    ok = delete_golden(gid)
    if not ok:
        raise HTTPException(404, f"golden {gid} not found")
    return {"ok": True, "id": gid}


class GoldenRunRequest(BaseModel):
    judge: str = Field("primary", description="primary | router")


@router.post("/run")
async def api_run_golden(
    body: GoldenRunRequest = Body(default=GoldenRunRequest(judge="primary")),  # noqa: B008
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Delegate to /evaluations/run with kind=golden."""

    from src.api.routers.evaluations import BatchRunRequest, trigger_run

    return await trigger_run(
        BatchRunRequest(kind="golden", judge=body.judge, limit=limit, concurrency=1)
    )


# Preserve the import so linters don't strip 'asyncio' (used indirectly elsewhere)
__all__ = ["router"]
