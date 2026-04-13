"""Integration test for TestCaseGenTool against real PG (§5A1)."""

from __future__ import annotations

import os

import pytest

from src.agent.tools.test_case_gen import TestCaseGenTool


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
async def test_params_fetched_from_pg(pg_pool) -> None:
    tool = TestCaseGenTool(db_pool=pg_pool, llm=None)
    params = await tool._get_params("STM32F407")
    # May be empty if chip not seeded — just verify no exception
    assert isinstance(params, list)


@pytest.mark.asyncio
async def test_no_llm_returns_error_gracefully(pg_pool) -> None:
    tool = TestCaseGenTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(chip_name="STM32F407")
    assert "error" in result


@pytest.mark.asyncio
async def test_unknown_chip_returns_error(pg_pool) -> None:
    tool = TestCaseGenTool(db_pool=pg_pool, llm=None)
    result = await tool.execute(chip_name="__NONEXISTENT_CHIP__")
    assert "error" in result
