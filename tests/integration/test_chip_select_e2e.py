"""Integration test for ChipSelectTool against real PG (§4B1)."""

from __future__ import annotations

import os

import pytest

from src.agent.tools.chip_select import ChipSelectTool


pytestmark = pytest.mark.integration


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
async def test_filter_by_category(pg_pool) -> None:
    tool = ChipSelectTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(criteria={"category": "MCU"}, top_k=5)
    assert "candidates" in result
    assert isinstance(result["candidates"], list)


@pytest.mark.asyncio
async def test_no_match_returns_empty(pg_pool) -> None:
    tool = ChipSelectTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(
        criteria={"manufacturer": "__NONE__"}, top_k=5
    )
    assert result["total"] == 0
    assert "message" in result


@pytest.mark.asyncio
async def test_include_domestic(pg_pool) -> None:
    tool = ChipSelectTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(
        criteria={"category": "MCU"}, include_domestic=True, top_k=3
    )
    assert "candidates" in result
    if result["candidates"]:
        assert "domestic_alternatives" in result["candidates"][0]
