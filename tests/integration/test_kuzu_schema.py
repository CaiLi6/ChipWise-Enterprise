"""Integration tests for Kùzu graph schema initialization.

Run: pytest -q tests/integration/test_kuzu_schema.py -m integration
Uses a temporary directory (no Docker required — Kùzu is embedded).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.init_kuzu import (
    EXPECTED_NODE_TABLES,
    EXPECTED_REL_TABLES,
    init_knowledge_graph,
    verify_schema,
)


@pytest.mark.integration
class TestKuzuSchemaInit:
    """Test Kùzu schema creation and verification using real Kùzu."""

    def test_init_creates_all_tables(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test_kuzu")
        db = init_knowledge_graph(db_path)
        assert db is not None
        assert verify_schema(db_path) is True

    def test_idempotent_init(self, tmp_path: Path) -> None:
        """Running init twice should not raise errors."""
        db_path = str(tmp_path / "test_kuzu_idempotent")
        init_knowledge_graph(db_path)
        init_knowledge_graph(db_path)  # Second call should be fine
        assert verify_schema(db_path) is True

    def test_verify_empty_db_fails(self, tmp_path: Path) -> None:
        """Empty DB without tables should fail verification."""
        import kuzu

        db_path = str(tmp_path / "test_kuzu_empty")
        kuzu.Database(db_path)  # Create empty DB (kuzu creates the dir)
        assert verify_schema(db_path) is False

    def test_verify_nonexistent_path(self, tmp_path: Path) -> None:
        assert verify_schema(str(tmp_path / "nonexistent")) is False

    def test_node_table_count(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test_count")
        init_knowledge_graph(db_path)

        import kuzu

        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        result = conn.execute("CALL show_tables() RETURN *")
        tables = set()
        while result.has_next():
            tables.add(result.get_next()[1])  # index 1 = table name

        assert EXPECTED_NODE_TABLES.issubset(tables)
        assert EXPECTED_REL_TABLES.issubset(tables)

    def test_simple_cypher_query(self, tmp_path: Path) -> None:
        """After init, basic Cypher queries should work."""
        import kuzu

        db_path = str(tmp_path / "test_cypher")
        init_knowledge_graph(db_path)

        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)

        # Should be able to query (empty result is fine)
        result = conn.execute("MATCH (c:Chip) RETURN c.part_number")
        assert result is not None
