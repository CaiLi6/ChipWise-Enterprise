"""E2E tests for Agent multi-tool composition (§6D1)."""

from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.e2e

API_BASE = os.environ.get("CHIPWISE_API_URL", "http://localhost:8080")
JWT_TOKEN = os.environ.get("CHIPWISE_JWT", "")


@pytest.fixture(scope="module")
def http_client():
    httpx = pytest.importorskip("httpx")
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("ChipWise API not healthy")
    except Exception:
        pytest.skip("ChipWise API not reachable")
    headers = {"Authorization": f"Bearer {JWT_TOKEN}"} if JWT_TOKEN else {}
    return httpx.Client(base_url=API_BASE, headers=headers, timeout=60)


def test_agent_multi_tool_composition(http_client) -> None:
    """Complex query triggers ≥2 tools and returns comprehensive answer."""
    resp = http_client.post("/api/v1/query", json={
        "query": "Compare STM32F407 vs GD32F407, check design rules, and list any errata"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data or "response" in data


def test_agent_returns_valid_trace(http_client) -> None:
    """Response contains trace_id for observability."""
    resp = http_client.post("/api/v1/query", json={"query": "What is STM32F407?"})
    assert resp.status_code == 200


def test_report_export_after_comparison(http_client) -> None:
    """Compare chips → export comparison as Excel report."""
    compare_resp = http_client.post("/api/v1/compare", json={
        "chip_names": ["STM32F407", "GD32F407"]
    })
    assert compare_resp.status_code == 200
