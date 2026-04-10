"""Chip comparison API endpoint (§4A2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["compare"])


class CompareRequest(BaseModel):
    chip_names: list[str] = Field(..., min_length=2, max_length=5)
    dimensions: list[str] | None = None


class CompareResponse(BaseModel):
    comparison_table: dict[str, Any] = {}
    analysis: str = ""
    chips: list[str] = []
    citations: list[Any] = []


@router.post("/compare", response_model=CompareResponse)
async def compare_chips(req: CompareRequest) -> CompareResponse:
    """Direct chip comparison endpoint (bypasses Agent orchestrator)."""
    # In production, inject ChipCompareTool via DI
    from src.agent.tools.chip_compare import ChipCompareTool

    tool = ChipCompareTool()
    result = await tool.execute(
        chip_names=req.chip_names, dimensions=req.dimensions
    )

    if "error" in result:
        return CompareResponse(analysis=result["error"])

    return CompareResponse(**result)
