"""Unit tests for BCERerankerClient — mock HTTP."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.libs.reranker.base import BaseReranker, NoneReranker, RerankResult
from src.libs.reranker.bce_client import BCERerankerClient
from src.libs.reranker.factory import RerankerFactory


def _mock_rerank_response() -> dict:
    return {
        "results": [
            {"index": 2, "score": 0.95, "text": "doc2"},
            {"index": 0, "score": 0.88, "text": "doc0"},
            {"index": 1, "score": 0.72, "text": "doc1"},
        ]
    }


@pytest.mark.unit
class TestBCERerankerClient:
    @pytest.mark.asyncio
    async def test_rerank_returns_sorted(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_rerank_response()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            results = await client.rerank("query", ["doc0", "doc1", "doc2"], top_k=3)

        assert len(results) == 3
        assert all(isinstance(r, RerankResult) for r in results)
        # Must be sorted by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_rerank_top_k_limit(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_rerank_response()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            results = await client.rerank("query", ["d0", "d1", "d2"], top_k=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_server_error_raises(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp), \
                pytest.raises(httpx.HTTPStatusError):
            await client.rerank("q", ["d"])

    @pytest.mark.asyncio
    async def test_connection_error_retries(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")), \
                pytest.raises(httpx.ConnectError):
            await client.rerank("q", ["d"])

    @pytest.mark.asyncio
    async def test_health_check_ok(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_down(self) -> None:
        client = BCERerankerClient(base_url="http://fake:8002")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            assert await client.health_check() is False

    def test_isinstance_base(self) -> None:
        assert isinstance(BCERerankerClient(), BaseReranker)


@pytest.mark.unit
class TestNoneReranker:
    @pytest.mark.asyncio
    async def test_passthrough_order(self) -> None:
        rr = NoneReranker()
        results = await rr.rerank("query", ["a", "b", "c"])
        assert len(results) == 3
        assert results[0].text == "a"
        assert results[1].text == "b"

    @pytest.mark.asyncio
    async def test_top_k_respected(self) -> None:
        rr = NoneReranker()
        results = await rr.rerank("query", ["a", "b", "c", "d"], top_k=2)
        assert len(results) == 2

    def test_isinstance_base(self) -> None:
        assert isinstance(NoneReranker(), BaseReranker)


@pytest.mark.unit
class TestRerankerFactory:
    def test_create_bce(self) -> None:
        config = {"rerank": {"provider": "bce", "base_url": "http://localhost:8002"}}
        client = RerankerFactory.create(config)
        assert isinstance(client, BCERerankerClient)

    def test_create_none(self) -> None:
        config = {"rerank": {"provider": "none"}}
        client = RerankerFactory.create(config)
        assert isinstance(client, NoneReranker)

    def test_default_is_none(self) -> None:
        config = {"rerank": {}}
        client = RerankerFactory.create(config)
        assert isinstance(client, NoneReranker)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown reranker provider"):
            RerankerFactory.create({"rerank": {"provider": "cohere"}})
