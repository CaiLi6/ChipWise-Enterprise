"""Chips listing API — exposes the PG ``chips`` table for frontend pickers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chips", tags=["chips"])


@router.get("")
async def list_chips(
    q: str | None = Query(default=None, description="Substring search on part_number"),
    limit: int = Query(default=50, ge=1, le=500),
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """List chips for frontend pickers (compare page, query suggestions, ...).

    Matches both primary chips ingested by the upload pipeline and any
    co-mentioned chips registered by ``_store_co_mentioned_chips``.
    """
    if db_pool is None:
        return {"chips": [], "total": 0}
    try:
        async with db_pool.acquire() as conn:
            if q:
                pattern = f"%{q.upper()}%"
                rows = await conn.fetch(
                    """
                    SELECT id, part_number, manufacturer, family, status,
                           (SELECT COUNT(*) FROM chip_parameters cp
                                WHERE cp.chip_id = chips.id) AS param_count
                    FROM chips
                    WHERE upper(part_number) LIKE $1
                    ORDER BY param_count DESC, part_number ASC
                    LIMIT $2
                    """,
                    pattern, limit,
                )
                total = len(rows)
            else:
                total_row = await conn.fetchrow("SELECT COUNT(*) AS n FROM chips")
                total = int(total_row["n"]) if total_row else 0
                rows = await conn.fetch(
                    """
                    SELECT id, part_number, manufacturer, family, status,
                           (SELECT COUNT(*) FROM chip_parameters cp
                                WHERE cp.chip_id = chips.id) AS param_count
                    FROM chips
                    ORDER BY param_count DESC, part_number ASC
                    LIMIT $1
                    """,
                    limit,
                )
    except Exception as exc:
        logger.error("Failed to list chips: %s", exc, exc_info=True)
        raise HTTPException(503, "Database unavailable") from exc

    return {
        "chips": [
            {
                "chip_id": r["id"],
                "part_number": r["part_number"],
                "manufacturer": r["manufacturer"],
                "family": r["family"],
                "status": r["status"],
                "param_count": int(r["param_count"] or 0),
            }
            for r in rows
        ],
        "total": total,
    }
