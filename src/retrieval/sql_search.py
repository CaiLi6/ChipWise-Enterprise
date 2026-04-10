"""SQL Search — parameterized read-only PostgreSQL queries (§2C6).

Wraps asyncpg connection pool with safety checks (SELECT-only enforcement)
and returns structured results.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLSearchError(Exception):
    """Raised when a SQL search operation fails."""


class SQLSearch:
    """Execute read-only parameterized SQL queries against PostgreSQL.

    Args:
        db_pool: An ``asyncpg.Pool`` (or compatible async pool).
    """

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def execute(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run a SELECT query and return ``{rows, column_names}``.

        Raises:
            ValueError: If *sql* contains write keywords.
            SQLSearchError: If the query execution fails.
        """
        if _WRITE_KEYWORDS.search(sql):
            raise ValueError("Write operations are not allowed. Only SELECT queries are permitted.")

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *(params or []))
                if rows:
                    column_names = list(rows[0].keys())
                else:
                    column_names = []
                return {
                    "rows": [dict(row) for row in rows],
                    "column_names": column_names,
                }
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("SQL search query failed")
            raise SQLSearchError(str(exc)) from exc
