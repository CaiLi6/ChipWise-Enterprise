"""Integration test configuration and fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _load_dotenv() -> None:
    """Load .env at project root into os.environ for integration tests."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip Milvus-dependent tests when Milvus is unreachable."""
    try:
        import socket

        sock = socket.create_connection(("localhost", 19530), timeout=2)
        sock.close()
    except OSError:
        milvus_skip = pytest.mark.skip(reason="Milvus not reachable at localhost:19530")
        for item in items:
            if "milvus" in item.nodeid.lower() or "milvus" in getattr(item, "fspath", "").strpath.lower():
                item.add_marker(milvus_skip)
