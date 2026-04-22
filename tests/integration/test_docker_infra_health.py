"""Integration tests: verify Docker infrastructure services are healthy.

Requires: docker-compose up -d
"""

from __future__ import annotations

import os
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
        # Load REDIS_PASSWORD from .env (compose uses it via --requirepass) if not in env.
        redis_pw = os.environ.get("REDIS_PASSWORD")
        if not redis_pw:
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env",
            )
            if os.path.exists(env_path):
                with open(env_path) as fh:
                    for line in fh:
                        if line.startswith("REDIS_PASSWORD="):
                            redis_pw = line.split("=", 1)[1].strip()
                            break
        cmd = ["docker", "exec", "chipwise-redis", "redis-cli"]
        if redis_pw:
            cmd += ["-a", redis_pw]
        cmd.append("ping")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Redis not responding: {result.stderr}"
        assert "PONG" in result.stdout
