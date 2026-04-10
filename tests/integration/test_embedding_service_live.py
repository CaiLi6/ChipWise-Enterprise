"""Integration tests for BGE-M3 Embedding Service — requires real model loaded.

Run: pytest -q tests/integration/test_embedding_service_live.py -m integration
Requires: embedding-service running at localhost:8001
"""

from __future__ import annotations

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

BASE_URL = "http://localhost:8001"


@pytest.mark.integration
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestEmbeddingServiceLive:
    """Live tests against a running embedding service."""

    def _is_service_up(self) -> bool:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5)
            return resp.status_code == 200 and resp.json().get("ready") is True
        except Exception:
            return False

    def test_health_ready(self) -> None:
        if not self._is_service_up():
            pytest.skip("Embedding service not available")
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["model"] == "BAAI/bge-m3"

    def test_encode_single_dense(self) -> None:
        if not self._is_service_up():
            pytest.skip("Embedding service not available")
        resp = httpx.post(
            f"{BASE_URL}/encode",
            json={"texts": ["STM32F103 clock frequency"], "return_sparse": False},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimensions"] == 1024
        assert len(data["dense"]) == 1
        assert len(data["dense"][0]) == 1024

    def test_encode_with_sparse(self) -> None:
        if not self._is_service_up():
            pytest.skip("Embedding service not available")
        resp = httpx.post(
            f"{BASE_URL}/encode",
            json={"texts": ["hello world"], "return_sparse": True},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sparse"] is not None
        assert len(data["sparse"]) == 1

    def test_encode_batch(self) -> None:
        if not self._is_service_up():
            pytest.skip("Embedding service not available")
        texts = [f"chip parameter {i}" for i in range(5)]
        resp = httpx.post(
            f"{BASE_URL}/encode",
            json={"texts": texts, "return_sparse": True},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dense"]) == 5
        assert len(data["sparse"]) == 5

    def test_empty_texts_rejected(self) -> None:
        if not self._is_service_up():
            pytest.skip("Embedding service not available")
        resp = httpx.post(
            f"{BASE_URL}/encode",
            json={"texts": []},
            timeout=10,
        )
        assert resp.status_code == 400
