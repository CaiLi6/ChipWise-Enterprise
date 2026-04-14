"""Integration test configuration and fixtures."""

from __future__ import annotations

import pytest


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
