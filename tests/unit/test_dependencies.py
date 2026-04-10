"""Unit tests for DI container — all external connections mocked."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.dependencies import (
    EmbeddingClient,
    RerankerClient,
    get_embedding_client,
    get_reranker_client,
    get_settings,
    override_settings,
)
from src.core.settings import Settings


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singletons between tests."""
    import src.api.dependencies as deps

    deps._settings_instance = None
    deps._db_pool = None
    deps._redis_client = None
    yield
    deps._settings_instance = None
    deps._db_pool = None
    deps._redis_client = None


@pytest.fixture
def default_settings() -> Settings:
    return Settings(
        llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
        embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
    )


# ── get_settings ────────────────────────────────────────────────────


@pytest.mark.unit
class TestGetSettings:
    def test_returns_settings_instance(self) -> None:
        """get_settings returns a valid Settings object."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_singleton_same_object(self) -> None:
        """Multiple calls return the same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_override_settings(self, default_settings) -> None:
        """override_settings replaces the singleton."""
        override_settings(default_settings)
        assert get_settings() is default_settings


# ── EmbeddingClient ─────────────────────────────────────────────────


@pytest.mark.unit
class TestEmbeddingClient:
    def test_init(self) -> None:
        client = EmbeddingClient(base_url="http://localhost:8001", timeout=30)
        assert client.base_url == "http://localhost:8001"
        assert client.timeout == 30

    def test_trailing_slash_stripped(self) -> None:
        client = EmbeddingClient(base_url="http://localhost:8001/")
        assert client.base_url == "http://localhost:8001"

    @pytest.mark.asyncio
    async def test_encode_calls_post(self) -> None:
        client = EmbeddingClient(base_url="http://localhost:8001")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "dense": [[0.1] * 1024],
            "sparse": [{"101": 0.5}],
            "dimensions": 1024,
            "model": "BAAI/bge-m3",
        }
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            result = await client.encode(["test"])

        assert result["dimensions"] == 1024
        mock_http.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_returns_false_on_error(self) -> None:
        client = EmbeddingClient(base_url="http://localhost:9999")

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=ConnectionError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            result = await client.health()

        assert result is False


# ── RerankerClient ──────────────────────────────────────────────────


@pytest.mark.unit
class TestRerankerClient:
    def test_init(self) -> None:
        client = RerankerClient(base_url="http://localhost:8002", timeout=10)
        assert client.base_url == "http://localhost:8002"

    @pytest.mark.asyncio
    async def test_rerank_calls_post(self) -> None:
        client = RerankerClient(base_url="http://localhost:8002")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"index": 0, "score": 0.9, "text": "doc"}],
            "model": "bce-reranker",
        }
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            result = await client.rerank("query", ["doc"])

        assert len(result["results"]) == 1


# ── Factory functions ───────────────────────────────────────────────


@pytest.mark.unit
class TestFactoryFunctions:
    def test_get_embedding_client(self, default_settings) -> None:
        override_settings(default_settings)
        client = get_embedding_client(default_settings)
        assert isinstance(client, EmbeddingClient)
        assert "8001" in client.base_url

    def test_get_reranker_client(self, default_settings) -> None:
        override_settings(default_settings)
        client = get_reranker_client(default_settings)
        assert isinstance(client, RerankerClient)
        assert "8002" in client.base_url
