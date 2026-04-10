"""Unit tests for request logger middleware."""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.request_logger import (
    QUIET_PATHS,
    RequestLoggerMiddleware,
    _extract_user_agent,
    _extract_user_id,
    _sanitize_headers,
)
from src.observability.logger import JSONFormatter


# ── Helper sanitization ─────────────────────────────────────────────


@pytest.mark.unit
class TestSanitizeHeaders:
    def test_normal_header_kept(self) -> None:
        headers = [(b"content-type", b"application/json")]
        result = _sanitize_headers(headers)
        assert result["content-type"] == "application/json"

    def test_authorization_bearer_masked(self) -> None:
        headers = [(b"authorization", b"Bearer eyJhbGciOiJIUzI1NiJ9.secret")]
        result = _sanitize_headers(headers)
        assert result["authorization"] == "Bearer ***"

    def test_authorization_other_masked(self) -> None:
        headers = [(b"Authorization", b"Basic dXNlcjpwYXNz")]
        result = _sanitize_headers(headers)
        assert result["authorization"] == "***"


@pytest.mark.unit
class TestExtractHelpers:
    def test_extract_user_agent(self) -> None:
        headers = [
            (b"host", b"localhost"),
            (b"user-agent", b"TestClient/1.0"),
        ]
        assert _extract_user_agent(headers) == "TestClient/1.0"

    def test_extract_user_agent_missing(self) -> None:
        assert _extract_user_agent([]) == ""

    def test_extract_user_id(self) -> None:
        headers = [(b"x-user-id", b"user123")]
        assert _extract_user_id(headers) == "user123"

    def test_extract_user_id_missing(self) -> None:
        assert _extract_user_id([]) == ""


# ── Middleware integration tests ────────────────────────────────────


def _build_test_app(suppress_health: bool = True) -> FastAPI:
    """Build a minimal FastAPI app with RequestLoggerMiddleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"msg": "ok"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Wrap with middleware
    app = RequestLoggerMiddleware(app, suppress_health=suppress_health)
    return app


@pytest.mark.unit
class TestRequestLoggerMiddleware:
    def test_response_has_x_request_id(self) -> None:
        """Every response should include X-Request-ID header."""
        app = _build_test_app()
        # Use raw ASGI TestClient
        from starlette.testclient import TestClient as StarletteClient

        with StarletteClient(app) as client:
            resp = client.get("/test")

        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        # Verify it's a valid UUID format
        request_id = resp.headers["x-request-id"]
        assert len(request_id) == 36  # UUID format: 8-4-4-4-12

    def test_health_gets_x_request_id_too(self) -> None:
        """Even quiet paths get the X-Request-ID header."""
        app = _build_test_app()
        from starlette.testclient import TestClient as StarletteClient

        with StarletteClient(app) as client:
            resp = client.get("/health")
        assert "x-request-id" in resp.headers

    def test_request_logged_with_json(self, caplog) -> None:
        """Request logs should be valid JSON."""
        app = _build_test_app(suppress_health=False)
        from starlette.testclient import TestClient as StarletteClient

        with caplog.at_level(logging.INFO, logger="chipwise.request"):
            with StarletteClient(app) as client:
                client.get("/test")

        json_logs = []
        for record in caplog.records:
            if record.name == "chipwise.request":
                try:
                    parsed = json.loads(record.getMessage())
                    json_logs.append(parsed)
                except json.JSONDecodeError:
                    pass

        assert len(json_logs) >= 2  # request_start + request_end
        events = [l["event"] for l in json_logs]
        assert "request_start" in events
        assert "request_end" in events

    def test_request_end_has_latency(self, caplog) -> None:
        """Outbound log should include latency_ms."""
        app = _build_test_app(suppress_health=False)
        from starlette.testclient import TestClient as StarletteClient

        with caplog.at_level(logging.INFO, logger="chipwise.request"):
            with StarletteClient(app) as client:
                client.get("/test")

        for record in caplog.records:
            if record.name == "chipwise.request":
                try:
                    data = json.loads(record.getMessage())
                    if data.get("event") == "request_end":
                        assert "latency_ms" in data
                        assert data["latency_ms"] >= 0
                        return
                except json.JSONDecodeError:
                    pass
        pytest.fail("No request_end log found with latency_ms")

    def test_health_suppressed_by_default(self, caplog) -> None:
        """Health endpoint should not produce request logs when suppressed."""
        app = _build_test_app(suppress_health=True)
        from starlette.testclient import TestClient as StarletteClient

        with caplog.at_level(logging.INFO, logger="chipwise.request"):
            with StarletteClient(app) as client:
                client.get("/health")

        request_logs = [
            r for r in caplog.records if r.name == "chipwise.request"
        ]
        assert len(request_logs) == 0

    def test_health_logged_when_not_suppressed(self, caplog) -> None:
        """Health logs appear when suppression is disabled."""
        app = _build_test_app(suppress_health=False)
        from starlette.testclient import TestClient as StarletteClient

        with caplog.at_level(logging.INFO, logger="chipwise.request"):
            with StarletteClient(app) as client:
                client.get("/health")

        request_logs = [
            r for r in caplog.records if r.name == "chipwise.request"
        ]
        assert len(request_logs) >= 2


# ── JSONFormatter ───────────────────────────────────────────────────


@pytest.mark.unit
class TestJSONFormatter:
    def test_format_produces_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert "timestamp" in data

    def test_format_with_exception(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="", lineno=0,
                msg="error occurred", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]
