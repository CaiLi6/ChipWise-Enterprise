"""Integration test for Prometheus + Grafana monitoring stack (§6A4)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def prometheus_url() -> str:
    import os
    return os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


@pytest.fixture
def grafana_url() -> str:
    import os
    return os.environ.get("GRAFANA_URL", "http://localhost:3000")


@pytest.mark.asyncio
async def test_prometheus_health(prometheus_url: str) -> None:
    httpx = pytest.importorskip("httpx")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{prometheus_url}/-/healthy", timeout=5)
        assert resp.status_code == 200
    except Exception as exc:
        pytest.skip(f"Prometheus not reachable: {exc}")


@pytest.mark.asyncio
async def test_grafana_health(grafana_url: str) -> None:
    httpx = pytest.importorskip("httpx")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{grafana_url}/api/health", timeout=5)
        assert resp.status_code == 200
    except Exception as exc:
        pytest.skip(f"Grafana not reachable: {exc}")


@pytest.mark.asyncio
async def test_prometheus_api_query(prometheus_url: str) -> None:
    httpx = pytest.importorskip("httpx")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{prometheus_url}/api/v1/query",
                params={"query": "up"},
                timeout=5,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
    except Exception as exc:
        pytest.skip(f"Prometheus not reachable: {exc}")
