"""Chip comparison API endpoint (§4A2)."""

from __future__ import annotations

from fastapi import APIRouter

from src.agent.tools.chip_compare import ChipCompareTool
from src.api.schemas.compare import CompareRequest, CompareResponse

router = APIRouter(prefix="/api/v1", tags=["compare"])


@router.post("/compare", response_model=CompareResponse)
async def compare_chips(req: CompareRequest) -> CompareResponse:
    """Direct chip comparison endpoint (bypasses Agent orchestrator).

    JWT auth is enforced by the global middleware (see src/api/middleware/auth.py).
    """
    tool = ChipCompareTool()
    result = await tool.execute(
        chip_names=req.chip_names, dimensions=req.dimensions
    )

    if "error" in result:
        return CompareResponse(analysis=result["error"])

    return CompareResponse(**result)
