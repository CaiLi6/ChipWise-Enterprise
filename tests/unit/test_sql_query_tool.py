"""Unit tests for SQLQueryTool."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.tools.sql_query import SQLQueryTool


@pytest.mark.unit
class TestSQLQueryTool:
    def test_name(self) -> None:
        tool = SQLQueryTool()
        assert tool.name == "sql_query"

    def test_schema_has_query(self) -> None:
        tool = SQLQueryTool()
        schema = tool.parameters_schema
        assert "query" in schema["properties"]

    @pytest.mark.asyncio
    async def test_no_pool_returns_error(self) -> None:
        tool = SQLQueryTool(db_pool=None)
        result = await tool.execute(query="SELECT 1")
        assert "error" in result
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_write_blocked_insert(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(query="INSERT INTO chips VALUES (1, 'test')")
        assert "error" in result
        assert "Write" in result["error"]

    @pytest.mark.asyncio
    async def test_write_blocked_delete(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(query="DELETE FROM chips WHERE id = 1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_write_blocked_drop(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(query="DROP TABLE chips")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_select_with_mock_pool(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"chip_id": 1, "name": "STM32F407"},
        ]
        # acquire() must return a sync context manager wrapping the connection
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = cm

        tool = SQLQueryTool(db_pool=mock_pool)
        result = await tool.execute(query="SELECT * FROM chips WHERE chip_id = $1", params=[1])
        assert result["total"] == 1
        assert result["results"][0]["name"] == "STM32F407"

    @pytest.mark.asyncio
    async def test_db_error_handled(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = Exception("connection lost")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = cm

        tool = SQLQueryTool(db_pool=mock_pool)
        result = await tool.execute(query="SELECT 1")
        assert "error" in result
