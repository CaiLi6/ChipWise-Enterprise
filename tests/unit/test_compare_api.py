"""Unit tests for compare API (§4A2)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers.compare import router


@pytest.mark.unit
class TestCompareAPI:
    @pytest.fixture
    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_compare_basic(self, client: TestClient) -> None:
        resp = client.post("/api/v1/compare", json={
            "chip_names": ["STM32F407", "STM32F103"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "comparison_table" in data

    def test_compare_too_few(self, client: TestClient) -> None:
        resp = client.post("/api/v1/compare", json={
            "chip_names": ["STM32F407"]
        })
        assert resp.status_code == 422

    def test_compare_with_dimensions(self, client: TestClient) -> None:
        resp = client.post("/api/v1/compare", json={
            "chip_names": ["A", "B"],
            "dimensions": ["electrical"]
        })
        assert resp.status_code == 200
