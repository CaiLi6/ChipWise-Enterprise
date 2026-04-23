"""Graph Synchronizer — PG → Kùzu incremental sync (§3B3).

Maps PostgreSQL relational rows into Kùzu graph nodes and edges.

PG → Kùzu field mapping
-----------------------
chips.id              -> Chip.chip_id (INT64)
chips.part_number     -> Chip.part_number
chips.manufacturer    -> Chip.manufacturer
chips.category        -> Chip.category
chips.family          -> Chip.family
chips.status          -> Chip.status

chip_parameters.id              -> Parameter.param_id (INT64)
chip_parameters.parameter_name  -> Parameter.name
chip_parameters.parameter_category -> Parameter.category
chip_parameters.min_value       -> Parameter.min_val
chip_parameters.typ_value       -> Parameter.typ_val
chip_parameters.max_value       -> Parameter.max_val
chip_parameters.unit            -> Parameter.unit
chip_parameters.condition       -> Parameter.condition

errata.id          -> Errata.errata_id (INT64)
errata.errata_id   -> Errata.errata_code
errata.title/severity/workaround -> as named
errata.affected_rev -> Errata.affected_revisions

design_rules.id          -> DesignRule.rule_id (INT64)
design_rules.rule_type   -> DesignRule.rule_type
design_rules.description -> DesignRule.rule_text
design_rules.severity    -> DesignRule.severity
design_rules.source_page -> HAS_RULE.source_page

chip_alternatives.alt_id -> ALTERNATIVE edge target
chip_alternatives.compat_type -> ALTERNATIVE.compat_type
chip_alternatives.compat_score -> ALTERNATIVE.compat_score
chip_alternatives.notes -> ALTERNATIVE.key_differences
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.libs.graph_store.base import BaseGraphStore

logger = logging.getLogger(__name__)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_str(v: Any) -> str:
    return "" if v is None else str(v)


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_chip(self, chip_id: int) -> SyncResult:
        """Full sync for a single chip: nodes + edges."""
        result = SyncResult()
        try:
            async with self._pool.acquire() as conn:
                chip_row = await conn.fetchrow(
                    "SELECT id, part_number, manufacturer, category, family, status "
                    "FROM chips WHERE id = $1",
                    chip_id,
                )
                if chip_row is None:
                    result.errors.append(f"chip {chip_id} not found in PG")
                    return result

                self._upsert_chip(dict(chip_row), result)

                params = await conn.fetch(
                    "SELECT id, parameter_name, parameter_category, "
                    "min_value, typ_value, max_value, unit, condition, "
                    "source_page, source_table "
                    "FROM chip_parameters WHERE chip_id = $1",
                    chip_id,
                )
                for p in params:
                    self._upsert_param(chip_id, dict(p), result)

                rules = await conn.fetch(
                    "SELECT id, rule_type, description, severity, source_page, title "
                    "FROM design_rules WHERE chip_id = $1",
                    chip_id,
                )
                for r in rules:
                    self._upsert_rule(chip_id, dict(r), result)

                err_rows = await conn.fetch(
                    "SELECT id, errata_id, title, severity, workaround, "
                    "affected_rev "
                    "FROM errata WHERE chip_id = $1",
                    chip_id,
                )
                for e in err_rows:
                    self._upsert_errata(chip_id, dict(e), result)

                alts = await conn.fetch(
                    "SELECT alt_id, compat_type, compat_score, notes "
                    "FROM chip_alternatives WHERE original_id = $1",
                    chip_id,
                )
                for a in alts:
                    self._upsert_alternative_edge(chip_id, dict(a), result)

                docs = await conn.fetch(
                    "SELECT d.id, d.file_hash, d.doc_type, d.file_name "
                    "FROM documents d WHERE d.chip_id = $1",
                    chip_id,
                )
                for d in docs:
                    self._upsert_document(chip_id, dict(d), result)

        except Exception as e:  # pragma: no cover — defensive
            result.errors.append(str(e))
            logger.exception("Graph sync failed for chip %d", chip_id)

        return result

    # ------------------------------------------------------------------
    # Upserts (each maps PG → Kùzu schema)
    # ------------------------------------------------------------------

    def _upsert_chip(self, pg: dict[str, Any], result: SyncResult) -> None:
        node = {
            "chip_id": int(pg["id"]),
            "part_number": _to_str(pg.get("part_number")),
            "manufacturer": _to_str(pg.get("manufacturer")),
            "category": _to_str(pg.get("category")),
            "family": _to_str(pg.get("family")),
            "status": _to_str(pg.get("status")),
        }
        self._graph.upsert_node("Chip", node, key_field="chip_id")
        result.nodes_created += 1

    def _upsert_param(
        self, chip_id: int, pg: dict[str, Any], result: SyncResult
    ) -> None:
        node = {
            "param_id": int(pg["id"]),
            "name": _to_str(pg.get("parameter_name")),
            "category": _to_str(pg.get("parameter_category")),
            "min_val": _to_float(pg.get("min_value")) or 0.0,
            "typ_val": _to_float(pg.get("typ_value")) or 0.0,
            "max_val": _to_float(pg.get("max_value")) or 0.0,
            "unit": _to_str(pg.get("unit")),
            "condition": _to_str(pg.get("condition")),
        }
        self._graph.upsert_node("Parameter", node, key_field="param_id")
        result.nodes_created += 1

        edge_props = {
            "source_page": int(pg.get("source_page") or 0),
            "source_table": _to_str(pg.get("source_table")),
        }
        self._graph.upsert_edge(
            "HAS_PARAM",
            "Chip", chip_id,
            "Parameter", int(pg["id"]),
            edge_props,
            from_key_field="chip_id",
            to_key_field="param_id",
        )
        result.edges_created += 1

    def _upsert_rule(
        self, chip_id: int, pg: dict[str, Any], result: SyncResult
    ) -> None:
        node = {
            "rule_id": int(pg["id"]),
            "rule_type": _to_str(pg.get("rule_type")),
            "rule_text": _to_str(pg.get("description") or pg.get("title")),
            "severity": _to_str(pg.get("severity")),
        }
        self._graph.upsert_node("DesignRule", node, key_field="rule_id")
        result.nodes_created += 1

        self._graph.upsert_edge(
            "HAS_RULE",
            "Chip", chip_id,
            "DesignRule", int(pg["id"]),
            {"source_page": int(pg.get("source_page") or 0)},
            from_key_field="chip_id",
            to_key_field="rule_id",
        )
        result.edges_created += 1

    def _upsert_errata(
        self, chip_id: int, pg: dict[str, Any], result: SyncResult
    ) -> None:
        node = {
            "errata_id": int(pg["id"]),
            "errata_code": _to_str(pg.get("errata_id")),
            "title": _to_str(pg.get("title")),
            "severity": _to_str(pg.get("severity")),
            "status": "open",
            "workaround": _to_str(pg.get("workaround")),
            "affected_revisions": _to_str(pg.get("affected_rev")),
        }
        self._graph.upsert_node("Errata", node, key_field="errata_id")
        result.nodes_created += 1

        self._graph.upsert_edge(
            "HAS_ERRATA",
            "Chip", chip_id,
            "Errata", int(pg["id"]),
            None,
            from_key_field="chip_id",
            to_key_field="errata_id",
        )
        result.edges_created += 1

    def _upsert_alternative_edge(
        self, chip_id: int, pg: dict[str, Any], result: SyncResult
    ) -> None:
        try:
            alt_id = int(pg["alt_id"])
        except Exception:
            return
        # NB: assumes the alternative chip already has a Chip node;
        # if missing, MERGE in upsert_edge would silently fail (no MATCH).
        # Caller must ensure both ends exist — sync_chip is invoked for each.
        self._graph.upsert_edge(
            "ALTERNATIVE",
            "Chip", chip_id,
            "Chip", alt_id,
            {
                "compat_type": _to_str(pg.get("compat_type")),
                "compat_score": _to_float(pg.get("compat_score")) or 0.0,
                "is_domestic": False,
                "key_differences": _to_str(pg.get("notes")),
            },
            from_key_field="chip_id",
            to_key_field="chip_id",
        )
        result.edges_created += 1

    def _upsert_document(
        self, chip_id: int, pg: dict[str, Any], result: SyncResult
    ) -> None:
        node = {
            "doc_id": int(pg["id"]),
            "file_hash": _to_str(pg.get("file_hash")),
            "doc_type": _to_str(pg.get("doc_type")),
            "file_name": _to_str(pg.get("file_name")),
        }
        self._graph.upsert_node("Document", node, key_field="doc_id")
        result.nodes_created += 1

        self._graph.upsert_edge(
            "DOCUMENTED_IN",
            "Chip", chip_id,
            "Document", int(pg["id"]),
            None,
            from_key_field="chip_id",
            to_key_field="doc_id",
        )
        result.edges_created += 1
