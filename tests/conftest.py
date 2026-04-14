"""Global test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def settings_override(tmp_path: Path) -> dict:
    """Provide a temporary settings override dict for tests."""
    return {
        "database": {"host": "localhost", "port": 5432, "database": "chipwise_test"},
        "redis": {"host": "localhost", "port": 6379, "db": 15},
    }


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir
