"""Unit tests for tasks router (42% → 70%+)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers.tasks import router, set_redis


@pytest.fixture()
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_redis():
    """Reset the module-level _redis after each test."""
    set_redis(None)
    yield
    set_redis(None)


@pytest.mark.unit
class TestGetTaskProgress:
    def test_redis_unavailable_returns_503(self, client: TestClient) -> None:
        set_redis(None)
        resp = client.get("/api/v1/tasks/task-123")
        assert resp.status_code == 503

    def test_task_not_found_returns_404(self, client: TestClient) -> None:
        redis = AsyncMock()
        redis.hgetall.return_value = {}
        set_redis(redis)
        resp = client.get("/api/v1/tasks/task-nonexist")
        assert resp.status_code == 404

    def test_task_found_returns_progress(self, client: TestClient) -> None:
        redis = AsyncMock()
        redis.hgetall.return_value = {
            "status": "processing",
            "progress": "50",
            "stage": "embedding",
            "message": "Embedding chunks...",
        }
        set_redis(redis)
        resp = client.get("/api/v1/tasks/task-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-123"
        assert data["status"] == "processing"
        assert data["progress"] == 50
        assert data["stage"] == "embedding"

    def test_task_completed(self, client: TestClient) -> None:
        redis = AsyncMock()
        redis.hgetall.return_value = {
            "status": "completed",
            "progress": "100",
            "stage": "done",
            "message": "All done",
        }
        set_redis(redis)
        resp = client.get("/api/v1/tasks/task-456")
        assert resp.status_code == 200
        assert resp.json()["progress"] == 100
        assert resp.json()["status"] == "completed"

    def test_task_defaults_for_missing_fields(self, client: TestClient) -> None:
        redis = AsyncMock()
        redis.hgetall.return_value = {"status": "queued"}
        set_redis(redis)
        resp = client.get("/api/v1/tasks/task-789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"] == 0
        assert data["stage"] == ""
        assert data["message"] == ""
