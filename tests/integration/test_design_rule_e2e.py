"""Integration test for DesignRuleCheckTool against real PG (§5B1)."""

from __future__ import annotations

import os

import pytest
from src.agent.tools.design_rule import DesignRuleCheckTool

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
async def test_design_rules_query(pg_pool) -> None:
    tool = DesignRuleCheckTool(db_pool=pg_pool)
    result = await tool.execute(chip_name="STM32F407")
    assert "design_rules" in result
    assert isinstance(result["design_rules"], list)


@pytest.mark.asyncio
async def test_errata_query(pg_pool) -> None:
    tool = DesignRuleCheckTool(db_pool=pg_pool)
    result = await tool.execute(chip_name="STM32F407")
    assert "errata" in result
    assert isinstance(result["errata"], list)


@pytest.mark.asyncio
async def test_unknown_chip_returns_empty_lists(pg_pool) -> None:
    tool = DesignRuleCheckTool(db_pool=pg_pool)
    result = await tool.execute(chip_name="__UNKNOWN_CHIP__")
    assert result["design_rules"] == []
    assert result["errata"] == []
