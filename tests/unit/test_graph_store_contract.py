"""Contract tests for GraphStore — verify input/output shape matches BaseGraphStore."""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from src.libs.graph_store.base import BaseGraphStore
from src.libs.graph_store.kuzu_store import KuzuGraphStore
from src.libs.graph_store.factory import GraphStoreFactory


@pytest.mark.unit
class TestGraphStoreContract:
    """Verify KuzuGraphStore satisfies BaseGraphStore contract."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> KuzuGraphStore:
        s = KuzuGraphStore(db_path=str(tmp_path / "contract_db"))
        # Minimal schema
        s.execute_cypher(
            "CREATE NODE TABLE IF NOT EXISTS Chip "
            "(chip_id INT64, part_number STRING, manufacturer STRING, "
            "category STRING, family STRING, status STRING, PRIMARY KEY(chip_id))"
        )
        s.execute_cypher(
            "CREATE NODE TABLE IF NOT EXISTS Parameter "
            "(param_id INT64, name STRING, value STRING, unit STRING, PRIMARY KEY(param_id))"
        )
        s.execute_cypher("CREATE REL TABLE IF NOT EXISTS HAS_PARAM (FROM Chip TO Parameter)")
        s.execute_cypher(
            "CREATE REL TABLE IF NOT EXISTS ALTERNATIVE "
            "(FROM Chip TO Chip, compat_type STRING, compat_score DOUBLE, "
            "is_domestic BOOLEAN, key_differences STRING)"
        )
        return s

    def test_isinstance_base(self, store: KuzuGraphStore) -> None:
        assert isinstance(store, BaseGraphStore)

    def test_execute_cypher_returns_list_of_dicts(self, store: KuzuGraphStore) -> None:
        result = store.execute_cypher("RETURN 42 AS value")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["value"] == 42

    def test_upsert_node_idempotent(self, store: KuzuGraphStore) -> None:
        props = {"chip_id": 1, "part_number": "STM32F407", "manufacturer": "ST",
                 "category": "MCU", "family": "STM32F4", "status": "active"}
        store.upsert_node("Chip", props, key_field="chip_id")
        store.upsert_node("Chip", props, key_field="chip_id")
        rows = store.execute_cypher(
            "MATCH (c:Chip) WHERE c.chip_id = 1 RETURN c.part_number AS pn"
        )
        assert len(rows) == 1
        assert rows[0]["pn"] == "STM32F407"

    def test_upsert_edge_with_properties(self, store: KuzuGraphStore) -> None:
        store.upsert_node("Chip", {"chip_id": 1, "part_number": "STM32F407",
                                    "manufacturer": "ST", "category": "", "family": "", "status": ""},
                          key_field="chip_id")
        store.upsert_node("Chip", {"chip_id": 2, "part_number": "GD32F407",
                                    "manufacturer": "GigaDevice", "category": "", "family": "", "status": ""},
                          key_field="chip_id")
        store.upsert_edge(
            "ALTERNATIVE", "Chip", 1, "Chip", 2,
            properties={"compat_type": "pin-compatible", "compat_score": 0.85,
                        "is_domestic": True, "key_differences": "Flash timing"},
            from_key_field="chip_id", to_key_field="chip_id",
        )
        rows = store.execute_cypher(
            "MATCH (a:Chip)-[r:ALTERNATIVE]->(b:Chip) "
            "WHERE a.chip_id = 1 RETURN r.compat_score AS score"
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(0.85)

    def test_execute_cypher_returns_correct_columns(self, store: KuzuGraphStore) -> None:
        store.upsert_node("Chip", {"chip_id": 10, "part_number": "ESP32",
                                    "manufacturer": "Espressif", "category": "", "family": "", "status": ""},
                          key_field="chip_id")
        rows = store.execute_cypher(
            "MATCH (c:Chip) WHERE c.chip_id = 10 RETURN c.part_number AS pn, c.manufacturer AS mfr"
        )
        assert len(rows) == 1
        assert "pn" in rows[0]
        assert "mfr" in rows[0]

    def test_get_subgraph_returns_list(self, store: KuzuGraphStore) -> None:
        store.upsert_node("Chip", {"chip_id": 100, "part_number": "A", "manufacturer": "X",
                                    "category": "", "family": "", "status": ""},
                          key_field="chip_id")
        store.upsert_node("Parameter", {"param_id": 200, "name": "Vcc", "value": "3.3", "unit": "V"},
                          key_field="param_id")
        store.upsert_edge("HAS_PARAM", "Chip", 100, "Parameter", 200,
                          from_key_field="chip_id", to_key_field="param_id")
        result = store.get_subgraph("Chip", 100, max_hops=1, key_field="chip_id")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_health_check_returns_bool(self, store: KuzuGraphStore) -> None:
        assert store.health_check() is True

    def test_close_invalidates(self, store: KuzuGraphStore) -> None:
        store.close()
        assert store.health_check() is False

    def test_factory_creates_kuzu(self, tmp_path: Path) -> None:
        config = {"graph_store": {"backend": "kuzu", "db_path": str(tmp_path / "factory_test")}}
        s = GraphStoreFactory.create(config)
        assert isinstance(s, KuzuGraphStore)
        assert s.health_check() is True
        s.close()
