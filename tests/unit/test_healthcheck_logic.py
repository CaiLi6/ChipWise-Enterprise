"""Unit tests for healthcheck logic — all external deps are mocked."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts.healthcheck import (
    ServiceStatus,
    check_all,
    check_kuzu,
    check_milvus,
    check_postgres,
    check_redis,
    _build_dsn,
    _build_redis_url,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_settings(**overrides) -> SimpleNamespace:
    """Build a minimal Settings-like namespace for check_all()."""
    db = SimpleNamespace(
        host="localhost", port=5432, database="chipwise", user="chipwise", password="pw"
    )
    milvus = SimpleNamespace(host="localhost", port=19530)
    vector_store = SimpleNamespace(milvus=milvus)
    redis = SimpleNamespace(host="localhost", port=6379, db=0, password="")
    kuzu = SimpleNamespace(db_path=overrides.get("kuzu_db_path", "data/kuzu"))
    graph_store = SimpleNamespace(kuzu=kuzu)
    return SimpleNamespace(
        database=db,
        vector_store=vector_store,
        redis=redis,
        graph_store=graph_store,
    )


# ── ServiceStatus dataclass ─────────────────────────────────────────


@pytest.mark.unit
class TestServiceStatus:
    def test_healthy_instance(self) -> None:
        s = ServiceStatus(name="Test", healthy=True, latency_ms=1.5, message="OK")
        assert s.name == "Test"
        assert s.healthy is True
        assert s.latency_ms == 1.5
        assert s.message == "OK"

    def test_unhealthy_instance(self) -> None:
        s = ServiceStatus(name="Test", healthy=False, latency_ms=5000.0, message="timeout")
        assert s.healthy is False


# ── check_postgres ──────────────────────────────────────────────────


@pytest.mark.unit
class TestCheckPostgres:
    @patch("scripts.healthcheck.check_postgres.__module__", "scripts.healthcheck")
    def test_healthy(self) -> None:
        """SELECT 1 succeeds → healthy."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch("sqlalchemy.create_engine", return_value=mock_engine):
            result = check_postgres("postgresql://user:pw@localhost/db")

        assert result.healthy is True
        assert result.name == "PostgreSQL"
        assert result.message == "OK"
        assert result.latency_ms >= 0

    def test_connection_error(self) -> None:
        """Connection failure → unhealthy."""
        with patch("sqlalchemy.create_engine", side_effect=ConnectionError("refused")):
            result = check_postgres("postgresql://user:pw@badhost/db")

        assert result.healthy is False
        assert result.name == "PostgreSQL"
        assert "refused" in result.message

    def test_query_error(self) -> None:
        """Engine connects but query fails → unhealthy."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.side_effect = RuntimeError("query failed")

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch("sqlalchemy.create_engine", return_value=mock_engine):
            result = check_postgres("postgresql://user:pw@localhost/db")

        assert result.healthy is False
        assert "query failed" in result.message


# ── check_milvus ────────────────────────────────────────────────────


@pytest.mark.unit
class TestCheckMilvus:
    @patch("pymilvus.connections")
    @patch("pymilvus.utility")
    def test_healthy_all_collections(self, mock_utility, mock_connections) -> None:
        """Both collections exist → healthy."""
        mock_utility.has_collection.return_value = True
        result = check_milvus("localhost", 19530)
        assert result.healthy is True
        assert result.name == "Milvus"
        mock_connections.connect.assert_called_once()
        mock_connections.disconnect.assert_called_once_with("healthcheck")

    @patch("pymilvus.connections")
    @patch("pymilvus.utility")
    def test_missing_collection(self, mock_utility, mock_connections) -> None:
        """One collection missing → unhealthy."""

        def has_collection(name, using=None):
            return name == "datasheet_chunks"

        mock_utility.has_collection.side_effect = has_collection
        result = check_milvus("localhost", 19530)
        assert result.healthy is False
        assert "knowledge_notes" in result.message

    @patch("pymilvus.connections")
    def test_connection_error(self, mock_connections) -> None:
        """Connection failure → unhealthy."""
        mock_connections.connect.side_effect = ConnectionError("timeout")
        result = check_milvus("badhost", 19530)
        assert result.healthy is False
        assert "timeout" in result.message


# ── check_redis ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestCheckRedis:
    @patch("redis.Redis")
    def test_healthy(self, mock_redis_cls) -> None:
        """PING returns True → healthy."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_cls.from_url.return_value = mock_client
        result = check_redis("redis://localhost:6379/0")
        assert result.healthy is True
        assert result.name == "Redis"
        mock_client.close.assert_called_once()

    @patch("redis.Redis")
    def test_ping_returns_false(self, mock_redis_cls) -> None:
        """PING returns False → unhealthy."""
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        mock_redis_cls.from_url.return_value = mock_client
        result = check_redis("redis://localhost:6379/0")
        assert result.healthy is False
        assert "PING returned False" in result.message

    @patch("redis.Redis")
    def test_connection_error(self, mock_redis_cls) -> None:
        """Connection failure → unhealthy."""
        mock_redis_cls.from_url.side_effect = ConnectionError("refused")
        result = check_redis("redis://badhost:6379/0")
        assert result.healthy is False
        assert "refused" in result.message


# ── check_kuzu ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestCheckKuzu:
    def test_healthy(self, tmp_path: Path) -> None:
        """Valid DB directory + query succeeds → healthy."""
        db_dir = tmp_path / "kuzu_db"
        db_dir.mkdir()

        mock_conn = MagicMock()
        mock_db = MagicMock()

        with (
            patch("kuzu.Database", return_value=mock_db),
            patch("kuzu.Connection", return_value=mock_conn),
        ):
            result = check_kuzu(str(db_dir))

        assert result.healthy is True
        assert result.name == "Kùzu"
        mock_conn.execute.assert_called_once_with("RETURN 1")

    def test_missing_path(self, tmp_path: Path) -> None:
        """Non-existent path → unhealthy."""
        result = check_kuzu(str(tmp_path / "nonexistent"))
        assert result.healthy is False
        assert "does not exist" in result.message

    def test_query_error(self, tmp_path: Path) -> None:
        """DB opens but query fails → unhealthy."""
        db_dir = tmp_path / "kuzu_bad"
        db_dir.mkdir()

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("corrupted")
        mock_db = MagicMock()

        with (
            patch("kuzu.Database", return_value=mock_db),
            patch("kuzu.Connection", return_value=mock_conn),
        ):
            result = check_kuzu(str(db_dir))

        assert result.healthy is False
        assert "corrupted" in result.message


# ── check_all ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestCheckAll:
    @patch("scripts.healthcheck.check_kuzu")
    @patch("scripts.healthcheck.check_redis")
    @patch("scripts.healthcheck.check_milvus")
    @patch("scripts.healthcheck.check_postgres")
    def test_all_healthy(self, mock_pg, mock_milvus, mock_redis, mock_kuzu) -> None:
        """All services healthy → all results healthy."""
        for mock, name in [
            (mock_pg, "PostgreSQL"),
            (mock_milvus, "Milvus"),
            (mock_redis, "Redis"),
            (mock_kuzu, "Kùzu"),
        ]:
            mock.return_value = ServiceStatus(
                name=name, healthy=True, latency_ms=1.0, message="OK"
            )

        settings = _make_settings()
        results = check_all(settings)

        assert len(results) == 4
        assert all(s.healthy for s in results.values())

    @patch("scripts.healthcheck.check_kuzu")
    @patch("scripts.healthcheck.check_redis")
    @patch("scripts.healthcheck.check_milvus")
    @patch("scripts.healthcheck.check_postgres")
    def test_partial_failure(self, mock_pg, mock_milvus, mock_redis, mock_kuzu) -> None:
        """One service down does not block checking others."""
        mock_pg.return_value = ServiceStatus(
            name="PostgreSQL", healthy=True, latency_ms=1.0, message="OK"
        )
        mock_milvus.return_value = ServiceStatus(
            name="Milvus", healthy=False, latency_ms=5000.0, message="timeout"
        )
        mock_redis.return_value = ServiceStatus(
            name="Redis", healthy=True, latency_ms=0.5, message="OK"
        )
        mock_kuzu.return_value = ServiceStatus(
            name="Kùzu", healthy=True, latency_ms=2.0, message="OK"
        )

        settings = _make_settings()
        results = check_all(settings)

        assert len(results) == 4
        assert results["PostgreSQL"].healthy is True
        assert results["Milvus"].healthy is False
        assert results["Redis"].healthy is True
        assert results["Kùzu"].healthy is True

    @patch("scripts.healthcheck.check_kuzu")
    @patch("scripts.healthcheck.check_redis")
    @patch("scripts.healthcheck.check_milvus")
    @patch("scripts.healthcheck.check_postgres")
    def test_all_unhealthy(self, mock_pg, mock_milvus, mock_redis, mock_kuzu) -> None:
        """All services down → all results unhealthy."""
        for mock, name in [
            (mock_pg, "PostgreSQL"),
            (mock_milvus, "Milvus"),
            (mock_redis, "Redis"),
            (mock_kuzu, "Kùzu"),
        ]:
            mock.return_value = ServiceStatus(
                name=name, healthy=False, latency_ms=5000.0, message="down"
            )

        settings = _make_settings()
        results = check_all(settings)

        assert not any(s.healthy for s in results.values())


# ── Helper functions ────────────────────────────────────────────────


@pytest.mark.unit
class TestBuildDSN:
    def test_builds_correct_dsn(self) -> None:
        db = SimpleNamespace(
            host="myhost", port=5433, database="mydb", user="myuser", password="mypass"
        )
        dsn = _build_dsn(db)
        assert dsn == "postgresql://myuser:mypass@myhost:5433/mydb"


@pytest.mark.unit
class TestBuildRedisURL:
    def test_without_password(self) -> None:
        r = SimpleNamespace(host="localhost", port=6379, db=0, password="")
        assert _build_redis_url(r) == "redis://localhost:6379/0"

    def test_with_password(self) -> None:
        r = SimpleNamespace(host="localhost", port=6379, db=0, password="secret")
        assert _build_redis_url(r) == "redis://:secret@localhost:6379/0"


# ── Latency tracking ───────────────────────────────────────────────


@pytest.mark.unit
class TestLatencyTracking:
    def test_latency_is_positive(self) -> None:
        """Even on failure, latency should be recorded as a positive number."""
        result = check_kuzu("/nonexistent/path")
        assert result.latency_ms >= 0
