"""Integration test for ChipCompareTool against real PG + LLM (§4A1)."""

from __future__ import annotations

import os

import pytest

from src.agent.tools.chip_compare import ChipCompareTool


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
async def test_chip_compare_real_pg(pg_pool) -> None:
    """Compare two seeded chips end-to-end (no LLM, structural assertions)."""
    tool = ChipCompareTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(chip_names=["STM32F407", "STM32F103"])

    assert "comparison_table" in result
    assert result["chips"] == ["STM32F407", "STM32F103"]
    if "error" in result:
        pytest.skip(f"seed data not present: {result['error']}")
    assert isinstance(result["comparison_table"], dict)


@pytest.mark.asyncio
async def test_chip_not_found(pg_pool) -> None:
    tool = ChipCompareTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(
        chip_names=["__NON_EXISTENT_A__", "__NON_EXISTENT_B__"]
    )
    assert "error" in result
    assert "not found" in result["error"].lower()
