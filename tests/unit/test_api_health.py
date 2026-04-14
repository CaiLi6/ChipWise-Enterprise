"""Unit tests for FastAPI health and readiness endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.api.main import APP_VERSION, create_app
from src.core.settings import Settings

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """TestClient using the default app factory with default settings."""
    settings = Settings(
        llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
        embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
    )
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── /health ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestHealthEndpoint:
    def test_health_returns_200(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client) -> None:
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["version"] == APP_VERSION
        assert "uptime" in data
        assert isinstance(data["uptime"], float)


# ── /readiness ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestReadinessEndpoint:
    @patch("src.api.routers.health._check_lmstudio")
    @patch("src.api.routers.health._check_http_service")
    @patch("src.api.routers.health._check_milvus")
    @patch("src.api.routers.health._check_redis")
    @patch("src.api.routers.health._check_postgres")
    def test_all_healthy(self, mock_pg, mock_redis, mock_milvus, mock_http, mock_lm, client) -> None:
        from src.api.routers.health import ServiceStatusDetail

        healthy = ServiceStatusDetail(healthy=True, message="OK")
        mock_pg.return_value = healthy
        mock_redis.return_value = healthy
        mock_milvus.return_value = healthy
        mock_http.return_value = healthy
        mock_lm.return_value = healthy

        resp = client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert all(s["healthy"] for s in data["services"].values())

    @patch("src.api.routers.health._check_lmstudio")
    @patch("src.api.routers.health._check_http_service")
    @patch("src.api.routers.health._check_milvus")
    @patch("src.api.routers.health._check_redis")
    @patch("src.api.routers.health._check_postgres")
    def test_degraded_when_service_down(
        self, mock_pg, mock_redis, mock_milvus, mock_http, mock_lm, client
    ) -> None:
        from src.api.routers.health import ServiceStatusDetail

        healthy = ServiceStatusDetail(healthy=True, message="OK")
        unhealthy = ServiceStatusDetail(healthy=False, message="connection refused")
        mock_pg.return_value = unhealthy
        mock_redis.return_value = healthy
        mock_milvus.return_value = healthy
        mock_http.return_value = healthy
        mock_lm.return_value = healthy

        resp = client.get("/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["postgres"]["healthy"] is False

    def test_readiness_includes_expected_services(self, client) -> None:
        """Readiness check returns entries for all expected services."""
        with (
            patch("src.api.routers.health._check_postgres") as mp,
            patch("src.api.routers.health._check_redis") as mr,
            patch("src.api.routers.health._check_milvus") as mm,
            patch("src.api.routers.health._check_http_service") as mh,
            patch("src.api.routers.health._check_lmstudio") as ml,
        ):
            from src.api.routers.health import ServiceStatusDetail

            ok = ServiceStatusDetail(healthy=True, message="OK")
            mp.return_value = ok
            mr.return_value = ok
            mm.return_value = ok
            mh.return_value = ok
            ml.return_value = ok

            data = client.get("/readiness").json()
            assert "postgres" in data["services"]
            assert "redis" in data["services"]
            assert "milvus" in data["services"]
            assert "embedding" in data["services"]
            assert "lmstudio_primary" in data["services"]
            assert "lmstudio_router" in data["services"]


# ── CORS ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCORS:
    def test_cors_allowed_origin(self, client) -> None:
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:7860",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:7860"

    def test_cors_disallowed_origin(self, client) -> None:
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"


# ── 404 ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestNotFound:
    def test_unknown_route_returns_json_404(self, client) -> None:
        resp = client.get("/nonexistent/route")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data


# ── Global exception handler ────────────────────────────────────────


@pytest.mark.unit
class TestExceptionHandler:
    def test_unhandled_exception_returns_500_json(self) -> None:
        """Injecting a route that raises → should get 500 JSON, not HTML."""
        settings = Settings(
            llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
            embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
        )
        app = create_app(settings)

        @app.get("/test-error")
        async def boom():
            raise RuntimeError("test explosion")

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/test-error")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "InternalServerError"
        assert "trace_id" in data
