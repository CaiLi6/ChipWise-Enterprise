"""One-shot database initialization: run Alembic migrate + verify schema."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, inspect, text


EXPECTED_TABLES = [
    "chips", "chip_parameters", "documents", "document_images",
    "users", "bom_records", "bom_items", "knowledge_notes",
    "chip_alternatives", "design_rules", "errata", "query_audit_log",
]


def get_db_url() -> str:
    """Build database URL from environment variables."""
    host = os.environ.get("PG_HOST", "localhost")
    port = os.environ.get("PG_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "chipwise")
    user = os.environ.get("POSTGRES_USER", "chipwise")
    password = os.environ.get("PG_PASSWORD", "changeme")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def init_database(db_url: str) -> None:
    """Execute Alembic upgrade head."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


def verify_schema(db_url: str) -> bool:
    """Check that all 12 expected tables exist."""
    engine = create_engine(db_url)
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t for t in EXPECTED_TABLES if t not in existing]
    if missing:
        print(f"ERROR: Missing tables: {missing}", file=sys.stderr)
        return False
    print(f"OK: All {len(EXPECTED_TABLES)} tables exist.")
    return True


if __name__ == "__main__":
    url = get_db_url()
    print(f"Initializing database at {url.split('@')[1]}...")
    init_database(url)
    ok = verify_schema(url)
    sys.exit(0 if ok else 1)
