"""Unit tests for Knowledge Notes CRUD API (§5C1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.knowledge import router, _notes


@pytest.fixture(autouse=True)
def reset_notes_store():
    """Reset the in-memory store and ID counter before each test."""
    import src.api.routers.knowledge as mod
    mod._notes.clear()
    mod._next_id = 1
    yield
    mod._notes.clear()
    mod._next_id = 1


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.unit
class TestKnowledgeNoteCreate:
    def test_create_returns_201_data(self, client: TestClient) -> None:
        resp = client.post("/api/v1/knowledge", json={
            "chip_id": 1,
            "content": "STM32F407 SPI CS timing needs careful attention.",
            "note_type": "design_tip",
            "tags": ["SPI", "timing"],
            "is_public": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["note_id"] == 1
        assert data["content"] == "STM32F407 SPI CS timing needs careful attention."
        assert data["note_type"] == "design_tip"

    def test_create_auto_increments_id(self, client: TestClient) -> None:
        r1 = client.post("/api/v1/knowledge", json={"content": "Note 1"})
        r2 = client.post("/api/v1/knowledge", json={"content": "Note 2"})
        assert r1.json()["note_id"] == 1
        assert r2.json()["note_id"] == 2

    def test_create_defaults_applied(self, client: TestClient) -> None:
        resp = client.post("/api/v1/knowledge", json={"content": "Minimal note"})
        data = resp.json()
        assert data["note_type"] == "comment"
        assert data["tags"] == []
        assert data["is_public"] is True


@pytest.mark.unit
class TestKnowledgeNoteList:
    def test_list_returns_all_notes(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"content": "Note A"})
        client.post("/api/v1/knowledge", json={"content": "Note B"})

        resp = client.get("/api/v1/knowledge")
        data = resp.json()
        assert data["total"] == 2

    def test_filter_by_chip_id(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"chip_id": 1, "content": "MCU note"})
        client.post("/api/v1/knowledge", json={"chip_id": 2, "content": "PMIC note"})

        resp = client.get("/api/v1/knowledge?chip_id=1")
        data = resp.json()
        assert data["total"] == 1
        assert data["notes"][0]["chip_id"] == 1

    def test_filter_by_tags(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"content": "SPI note", "tags": ["SPI"]})
        client.post("/api/v1/knowledge", json={"content": "I2C note", "tags": ["I2C"]})

        resp = client.get("/api/v1/knowledge?tags=SPI")
        data = resp.json()
        assert data["total"] == 1

    def test_list_empty_returns_zero(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge")
        assert resp.json()["total"] == 0


@pytest.mark.unit
class TestKnowledgeNoteGet:
    def test_get_existing_note(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"content": "Hello"})
        resp = client.get("/api/v1/knowledge/1")
        assert resp.status_code == 200
        assert resp.json()["content"] == "Hello"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/knowledge/999")
        assert resp.status_code == 404


@pytest.mark.unit
class TestKnowledgeNoteUpdate:
    def test_update_changes_content(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"content": "Original"})
        resp = client.put("/api/v1/knowledge/1", json={"content": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated"

    def test_update_missing_returns_404(self, client: TestClient) -> None:
        resp = client.put("/api/v1/knowledge/999", json={"content": "X"})
        assert resp.status_code == 404


@pytest.mark.unit
class TestKnowledgeNoteDelete:
    def test_delete_removes_note(self, client: TestClient) -> None:
        client.post("/api/v1/knowledge", json={"content": "To delete"})
        resp = client.delete("/api/v1/knowledge/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify gone
        assert client.get("/api/v1/knowledge/1").status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/knowledge/999")
        assert resp.status_code == 404
