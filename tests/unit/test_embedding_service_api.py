"""Unit tests for BGE-M3 Embedding Service API — model is mocked."""

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
    """Return a mock FlagModel that produces deterministic outputs."""
    model = MagicMock()

    def mock_encode(texts, return_dense=True, return_sparse=False, return_colbert_vecs=False):
        n = len(texts)
        result = {}
        if return_dense:
            result["dense_vecs"] = np.random.rand(n, 1024).astype(np.float32)
        if return_sparse:
            result["lexical_weights"] = [
                {101: 0.5, 202: 0.3} for _ in range(n)
            ]
        return result

    model.encode.side_effect = mock_encode
    return model


def _make_test_app(svc_module) -> FastAPI:
    """Build a copy of the app without the real lifespan (no model load)."""

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(title="Test Embedding Service", lifespan=noop_lifespan)
    # Re-register routes from the real app
    for route in svc_module.app.routes:
        test_app.routes.append(route)
    return test_app


@pytest.fixture
def ready_client(mock_model):
    """TestClient with model loaded and ready."""
    import src.services.embedding_service as svc

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
    import src.services.embedding_service as svc

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
        assert data["model"] == "BAAI/bge-m3"
        assert data["ready"] is True

    def test_health_not_ready(self, not_ready_client) -> None:
        resp = not_ready_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is False
        assert data["status"] == "loading"


# ── Encode endpoint ─────────────────────────────────────────────────


@pytest.mark.unit
class TestEncodeEndpoint:
    def test_single_text_dense_and_sparse(self, ready_client) -> None:
        resp = ready_client.post(
            "/encode",
            json={"texts": ["hello world"], "return_sparse": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimensions"] == 1024
        assert data["model"] == "BAAI/bge-m3"
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024
        assert data["sparse"] is not None
        assert len(data["sparse"]) == 1

    def test_single_text_dense_only(self, ready_client) -> None:
        resp = ready_client.post(
            "/encode",
            json={"texts": ["hello world"], "return_sparse": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 1
        assert data["sparse"] is None

    def test_batch_texts(self, ready_client) -> None:
        texts = [f"text {i}" for i in range(10)]
        resp = ready_client.post(
            "/encode",
            json={"texts": texts, "return_sparse": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 10
        assert len(data["sparse"]) == 10

    def test_max_batch_size(self, ready_client) -> None:
        """Exactly 64 texts should succeed."""
        texts = [f"text {i}" for i in range(64)]
        resp = ready_client.post(
            "/encode",
            json={"texts": texts, "return_sparse": False},
        )
        assert resp.status_code == 200
        assert len(resp.json()["dense"]) == 64

    def test_empty_texts_returns_400(self, ready_client) -> None:
        resp = ready_client.post(
            "/encode",
            json={"texts": [], "return_sparse": True},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_exceed_batch_size_returns_422(self, ready_client) -> None:
        texts = [f"text {i}" for i in range(65)]
        resp = ready_client.post(
            "/encode",
            json={"texts": texts, "return_sparse": False},
        )
        assert resp.status_code == 422
        assert "exceeds" in resp.json()["detail"].lower()

    def test_model_not_ready_returns_503(self, not_ready_client) -> None:
        resp = not_ready_client.post(
            "/encode",
            json={"texts": ["test"]},
        )
        assert resp.status_code == 503


# ── Sparse vector format ────────────────────────────────────────────


@pytest.mark.unit
class TestSparseVectorFormat:
    def test_sparse_keys_are_strings(self, ready_client) -> None:
        resp = ready_client.post(
            "/encode",
            json={"texts": ["test"], "return_sparse": True},
        )
        data = resp.json()
        sparse = data["sparse"][0]
        assert all(isinstance(k, str) for k in sparse)

    def test_sparse_values_are_floats(self, ready_client) -> None:
        resp = ready_client.post(
            "/encode",
            json={"texts": ["test"], "return_sparse": True},
        )
        data = resp.json()
        sparse = data["sparse"][0]
        assert all(isinstance(v, float) for v in sparse.values())
