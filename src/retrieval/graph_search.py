"""Graph search: Kùzu query patterns for chip intelligence (§2B2)."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.libs.graph_store.base import BaseGraphStore

logger = logging.getLogger(__name__)

# Disallowed Cypher keywords for custom queries (read-only enforcement)
_WRITE_KEYWORDS = re.compile(r"\b(CREATE|DELETE|SET|REMOVE|MERGE|DROP|ALTER)\b", re.IGNORECASE)


class GraphSearch:
    """High-level query patterns over the Kùzu knowledge graph."""

    def __init__(self, graph_store: BaseGraphStore) -> None:
        self._store = graph_store

    async def find_alternatives(
        self, part_number: str, include_domestic: bool = False
    ) -> list[dict[str, Any]]:
        """Find alternative chips for a given part number."""
        base_query = (
            "MATCH (c:Chip)-[a:ALTERNATIVE]->(alt:Chip) "
            "WHERE c.part_number = $pn "
        )
        if not include_domestic:
            base_query += "AND (a.is_domestic IS NULL OR a.is_domestic = false) "
        base_query += (
            "RETURN alt.part_number AS part_number, alt.manufacturer AS manufacturer, "
            "a.compat_score AS score, a.compat_type AS compat_type, "
            "a.key_differences AS differences"
        )
        return self._store.execute_cypher(base_query, {"pn": part_number})

    async def find_errata_by_peripheral(
        self, part_number: str, peripheral: str
    ) -> list[dict[str, Any]]:
        """3-hop: Chip → Errata → Peripheral."""
        query = (
            "MATCH (c:Chip)-[:HAS_ERRATA]->(e:Errata)-[:ERRATA_AFFECTS]->(p:Peripheral) "
            "WHERE c.part_number = $pn AND p.name = $periph "
            "RETURN e.errata_code AS code, e.title AS title, "
            "e.severity AS severity, e.workaround AS workaround"
        )
        return self._store.execute_cypher(query, {"pn": part_number, "periph": peripheral})

    async def get_chip_subgraph(
        self, part_number: str, max_depth: int = 2
    ) -> list[dict[str, Any]]:
        """Return the full subgraph around a chip."""
        return self._store.get_subgraph(
            "Chip", part_number, max_hops=max_depth, key_field="part_number"
        )

    async def param_range_search(
        self, param_name: str, min_val: float, max_val: float
    ) -> list[dict[str, Any]]:
        """Find chips with a parameter in the given range."""
        query = (
            "MATCH (c:Chip)-[:HAS_PARAM]->(p:Parameter) "
            "WHERE p.name = $pname AND p.typ_val >= $min_val AND p.typ_val <= $max_val "
            "RETURN c.part_number AS part_number, c.manufacturer AS manufacturer, "
            "p.name AS param, p.typ_val AS value, p.unit AS unit"
        )
        return self._store.execute_cypher(
            query, {"pname": param_name, "min_val": min_val, "max_val": max_val}
        )

    async def execute_custom_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only custom Cypher query.

        Raises ValueError if query contains write keywords.
        """
        if _WRITE_KEYWORDS.search(query):
            raise ValueError("Write operations are not allowed in custom Cypher queries")
        return self._store.execute_cypher(query, params)
