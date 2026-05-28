"""Chip comparison API endpoint (§4A2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.agent.tools.chip_compare import ChipCompareTool
from src.api.dependencies import get_db_pool, get_settings
from src.api.schemas.compare import CompareRequest, CompareResponse

router = APIRouter(prefix="/api/v1", tags=["compare"])


def _create_compare_tool(db_pool: Any, settings: Any) -> ChipCompareTool:
    """Build ChipCompareTool with real dependencies (graceful on failure)."""
    from src.libs.embedding.factory import EmbeddingFactory
    from src.libs.llm.factory import LLMFactory
    from src.libs.vector_store.factory import VectorStoreFactory

    cfg = settings.model_dump()
    llm = None
    vector_store = None
    embedding = None

    try:
        llm = LLMFactory.create(cfg, role="primary")
    except Exception:
        pass
    try:
        embedding = EmbeddingFactory.create(cfg)
        vector_store = VectorStoreFactory.create(cfg)
    except Exception:
        pass

    return ChipCompareTool(
        db_pool=db_pool, llm=llm, vector_store=vector_store, embedding=embedding
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_chips(
    req: CompareRequest,
    db_pool: Any = Depends(get_db_pool),
    settings: Any = Depends(get_settings),
) -> CompareResponse:
    """Direct chip comparison endpoint (bypasses Agent orchestrator)."""
    tool = _create_compare_tool(db_pool, settings)
    result = await tool.execute(
        chip_names=req.chip_names, dimensions=req.dimensions
    )

    if "error" in result:
        return CompareResponse(analysis=result["error"])

    return CompareResponse(**result)
