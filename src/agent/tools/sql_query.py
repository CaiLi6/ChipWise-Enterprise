"""SQL Query Agent Tool — parameterized PostgreSQL queries (§2C6)."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.retrieval.sql_search import SQLSearch, SQLSearchError

logger = logging.getLogger(__name__)

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLQueryTool(BaseTool):
    """Execute read-only parameterized SQL queries against PostgreSQL.

    Accepts either a ``SQLSearch`` instance or a raw ``asyncpg.Pool``.
    """

    def __init__(
        self,
        sql_search: SQLSearch | None = None,
        db_pool: Any = None,
    ) -> None:
        if sql_search is not None:
            self._search = sql_search
        elif db_pool is not None:
            self._search = SQLSearch(db_pool)
        else:
            self._search = None

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return (
            "Query the PostgreSQL database for chip parameters, document metadata, "
            "and structured data using parameterized SQL."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT query with $1, $2... parameter placeholders",
                },
                "params": {
                    "type": "array",
                    "items": {"type": ["string", "number", "boolean"]},
                    "description": "Parameters for the SQL query",
                },
            },
            "required": ["sql"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        sql = kwargs.get("sql", kwargs.get("query", ""))
        params = kwargs.get("params", [])

        # Security: block write operations
        if _WRITE_KEYWORDS.search(sql):
            return {"error": "Write operations are not allowed", "rows": [], "column_names": []}

        if self._search is None:
            return {"error": "Database connection not available", "rows": [], "column_names": []}

        try:
            result = await self._search.execute(sql, params)
            return result
        except ValueError as exc:
            return {"error": str(exc), "rows": [], "column_names": []}
        except SQLSearchError as exc:
            return {"error": str(exc), "rows": [], "column_names": []}
        except Exception as exc:
            logger.exception("SQL query failed")
            return {"error": str(exc), "rows": [], "column_names": []}
