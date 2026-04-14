"""Unit tests for SQLQueryTool and SQLSearch (task 2C6).

Acceptance criteria:
- SELECT with params returns rows + column_names
- Non-SELECT (INSERT/UPDATE/DELETE/DROP) rejected with clear error
- SQL injection mitigated by parameterized queries
- Empty result returns {rows: [], column_names: []}
- DB unavailable returns error
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agent.tools.sql_query import SQLQueryTool
from src.retrieval.sql_search import SQLSearch, SQLSearchError


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_mock_pool(rows: list[dict[str, Any]] | None = None, error: Exception | None = None) -> Any:
    """Create a mock asyncpg pool."""
    mock_conn = AsyncMock()
    if error:
        mock_conn.fetch.side_effect = error
    else:
        mock_conn.fetch.return_value = [
            MagicMock(**{"keys.return_value": list((rows or [{}])[0].keys()), **r})
            for r in (rows or [])
        ]
        # Make dict(row) work
        result_rows = []
        for r in (rows or []):
            mock_row = MagicMock()
            mock_row.__iter__ = MagicMock(return_value=iter(r.items()))
            mock_row.keys.return_value = list(r.keys())
            result_rows.append(mock_row)
        mock_conn.fetch.return_value = result_rows

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = cm
    return mock_pool


# ------------------------------------------------------------------
# SQLQueryTool tests
# ------------------------------------------------------------------
@pytest.mark.unit
class TestSQLQueryTool:
    def test_name(self) -> None:
        tool = SQLQueryTool()
        assert tool.name == "sql_query"

    def test_schema_has_sql(self) -> None:
        tool = SQLQueryTool()
        schema = tool.parameters_schema
        assert "sql" in schema["properties"]
        assert "sql" in schema["required"]

    @pytest.mark.asyncio
    async def test_no_pool_returns_error(self) -> None:
        tool = SQLQueryTool()
        result = await tool.execute(sql="SELECT 1")
        assert "error" in result
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_write_blocked_insert(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(sql="INSERT INTO chips VALUES (1, 'test')")
        assert "error" in result
        assert "Write" in result["error"]

    @pytest.mark.asyncio
    async def test_write_blocked_delete(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(sql="DELETE FROM chips WHERE id = 1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_write_blocked_drop(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(sql="DROP TABLE chips")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_write_blocked_update(self) -> None:
        tool = SQLQueryTool(db_pool=MagicMock())
        result = await tool.execute(sql="UPDATE chips SET name='x' WHERE id=1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_select_query_succeeds(self) -> None:
        """Mocked SQLSearch returns proper rows."""
        mock_search = AsyncMock(spec=SQLSearch)
        mock_search.execute.return_value = {
            "rows": [{"part_number": "STM32F407", "manufacturer": "ST"}],
            "column_names": ["part_number", "manufacturer"],
        }
        tool = SQLQueryTool(sql_search=mock_search)
        result = await tool.execute(sql="SELECT part_number FROM chips WHERE manufacturer = $1", params=["ST"])
        assert "rows" in result
        assert len(result["rows"]) == 1
        assert result["rows"][0]["part_number"] == "STM32F407"

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        mock_search = AsyncMock(spec=SQLSearch)
        mock_search.execute.return_value = {"rows": [], "column_names": ["part_number"]}
        tool = SQLQueryTool(sql_search=mock_search)
        result = await tool.execute(sql="SELECT part_number FROM chips WHERE 1=0")
        assert result["rows"] == []

    @pytest.mark.asyncio
    async def test_db_error_handled(self) -> None:
        mock_search = AsyncMock(spec=SQLSearch)
        mock_search.execute.side_effect = SQLSearchError("connection lost")
        tool = SQLQueryTool(sql_search=mock_search)
        result = await tool.execute(sql="SELECT 1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_backward_compat_query_param(self) -> None:
        """Tool also accepts 'query' kwarg for backward compat."""
        mock_search = AsyncMock(spec=SQLSearch)
        mock_search.execute.return_value = {"rows": [], "column_names": []}
        tool = SQLQueryTool(sql_search=mock_search)
        _result = await tool.execute(query="SELECT 1")
        mock_search.execute.assert_called_once()

    def test_openai_tool_format(self) -> None:
        tool = SQLQueryTool()
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "sql_query"


# ------------------------------------------------------------------
# SQLSearch tests
# ------------------------------------------------------------------
@pytest.mark.unit
class TestSQLSearch:
    @pytest.mark.asyncio
    async def test_write_rejected(self) -> None:
        search = SQLSearch(db_pool=MagicMock())
        with pytest.raises(ValueError, match="Write operations"):
            await search.execute("INSERT INTO chips VALUES (1)")

    @pytest.mark.asyncio
    async def test_write_rejected_drop(self) -> None:
        search = SQLSearch(db_pool=MagicMock())
        with pytest.raises(ValueError):
            await search.execute("DROP TABLE chips")

    @pytest.mark.asyncio
    async def test_sql_injection_blocked(self) -> None:
        """SQL injection via write keywords is blocked."""
        search = SQLSearch(db_pool=MagicMock())
        with pytest.raises(ValueError):
            await search.execute("SELECT 1; DELETE FROM chips")
