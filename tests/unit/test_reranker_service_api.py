"""Unit tests for bce-reranker Service API — model is mocked."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_model():
    """Return a mock CrossEncoder that produces deterministic scores."""
    model = MagicMock()

    def mock_predict(pairs):
        n = len(pairs)
        # Generate descending scores so we can verify sorting
        return np.array([1.0 - i * 0.1 for i in range(n)], dtype=np.float32)

    model.predict.side_effect = mock_predict
    return model


def _make_test_app(svc_module) -> FastAPI:
    """Build a copy of the app without the real lifespan."""

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(title="Test Reranker Service", lifespan=noop_lifespan)
    for route in svc_module.app.routes:
        test_app.routes.append(route)
    return test_app


@pytest.fixture
def ready_client(mock_model):
    """TestClient with model loaded and ready."""
    import src.services.reranker_service as svc

    svc._model = mock_model
    svc._model_ready = True
    test_app = _make_test_app(svc)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client
    svc._model = None
    svc._model_ready = False


@pytest.fixture
def not_ready_client():
    """TestClient with model NOT loaded."""
    import src.services.reranker_service as svc

    svc._model = None
    svc._model_ready = False
    test_app = _make_test_app(svc)
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


# ── Health endpoint ─────────────────────────────────────────────────


@pytest.mark.unit
class TestHealthEndpoint:
    def test_health_ready(self, ready_client) -> None:
        resp = ready_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["model"] == "maidalun1020/bce-reranker-base_v1"
        assert data["ready"] is True

    def test_health_not_ready(self, not_ready_client) -> None:
        resp = not_ready_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is False
        assert data["status"] == "loading"


# ── Rerank endpoint ─────────────────────────────────────────────────


@pytest.mark.unit
class TestRerankEndpoint:
    def test_basic_rerank(self, ready_client) -> None:
        resp = ready_client.post(
            "/rerank",
            json={
                "query": "STM32 clock frequency",
                "documents": ["doc about clocks", "doc about memory"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "maidalun1020/bce-reranker-base_v1"
        assert len(data["results"]) == 2

    def test_results_sorted_by_score_descending(self, ready_client) -> None:
        resp = ready_client.post(
            "/rerank",
            json={
                "query": "test",
                "documents": ["a", "b", "c", "d"],
            },
        )
        data = resp.json()
        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_results_contain_index_and_text(self, ready_client) -> None:
        docs = ["first doc", "second doc"]
        resp = ready_client.post(
            "/rerank",
            json={"query": "test", "documents": docs},
        )
        data = resp.json()
        for result in data["results"]:
            assert "index" in result
            assert "score" in result
            assert "text" in result
            assert result["text"] in docs

    def test_top_k_truncation(self, ready_client) -> None:
        docs = [f"doc {i}" for i in range(10)]
        resp = ready_client.post(
            "/rerank",
            json={"query": "test", "documents": docs, "top_k": 3},
        )
        data = resp.json()
        assert len(data["results"]) == 3

    def test_top_k_larger_than_docs(self, ready_client) -> None:
        resp = ready_client.post(
            "/rerank",
            json={"query": "test", "documents": ["a", "b"], "top_k": 100},
        )
        data = resp.json()
        assert len(data["results"]) == 2

    def test_empty_documents_returns_empty_results(self, ready_client) -> None:
        resp = ready_client.post(
            "/rerank",
            json={"query": "test", "documents": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    def test_model_not_ready_returns_503(self, not_ready_client) -> None:
        resp = not_ready_client.post(
            "/rerank",
            json={"query": "test", "documents": ["doc"]},
        )
        assert resp.status_code == 503
