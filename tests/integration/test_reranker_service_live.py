"""Integration tests for bce-reranker Service — requires real model loaded.

Run: pytest -q tests/integration/test_reranker_service_live.py -m integration
Requires: reranker-service running at localhost:8002
"""

from __future__ import annotations

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

BASE_URL = "http://localhost:8002"


@pytest.mark.integration
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestRerankerServiceLive:
    """Live tests against a running reranker service."""

    def _is_service_up(self) -> bool:
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=5)
            return resp.status_code == 200 and resp.json().get("ready") is True
        except Exception:
            return False

    def test_health_ready(self) -> None:
        if not self._is_service_up():
            pytest.skip("Reranker service not available")
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True

    def test_rerank_basic(self) -> None:
        if not self._is_service_up():
            pytest.skip("Reranker service not available")
        resp = httpx.post(
            f"{BASE_URL}/rerank",
            json={
                "query": "STM32 clock frequency",
                "documents": [
                    "The STM32F103 has a maximum clock of 72 MHz",
                    "Python is a programming language",
                ],
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        # The STM32-related doc should rank higher
        assert data["results"][0]["score"] >= data["results"][1]["score"]

    def test_empty_documents(self) -> None:
        if not self._is_service_up():
            pytest.skip("Reranker service not available")
        resp = httpx.post(
            f"{BASE_URL}/rerank",
            json={"query": "test", "documents": []},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_top_k(self) -> None:
        if not self._is_service_up():
            pytest.skip("Reranker service not available")
        docs = [f"document about topic {i}" for i in range(5)]
        resp = httpx.post(
            f"{BASE_URL}/rerank",
            json={"query": "topic 1", "documents": docs, "top_k": 2},
            timeout=30,
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2
