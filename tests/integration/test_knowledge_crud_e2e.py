"""Integration test for Knowledge Notes CRUD via TestClient (§5C1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.knowledge import router
import src.api.routers.knowledge as knowledge_mod


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_store():
    knowledge_mod._notes.clear()
    knowledge_mod._next_id = 1
    yield
    knowledge_mod._notes.clear()
    knowledge_mod._next_id = 1


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_full_crud_lifecycle(client: TestClient) -> None:
    # Create
    resp = client.post("/api/v1/knowledge", json={
        "chip_id": 1,
        "content": "STM32F407 SPI CS timing note",
        "note_type": "design_tip",
        "tags": ["SPI"],
        "is_public": True,
    })
    assert resp.status_code == 200
    note_id = resp.json()["note_id"]

    # Read
    resp = client.get(f"/api/v1/knowledge/{note_id}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "STM32F407 SPI CS timing note"

    # Update
    resp = client.put(f"/api/v1/knowledge/{note_id}", json={
        "content": "Updated: STM32F407 SPI needs CS assert before clock.",
        "note_type": "design_tip",
        "tags": ["SPI", "clock"],
        "is_public": True,
    })
    assert resp.status_code == 200
    assert "Updated" in resp.json()["content"]

    # List
    resp = client.get("/api/v1/knowledge?chip_id=1")
    assert resp.json()["total"] == 1

    # Delete
    resp = client.delete(f"/api/v1/knowledge/{note_id}")
    assert resp.status_code == 200

    # Verify gone
    assert client.get(f"/api/v1/knowledge/{note_id}").status_code == 404


def test_tag_filter_works(client: TestClient) -> None:
    client.post("/api/v1/knowledge", json={"content": "SPI note", "tags": ["SPI"]})
    client.post("/api/v1/knowledge", json={"content": "I2C note", "tags": ["I2C"]})
    client.post("/api/v1/knowledge", json={"content": "Generic note", "tags": []})

    resp = client.get("/api/v1/knowledge?tags=SPI")
    assert resp.json()["total"] == 1
