"""Unit tests for LMStudioClient — mock HTTP for chat + tool calling."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.libs.llm.base import BaseLLM, LLMResponse
from src.libs.llm.factory import LLMFactory
from src.libs.llm.lmstudio_client import LMStudioClient


def _mock_chat_response(text: str = "Hello!", tool_calls: list | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"content": text}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def _mock_tool_call_response() -> dict[str, Any]:
    return _mock_chat_response(text=None, tool_calls=[{
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "rag_search",
            "arguments": json.dumps({"query": "STM32F4 clock speed"}),
        },
    }])


@pytest.mark.unit
class TestLMStudioClient:
    @pytest.mark.asyncio
    async def test_generate_returns_response(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("Generated text.")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.generate("Hello")

        assert isinstance(result, LLMResponse)
        assert result.text == "Generated text."
        assert result.usage["total_tokens"] == 30
        assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_chat_returns_text(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_chat_response("Chat response.")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.chat([{"role": "user", "content": "Hi"}])

        assert result.text == "Chat response."

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_tool_call_response()

        tools = [{"type": "function", "function": {"name": "rag_search"}}]
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.chat([{"role": "user", "content": "Search for STM32"}], tools=tools)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "rag_search"
        assert result.tool_calls[0].arguments["query"] == "STM32F4 clock speed"
        assert result.tool_calls[0].id == "call_123"

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1", timeout=1.0)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")), \
                pytest.raises(httpx.TimeoutException):
            await client.chat([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_connection_error_retries(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")), \
                pytest.raises(httpx.ConnectError):
            await client.generate("test")

    @pytest.mark.asyncio
    async def test_health_check_ok(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_down(self) -> None:
        client = LMStudioClient(base_url="http://fake:1234/v1")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("down")):
            assert await client.health_check() is False

    def test_isinstance_base(self) -> None:
        assert isinstance(LMStudioClient(), BaseLLM)

    @pytest.mark.asyncio
    async def test_parse_response_with_usage(self) -> None:
        data = _mock_chat_response("test")
        result = LMStudioClient._parse_response(data)
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_parse_response_empty_tool_calls(self) -> None:
        data = _mock_chat_response("text", tool_calls=[])
        result = LMStudioClient._parse_response(data)
        assert result.tool_calls is None  # empty list -> None

    @pytest.mark.asyncio
    async def test_parse_response_invalid_args_json(self) -> None:
        data = _mock_chat_response(text=None, tool_calls=[{
            "id": "c1",
            "function": {"name": "t", "arguments": "not json{"},
        }])
        result = LMStudioClient._parse_response(data)
        assert result.tool_calls is not None
        assert result.tool_calls[0].arguments == {}


@pytest.mark.unit
class TestLLMFactory:
    def test_create_primary(self) -> None:
        config = {
            "llm": {
                "primary": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:1234/v1",
                    "model": "qwen3-35b",
                    "api_key": "lm-studio",
                },
            }
        }
        client = LLMFactory.create(config, role="primary")
        assert isinstance(client, LMStudioClient)

    def test_create_router(self) -> None:
        config = {
            "llm": {
                "router": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:1234/v1",
                    "model": "qwen3-1.7b",
                },
            }
        }
        client = LLMFactory.create(config, role="router")
        assert isinstance(client, LMStudioClient)

    def test_unknown_provider_raises(self) -> None:
        config = {"llm": {"primary": {"provider": "anthropic"}}}
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMFactory.create(config, role="primary")

    def test_default_provider(self) -> None:
        config = {"llm": {"primary": {}}}
        client = LLMFactory.create(config, role="primary")
        assert isinstance(client, LMStudioClient)
