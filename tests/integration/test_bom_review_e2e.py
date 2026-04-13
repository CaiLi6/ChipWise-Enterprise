"""Integration test for BOMReviewTool against real PG (§4C1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.agent.tools.bom_review import BOMReviewTool

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_bom.xlsx"


@pytest.fixture
def pg_dsn() -> str:
    return os.environ.get(
        "PG_DSN", "postgresql://chipwise:chipwise@localhost:5432/chipwise"
    )


@pytest.fixture
async def pg_pool(pg_dsn: str):
    asyncpg = pytest.importorskip("asyncpg")
    try:
        pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=2)
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_bom_review_from_excel(pg_pool) -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture missing: {FIXTURE}")

    tool = BOMReviewTool(db_pool=pg_pool)
    result = await tool.execute(file_path=str(FIXTURE))

    assert "bom_review" in result
    summary = result["bom_review"]
    assert summary["total_items"] >= 1
    assert summary["matched"] + summary["unmatched"] == summary["total_items"]
    assert "items" in result


@pytest.mark.asyncio
async def test_bom_review_empty_fallback() -> None:
    tool = BOMReviewTool(db_pool=None)
    result = await tool.execute()
    assert "error" in result
