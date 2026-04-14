"""Seed fixture for integration_nollm tests.

Loads ``seed_chips.sql`` into PostgreSQL before the test session and cleans up after.
Usage: automatically collected by pytest when running ``-m integration_nollm``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

SEED_SQL = Path(__file__).parent / "seed_chips.sql"


@pytest.fixture(scope="session")
def seed_db():
    """Load seed data into PostgreSQL for the integration test session."""
    try:
        import psycopg2  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("psycopg2 not installed")
        return

    dsn = (
        f"host={os.environ.get('PG_HOST', 'localhost')} "
        f"port={os.environ.get('PG_PORT', '5432')} "
        f"dbname={os.environ.get('PG_DATABASE', 'chipwise')} "
        f"user={os.environ.get('PG_USER', 'chipwise')} "
        f"password={os.environ.get('PG_PASSWORD', 'chipwise123')}"
    )

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()

        # Load seed SQL
        sql = SEED_SQL.read_text(encoding="utf-8")
        cur.execute(sql)
        cur.close()

        yield conn

        # Cleanup: remove seeded data
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM errata WHERE chip_part_number"
            " IN ('STM32F407VGT6', 'STM32F103C8T6')"
        )
        parts = (
            "('STM32F407VGT6', 'STM32F103C8T6',"
            " 'GD32F303CCT6', 'ESP32-WROOM-32', 'RP2040')"
        )
        cur.execute(f"DELETE FROM chip_parameters WHERE chip_part_number IN {parts}")
        cur.execute(f"DELETE FROM chips WHERE part_number IN {parts}")
        cur.close()
        conn.close()
    except Exception as exc:
        pytest.skip(f"Cannot connect to PostgreSQL: {exc}")
