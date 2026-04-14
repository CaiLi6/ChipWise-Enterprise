"""Unit tests for graph_store: BaseGraphStore, KuzuGraphStore, GraphStoreFactory."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.libs.graph_store.base import BaseGraphStore
from src.libs.graph_store.factory import GraphStoreFactory
from src.libs.graph_store.kuzu_store import KuzuGraphStore


@pytest.mark.unit
class TestKuzuGraphStore:
    """Tests using a real embedded Kùzu instance (no external service)."""

    @pytest.fixture(autouse=True)
    def setup_store(self, tmp_path: Path) -> None:
        self.db_path = str(tmp_path / "test_gs")
        self.store = KuzuGraphStore(db_path=self.db_path)
        # Create minimal schema for testing
        self.store.execute_cypher(
            "CREATE NODE TABLE IF NOT EXISTS Chip "
            "(chip_id STRING, name STRING, manufacturer STRING, PRIMARY KEY(chip_id))"
        )
        self.store.execute_cypher(
            "CREATE NODE TABLE IF NOT EXISTS Parameter "
            "(param_id STRING, name STRING, value STRING, unit STRING, PRIMARY KEY(param_id))"
        )
        self.store.execute_cypher(
            "CREATE REL TABLE IF NOT EXISTS HAS_PARAM (FROM Chip TO Parameter)"
        )

    def teardown_method(self) -> None:
        self.store.close()

    def test_health_check(self) -> None:
        assert self.store.health_check() is True

    def test_execute_cypher_return_1(self) -> None:
        rows = self.store.execute_cypher("RETURN 1 AS val")
        assert len(rows) == 1
        assert rows[0]["val"] == 1

    def test_execute_cypher_match_empty(self) -> None:
        rows = self.store.execute_cypher("MATCH (c:Chip) RETURN c.chip_id AS id")
        assert rows == []

    def test_upsert_node_inserts(self) -> None:
        self.store.upsert_node(
            "Chip", {"chip_id": "STM32F4", "name": "STM32F407", "manufacturer": "ST"}, key_field="chip_id",
        )
        rows = self.store.execute_cypher("MATCH (c:Chip) WHERE c.chip_id = 'STM32F4' RETURN c.name AS name")
        assert len(rows) == 1
        assert rows[0]["name"] == "STM32F407"

    def test_upsert_node_idempotent(self) -> None:
        props = {"chip_id": "NRF52", "name": "nRF52840", "manufacturer": "Nordic"}
        self.store.upsert_node("Chip", props, key_field="chip_id")
        self.store.upsert_node("Chip", props, key_field="chip_id")  # duplicate
        rows = self.store.execute_cypher("MATCH (c:Chip) WHERE c.chip_id = 'NRF52' RETURN c.name AS n")
        assert len(rows) == 1

    def test_upsert_node_updates(self) -> None:
        self.store.upsert_node(
            "Chip", {"chip_id": "ESP32", "name": "ESP32-WROOM", "manufacturer": "Espressif"}, key_field="chip_id",
        )
        self.store.upsert_node(
            "Chip", {"chip_id": "ESP32", "name": "ESP32-S3", "manufacturer": "Espressif"}, key_field="chip_id",
        )
        rows = self.store.execute_cypher("MATCH (c:Chip) WHERE c.chip_id = 'ESP32' RETURN c.name AS n")
        assert len(rows) == 1
        assert rows[0]["n"] == "ESP32-S3"

    def test_upsert_edge(self) -> None:
        self.store.upsert_node("Chip", {"chip_id": "C1", "name": "Chip1", "manufacturer": "X"}, key_field="chip_id")
        self.store.upsert_node(
            "Parameter", {"param_id": "P1", "name": "Voltage", "value": "3.3", "unit": "V"}, key_field="param_id",
        )
        self.store.upsert_edge(
            "HAS_PARAM", "Chip", "C1", "Parameter", "P1",
            from_key_field="chip_id", to_key_field="param_id",
        )
        rows = self.store.execute_cypher(
            "MATCH (c:Chip)-[:HAS_PARAM]->(p:Parameter) "
            "RETURN c.chip_id AS cid, p.param_id AS pid"
        )
        assert len(rows) == 1
        assert rows[0]["cid"] == "C1"

    def test_get_subgraph(self) -> None:
        self.store.upsert_node("Chip", {"chip_id": "C2", "name": "Chip2", "manufacturer": "Y"}, key_field="chip_id")
        self.store.upsert_node(
            "Parameter", {"param_id": "P2", "name": "Clock", "value": "168", "unit": "MHz"}, key_field="param_id",
        )
        self.store.upsert_edge(
            "HAS_PARAM", "Chip", "C2", "Parameter", "P2",
            from_key_field="chip_id", to_key_field="param_id",
        )
        rows = self.store.get_subgraph("Chip", "C2", max_hops=1, key_field="chip_id")
        assert len(rows) >= 1

    def test_close_then_health_fails(self) -> None:
        self.store.close()
        assert self.store.health_check() is False

    def test_isinstance_base(self) -> None:
        assert isinstance(self.store, BaseGraphStore)


@pytest.mark.unit
class TestGraphStoreFactory:
    def test_create_kuzu(self, tmp_path: Path) -> None:
        config = {"graph_store": {"backend": "kuzu", "db_path": str(tmp_path / "factory_db")}}
        store = GraphStoreFactory.create(config)
        assert isinstance(store, KuzuGraphStore)
        assert store.health_check() is True
        store.close()

    def test_create_default_backend(self, tmp_path: Path) -> None:
        config = {"graph_store": {"db_path": str(tmp_path / "default_db")}}
        store = GraphStoreFactory.create(config)
        assert isinstance(store, KuzuGraphStore)
        store.close()

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown graph store backend"):
            GraphStoreFactory.create({"graph_store": {"backend": "neo4j"}})

    def test_register_custom(self, tmp_path: Path) -> None:
        class FakeGraphStore(BaseGraphStore):
            def execute_cypher(self, query, parameters=None):
                return []
            def upsert_node(self, label, properties, key_field="id"):
                pass
            def upsert_edge(
                self, rel_type, from_label, from_key, to_label, to_key,
                properties=None, from_key_field="id", to_key_field="id",
            ):
                pass
            def get_subgraph(self, start_label, start_key, max_hops=2, key_field="id"):
                return []
            def health_check(self):
                return True

        GraphStoreFactory.register("fake", FakeGraphStore)
        store = GraphStoreFactory.create({"graph_store": {"backend": "fake"}})
        assert store.health_check() is True
        # Cleanup
        del GraphStoreFactory._registry["fake"]
