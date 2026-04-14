"""Integration tests: verify Docker infrastructure services are healthy.

Requires: docker-compose up -d
"""

from __future__ import annotations

import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_nollm]


class TestDockerInfraHealth:
    """Verify all three infrastructure containers are healthy."""

    def test_postgres_healthy(self) -> None:
        result = subprocess.run(
            ["docker", "exec", "chipwise-postgres", "pg_isready", "-U", "chipwise"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"PostgreSQL not ready: {result.stderr}"

    def test_milvus_healthy(self) -> None:
        result = subprocess.run(
            ["docker", "exec", "chipwise-milvus", "curl", "-f", "http://localhost:9091/healthz"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Milvus not healthy: {result.stderr}"

    def test_redis_healthy(self) -> None:
        result = subprocess.run(
            ["docker", "exec", "chipwise-redis", "redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Redis not responding: {result.stderr}"
        assert "PONG" in result.stdout
