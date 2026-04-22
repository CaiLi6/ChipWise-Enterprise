"""Alembic bidirectional migration test.

Verifies: upgrade → tables exist → downgrade → tables gone → upgrade again.
Requires: docker-compose up -d postgres
"""

from __future__ import annotations

import os
import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_nollm]

CORE_TABLES = [
    "users", "documents", "chips", "chip_parameters",
    "errata", "bom_records", "bom_items",
]

_PG_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chipwise:chipwise123@localhost:5432/chipwise",
)


def _alembic(cmd: str) -> None:
    """Run an alembic CLI command from the project root using the venv binary."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    alembic_bin = os.path.join(project_root, ".venv", "bin", "alembic")
    if not os.path.exists(alembic_bin):
        alembic_bin = "alembic"
    args = [alembic_bin, cmd, "head"] if cmd == "upgrade" else [alembic_bin, cmd, "-1"]
    result = subprocess.run(
        args,
        capture_output=True, text=True,
        cwd=project_root,
    )
    if result.returncode != 0 and "No such file or directory" in (result.stderr or ""):
        pytest.skip(f"alembic CLI not available: {result.stderr}")
    assert result.returncode == 0, f"alembic {cmd} failed:\n{result.stderr}"


def _table_names() -> list[str]:
    """Query pg_tables for public schema tables via psql."""
    try:
        result = subprocess.run(
            [
                "psql", _PG_URL, "-t", "-A",
                "-c", "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
            ],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        pytest.skip("psql binary not available on PATH")
    if result.returncode != 0:
        pytest.skip(f"psql not available or PG not running: {result.stderr}")
    return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]


class TestAlembicBidirectional:
    """Test upgrade → downgrade → upgrade cycle."""

    def test_upgrade_creates_tables(self) -> None:
        _alembic("upgrade")
        tables = _table_names()
        for t in CORE_TABLES:
            assert t in tables, f"Table '{t}' missing after upgrade"

    def test_downgrade_removes_tables(self) -> None:
        _alembic("upgrade")
        _alembic("downgrade")
        tables = _table_names()
        for t in CORE_TABLES:
            assert t not in tables, f"Table '{t}' still exists after downgrade"

    def test_re_upgrade_succeeds(self) -> None:
        _alembic("upgrade")
        _alembic("downgrade")
        _alembic("upgrade")
        tables = _table_names()
        for t in CORE_TABLES:
            assert t in tables, f"Table '{t}' missing after re-upgrade"
