"""Kùzu embedded graph store implementation (§4.7.4)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import kuzu

from .base import BaseGraphStore

logger = logging.getLogger(__name__)


class KuzuGraphStore(BaseGraphStore):
    """Kùzu embedded graph database backend.

    Kùzu runs in-process — no separate server or port required.
    Data is persisted to *db_path* on disk.
    """

    def __init__(self, db_path: str = "data/kuzu", read_only: bool = False) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(path), read_only=read_only)
        self._conn = kuzu.Connection(self._db)
        logger.info("KuzuGraphStore opened at %s", db_path)

    # ------------------------------------------------------------------
    # BaseGraphStore interface
    # ------------------------------------------------------------------

    def execute_cypher(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = self._conn.execute(query, parameters or {})
        rows: list[dict[str, Any]] = []
        columns = result.get_column_names()
        while result.has_next():
            values = result.get_next()
            rows.append(dict(zip(columns, values)))
        return rows

    def upsert_node(self, label: str, properties: dict[str, Any], key_field: str = "id") -> None:
        key_value = properties[key_field]
        set_parts = [f"n.{k} = ${k}" for k in properties if k != key_field]
        set_clause = f" SET {', '.join(set_parts)}" if set_parts else ""
        cypher = f"MERGE (n:{label} {{{key_field}: ${key_field}}}){set_clause}"
        self._conn.execute(cypher, properties)

    def upsert_edge(
        self,
        rel_type: str,
        from_label: str,
        from_key: Any,
        to_label: str,
        to_key: Any,
        properties: dict[str, Any] | None = None,
        from_key_field: str = "id",
        to_key_field: str = "id",
    ) -> None:
        params: dict[str, Any] = {"from_key": from_key, "to_key": to_key}
        match_clause = (
            f"MATCH (a:{from_label} {{{from_key_field}: $from_key}}), "
            f"(b:{to_label} {{{to_key_field}: $to_key}})"
        )
        merge_clause = f"MERGE (a)-[r:{rel_type}]->(b)"
        if properties:
            set_parts = [f"r.{k} = ${k}" for k in properties]
            merge_clause += f" SET {', '.join(set_parts)}"
            params.update(properties)
        cypher = f"{match_clause} {merge_clause}"
        self._conn.execute(cypher, params)

    def get_subgraph(
        self,
        start_label: str,
        start_key: Any,
        max_hops: int = 2,
        key_field: str = "id",
    ) -> list[dict[str, Any]]:
        # Use WHERE instead of inline property (avoids issues with some Kùzu versions)
        # 'end' is reserved, use 'dest' as alias
        cypher = (
            f"MATCH (src:{start_label})-[*1..{max_hops}]->(dest) "
            f"WHERE src.{key_field} = $key "
            f"RETURN src, dest"
        )
        return self.execute_cypher(cypher, {"key": start_key})

    def health_check(self) -> bool:
        try:
            self._conn.execute("RETURN 1")
            return True
        except Exception:
            logger.exception("Kùzu health check failed")
            return False

    def close(self) -> None:
        # Kùzu Python binding handles cleanup via __del__
        self._conn = None  # type: ignore[assignment]
        self._db = None  # type: ignore[assignment]
        logger.info("KuzuGraphStore closed")
