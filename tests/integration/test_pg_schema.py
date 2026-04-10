"""Integration test: verify PostgreSQL schema (12 tables + key indexes).

Requires: docker-compose up -d (PostgreSQL running)
"""

from __future__ import annotations

import os

import pytest

EXPECTED_TABLES = [
    "chips", "chip_parameters", "documents", "document_images",
    "users", "bom_records", "bom_items", "knowledge_notes",
    "chip_alternatives", "design_rules", "errata", "query_audit_log",
]

KEY_INDEXES = [
    "idx_chips_part_number",
    "idx_params_chip_name",
    "idx_documents_hash",
    "idx_knowledge_notes_tags",
]


@pytest.mark.integration
class TestPgSchema:
    """Verify Alembic migration creates all expected tables and indexes."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from sqlalchemy import create_engine, inspect

        db_url = os.environ.get(
            "DATABASE_URL",
            f"postgresql://chipwise:{os.environ.get('PG_PASSWORD', 'changeme')}@localhost:5432/chipwise",
        )
        engine = create_engine(db_url)
        self.inspector = inspect(engine)

    def test_all_tables_exist(self) -> None:
        existing = set(self.inspector.get_table_names())
        for table in EXPECTED_TABLES:
            assert table in existing, f"Missing table: {table}"

    def test_table_count(self) -> None:
        existing = [t for t in self.inspector.get_table_names() if not t.startswith("alembic")]
        assert len(existing) >= 12

    def test_key_indexes_exist(self) -> None:
        all_indexes: set[str] = set()
        for table in EXPECTED_TABLES:
            for idx in self.inspector.get_indexes(table):
                all_indexes.add(idx["name"])
        for idx_name in KEY_INDEXES:
            assert idx_name in all_indexes, f"Missing index: {idx_name}"
