"""Unit tests for task progress API (§3B5)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.tasks import router, set_redis


@pytest.mark.unit
class TestTaskProgress:
    @pytest.fixture
    def redis(self) -> AsyncMock:
        r = AsyncMock()
        r._data = {}

        async def _hgetall(key: str):
            return r._data.get(key, {})

        r.hgetall = AsyncMock(side_effect=_hgetall)
        return r

    @pytest.fixture
    def app(self, redis: AsyncMock) -> FastAPI:
        app = FastAPI()
        app.include_router(router)
        set_redis(redis)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_get_progress_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tasks/nonexistent")
        assert resp.status_code == 404

    def test_get_progress_found(self, client: TestClient, redis: AsyncMock) -> None:
        redis._data["task:progress:abc"] = {
            "status": "running",
            "progress": "50",
            "stage": "embedding",
            "message": "Embedding chunks",
        }
        resp = client.get("/api/v1/tasks/abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"] == 50
        assert data["stage"] == "embedding"

    def test_progress_completed(self, client: TestClient, redis: AsyncMock) -> None:
        redis._data["task:progress:done1"] = {
            "status": "completed",
            "progress": "100",
            "stage": "done",
            "message": "",
        }
        resp = client.get("/api/v1/tasks/done1")
        data = resp.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
