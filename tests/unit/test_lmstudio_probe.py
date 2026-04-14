"""Unit tests for LM Studio background probe (§8C)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.observability.lmstudio_probe import _probe_once, start_lmstudio_probe


@pytest.mark.unit
class TestProbeOnce:
    """Test the single-shot _probe_once function."""

    @pytest.mark.asyncio
    async def test_healthy_when_model_found(self) -> None:
        """Probe returns healthy when /v1/models lists the expected model."""
        cfg = MagicMock()
        cfg.base_url = "http://localhost:1234/v1"
        cfg.model = "qwen3-35b"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"id": "qwen3-35b"}, {"id": "other-model"}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            client_inst = AsyncMock()
            client_inst.get = AsyncMock(return_value=mock_resp)
            client_inst.__aenter__ = AsyncMock(return_value=client_inst)
            client_inst.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_inst

            result = await _probe_once(cfg)

        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_unhealthy_on_connection_error(self) -> None:
        """Probe returns unhealthy when LM Studio is unreachable."""
        cfg = MagicMock()
        cfg.base_url = "http://localhost:1234/v1"
        cfg.model = "qwen3-35b"

        with patch("httpx.AsyncClient") as mock_client:
            client_inst = AsyncMock()
            client_inst.get = AsyncMock(side_effect=Exception("Connection refused"))
            client_inst.__aenter__ = AsyncMock(return_value=client_inst)
            client_inst.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_inst

            result = await _probe_once(cfg)

        assert result["healthy"] is False
        assert "Connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_unhealthy_when_model_not_loaded(self) -> None:
        """Probe returns unhealthy when model is not in the list."""
        cfg = MagicMock()
        cfg.base_url = "http://localhost:1234/v1"
        cfg.model = "qwen3-35b"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"id": "wrong-model"}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            client_inst = AsyncMock()
            client_inst.get = AsyncMock(return_value=mock_resp)
            client_inst.__aenter__ = AsyncMock(return_value=client_inst)
            client_inst.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_inst

            result = await _probe_once(cfg)

        assert result["healthy"] is False


@pytest.mark.unit
class TestStartProbe:
    """Test the start_lmstudio_probe launcher."""

    @pytest.mark.asyncio
    async def test_start_probe_creates_task(self) -> None:
        """start_lmstudio_probe should create an asyncio task."""
        app = MagicMock()
        app.state = MagicMock()

        with (
            patch("src.observability.lmstudio_probe._probe_loop", new_callable=AsyncMock),
            patch("asyncio.create_task") as mock_create,
        ):
            start_lmstudio_probe(app, interval=30)
            mock_create.assert_called_once()
