"""Request logger ASGI middleware: inject X-Request-ID and log requests/responses.

Features:
- UUID request_id on every request (X-Request-ID header)
- Structured JSON inbound/outbound logs
- Sensitive data sanitization (Authorization, password)
- Configurable health endpoint suppression
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("chipwise.request")

# Paths whose logs are suppressed by default (health check noise)
QUIET_PATHS: set[str] = {"/health", "/readiness"}

# Headers to sanitize in logs
_SENSITIVE_HEADERS = {b"authorization"}

# Body fields to sanitize
_SENSITIVE_FIELDS = {"password", "secret", "token", "api_key"}


def _sanitize_headers(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Convert ASGI headers to dict, masking sensitive values."""
    result: dict[str, str] = {}
    for name, value in headers:
        key = name.decode("latin-1").lower()
        if name.lower() in _SENSITIVE_HEADERS:
            # Show prefix only
            val = value.decode("latin-1", errors="replace")
            if val.lower().startswith("bearer "):
                result[key] = "Bearer ***"
            else:
                result[key] = "***"
        else:
            result[key] = value.decode("latin-1", errors="replace")
    return result


def _extract_user_agent(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == b"user-agent":
            return value.decode("latin-1", errors="replace")
    return ""


def _extract_user_id(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == b"x-user-id":
            return value.decode("latin-1", errors="replace")
    return ""


class RequestLoggerMiddleware:
    """ASGI middleware that logs structured request/response info."""

    def __init__(self, app: Any, suppress_health: bool = True):
        self.app = app
        self.suppress_health = suppress_health

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        path = scope.get("path", "")
        method = scope.get("method", "")
        headers = scope.get("headers", [])
        start_time = time.monotonic()

        # Determine if this is a quiet path
        is_quiet = self.suppress_health and path in QUIET_PATHS

        # Log inbound request
        if not is_quiet:
            logger.info(
                json.dumps({
                    "event": "request_start",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "user_agent": _extract_user_agent(headers),
                    "user_id": _extract_user_id(headers),
                }, ensure_ascii=False)
            )

        # Inject request_id into scope extensions for downstream access
        if "extensions" not in scope:
            scope["extensions"] = {}
        scope["extensions"]["request_id"] = request_id

        # Intercept response to capture status code and inject X-Request-ID
        response_status = 0
        response_size = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal response_status, response_size

            if message["type"] == "http.response.start":
                response_status = message.get("status", 0)
                # Inject X-Request-ID header
                resp_headers = list(message.get("headers", []))
                resp_headers.append([b"x-request-id", request_id.encode()])
                message = {**message, "headers": resp_headers}

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_size += len(body)

            await send(message)

        await self.app(scope, receive, send_wrapper)

        # Log outbound response
        elapsed_ms = (time.monotonic() - start_time) * 1000
        if not is_quiet:
            logger.info(
                json.dumps({
                    "event": "request_end",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": response_status,
                    "latency_ms": round(elapsed_ms, 2),
                    "response_size": response_size,
                }, ensure_ascii=False)
            )
