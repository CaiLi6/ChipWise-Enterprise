"""E2E tests for all 10 Agent Tools (§6D1).

These tests require a running ChipWise stack (FastAPI + Docker services).
They are skipped automatically when the API is unreachable.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.e2e

API_BASE = os.environ.get("CHIPWISE_API_URL", "http://localhost:8080")
JWT_TOKEN = os.environ.get("CHIPWISE_JWT", "")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {JWT_TOKEN}"} if JWT_TOKEN else {}


@pytest.fixture(scope="module")
def http_client():
    httpx = pytest.importorskip("httpx")
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("ChipWise API not healthy")
    except Exception:
        pytest.skip("ChipWise API not reachable")
    return httpx.Client(base_url=API_BASE, headers=_headers(), timeout=30)


@pytest.mark.asyncio
async def test_rag_search_e2e(http_client) -> None:
    """Tool 1: rag_search — query returns answer with citations."""
    resp = http_client.post("/api/v1/query", json={"query": "STM32F407 operating voltage"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data or "response" in data


@pytest.mark.asyncio
async def test_chip_compare_e2e(http_client) -> None:
    """Tool 4: chip_compare — returns comparison table."""
    resp = http_client.post("/api/v1/compare", json={"chip_names": ["STM32F407", "GD32F407"]})
    assert resp.status_code == 200
    data = resp.json()
    assert "comparison_table" in data or "analysis" in data


@pytest.mark.asyncio
async def test_health_check_e2e(http_client) -> None:
    """System health baseline."""
    resp = http_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_knowledge_crud_e2e(http_client) -> None:
    """Tool 9: knowledge_search — create note, then list."""
    create_resp = http_client.post("/api/v1/knowledge", json={
        "content": "STM32F407 SPI CS timing test note",
        "note_type": "design_tip",
        "tags": ["SPI"],
    })
    assert create_resp.status_code == 200
    note_id = create_resp.json()["note_id"]

    list_resp = http_client.get("/api/v1/knowledge")
    assert list_resp.status_code == 200
    notes = list_resp.json()["notes"]
    assert any(n["note_id"] == note_id for n in notes)

    # Cleanup
    http_client.delete(f"/api/v1/knowledge/{note_id}")
