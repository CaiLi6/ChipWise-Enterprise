"""SQL Query Agent Tool — parameterized PostgreSQL queries (§2C6)."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.agent.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Blocked SQL keywords (write operations)
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLQueryTool(BaseTool):
    """Execute read-only parameterized SQL queries against PostgreSQL."""

    def __init__(self, db_pool: Any = None) -> None:
        self._pool = db_pool

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
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query with $1, $2... parameter placeholders",
                },
                "params": {
                    "type": "array",
                    "items": {"type": ["string", "number", "boolean"]},
                    "description": "Parameters for the SQL query",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        params = kwargs.get("params", [])

        # Security: block write operations
        if _WRITE_KEYWORDS.search(query):
            return {"error": "Write operations are not allowed", "results": []}

        if self._pool is None:
            return {"error": "Database connection not available", "results": []}

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                results = [dict(row) for row in rows]
                return {"results": results, "total": len(results)}
        except Exception as e:
            logger.exception("SQL query failed")
            return {"error": str(e), "results": []}
