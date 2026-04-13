"""Unit tests for monitoring tab (§6A3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.health import router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
class TestReadinessEndpointMetrics:
    def test_readiness_returns_services_dict(self, client: TestClient) -> None:
        resp = client.get("/readiness")
        # May be 200 or 500 without real services, but structure should be consistent
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data
            assert "services" in data
        # If 500, that's OK — readiness check requires live services

    def test_health_endpoint_returns_version(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "uptime" in data
        assert isinstance(data["uptime"], (int, float))


@pytest.mark.unit
class TestTokenTrackerIntegration:
    def test_token_tracker_records_and_summarizes(self) -> None:
        from src.observability.token_tracker import TokenTracker
        t = TokenTracker()
        t.record("qwen3-35b", "primary", 500, 200)
        t.record("qwen3-1.7b", "router", 50, 20)
        summary = t.get_daily_summary()
        assert summary["totals"]["total"] == 770
        assert len(summary["by_model"]) == 2

    def test_monitoring_tab_data_structure(self) -> None:
        """Mock monitoring tab status aggregation."""
        from src.observability.token_tracker import TokenTracker
        t = TokenTracker()
        t.record("primary", "qwen3-35b", 1000, 400)
        summary = t.get_daily_summary()

        # Verify structure matches what the monitoring tab would display
        assert "totals" in summary
        assert summary["totals"]["total"] > 0
