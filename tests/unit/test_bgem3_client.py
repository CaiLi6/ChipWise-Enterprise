"""Unit tests for BGEM3Client — mock HTTP to test request/response contract."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any

import httpx

from src.libs.embedding.base import BaseEmbedding, EmbeddingResult
from src.libs.embedding.bgem3_client import BGEM3Client
from src.libs.embedding.factory import EmbeddingFactory


def _mock_encode_response(n_texts: int = 1, dim: int = 1024) -> dict[str, Any]:
    return {
        "dense": [[0.1] * dim for _ in range(n_texts)],
        "sparse": [{str(i): 0.5 for i in range(10)} for _ in range(n_texts)],
    }


@pytest.mark.unit
class TestBGEM3Client:
    @pytest.mark.asyncio
    async def test_encode_single_text(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_encode_response(1, 1024)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.encode(["hello world"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.dense) == 1
        assert result.dimensions == 1024
        assert len(result.sparse) == 1
        assert all(isinstance(k, int) for k in result.sparse[0])

    @pytest.mark.asyncio
    async def test_encode_batch(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_encode_response(5, 1024)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.encode(["text"] * 5)

        assert len(result.dense) == 5
        assert len(result.sparse) == 5

    @pytest.mark.asyncio
    async def test_encode_no_sparse(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"dense": [[0.1] * 1024], "sparse": []}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.encode(["test"], return_sparse=False)

        assert result.dimensions == 1024
        assert result.sparse == []

    @pytest.mark.asyncio
    async def test_server_error_raises(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                await client.encode(["test"])

    @pytest.mark.asyncio
    async def test_timeout_retries(self) -> None:
        """Connection timeout should trigger retries then raise."""
        client = BGEM3Client(base_url="http://fake:8001")

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(httpx.ConnectError):
                await client.encode(["test"])

    @pytest.mark.asyncio
    async def test_health_check_ok(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_down(self) -> None:
        client = BGEM3Client(base_url="http://fake:8001")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            assert await client.health_check() is False

    def test_isinstance_base(self) -> None:
        client = BGEM3Client()
        assert isinstance(client, BaseEmbedding)


@pytest.mark.unit
class TestEmbeddingFactory:
    def test_create_bgem3(self) -> None:
        config = {"embedding": {"provider": "bgem3", "base_url": "http://localhost:8001"}}
        client = EmbeddingFactory.create(config)
        assert isinstance(client, BGEM3Client)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            EmbeddingFactory.create({"embedding": {"provider": "openai"}})
