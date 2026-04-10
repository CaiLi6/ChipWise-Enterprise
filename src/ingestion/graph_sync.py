"""Graph Synchronizer — PG → Kùzu incremental sync (§3B3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.libs.graph_store.base import BaseGraphStore

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a graph sync operation."""

    nodes_created: int = 0
    edges_created: int = 0
    errors: list[str] = field(default_factory=list)


class GraphSynchronizer:
    """Sync chip data from PostgreSQL to Kùzu knowledge graph."""

    def __init__(self, db_pool: Any, graph_store: BaseGraphStore) -> None:
        self._pool = db_pool
        self._graph = graph_store

    async def sync_chip(self, chip_id: int) -> SyncResult:
        """Full sync for a single chip: nodes + edges."""
        result = SyncResult()

        try:
            async with self._pool.acquire() as conn:
                # Step 1: Chip node
                chip = await conn.fetchrow(
                    "SELECT * FROM chips WHERE chip_id = $1", chip_id
                )
                if not chip:
                    result.errors.append(f"Chip {chip_id} not found in PG")
                    return result

                chip_data = dict(chip)
                await self._graph.upsert_node("Chip", chip_data, key_field="chip_id")
                result.nodes_created += 1

                # Step 2: Parameters
                params = await conn.fetch(
                    "SELECT * FROM chip_parameters WHERE chip_id = $1", chip_id
                )
                for p in params:
                    p_data = dict(p)
                    await self._graph.upsert_node("Parameter", p_data, key_field="param_id")
                    result.nodes_created += 1
                    await self._graph.upsert_edge(
                        "Chip", chip_data.get("chip_id"),
                        "Parameter", p_data.get("param_id"),
                        "HAS_PARAM", {},
                    )
                    result.edges_created += 1

                # Step 3: Alternatives
                alts = await conn.fetch(
                    "SELECT * FROM chip_alternatives WHERE source_chip_id = $1", chip_id
                )
                for alt in alts:
                    await self._graph.upsert_edge(
                        "Chip", chip_id,
                        "Chip", alt["target_chip_id"],
                        "ALTERNATIVE", {"compatibility": alt.get("compatibility_level")},
                    )
                    result.edges_created += 1

                # Step 4: Errata
                errata = await conn.fetch(
                    "SELECT * FROM errata WHERE chip_id = $1", chip_id
                )
                for e in errata:
                    e_data = dict(e)
                    await self._graph.upsert_node("Errata", e_data, key_field="errata_id")
                    result.nodes_created += 1
                    await self._graph.upsert_edge(
                        "Chip", chip_id, "Errata", e_data.get("errata_id"),
                        "HAS_ERRATA", {},
                    )
                    result.edges_created += 1

                # Step 5: Design Rules
                rules = await conn.fetch(
                    "SELECT * FROM design_rules WHERE chip_id = $1", chip_id
                )
                for r in rules:
                    r_data = dict(r)
                    await self._graph.upsert_node("DesignRule", r_data, key_field="rule_id")
                    result.nodes_created += 1
                    await self._graph.upsert_edge(
                        "Chip", chip_id, "DesignRule", r_data.get("rule_id"),
                        "HAS_RULE", {},
                    )
                    result.edges_created += 1

                # Step 6: Documents
                docs = await conn.fetch(
                    "SELECT d.* FROM documents d "
                    "JOIN chip_documents cd ON d.doc_id = cd.doc_id "
                    "WHERE cd.chip_id = $1",
                    chip_id,
                )
                for d in docs:
                    d_data = dict(d)
                    await self._graph.upsert_node("Document", d_data, key_field="doc_id")
                    result.nodes_created += 1
                    await self._graph.upsert_edge(
                        "Chip", chip_id, "Document", d_data.get("doc_id"),
                        "DOCUMENTED_IN", {},
                    )
                    result.edges_created += 1

        except Exception as e:
            result.errors.append(str(e))
            logger.exception("Graph sync failed for chip %d", chip_id)

        return result
