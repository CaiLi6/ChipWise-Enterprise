"""Unit tests for SSE streaming endpoint (§6A2)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.agent.orchestrator import AgentResult, AgentStep
from src.api.middleware.auth import get_current_user
from src.api.routers.query import get_orchestrator, router
from src.api.schemas.auth import UserInfo


def _make_mock_orchestrator(answer: str = "Mock agent answer") -> MagicMock:
    """Build a mock AgentOrchestrator that returns a fixed answer."""
    step = AgentStep(thought="mock thought", observations=[])
    result = AgentResult(
        answer=answer,
        tool_calls_log=[step],
        total_tokens=42,
        iterations=1,
    )
    mock_orch = MagicMock()
    mock_orch.run = AsyncMock(return_value=result)
    return mock_orch


_TEST_USER = UserInfo(sub="test-sub-001", username="test_user", role="user", department="")


@pytest.fixture(scope="module")
def client() -> TestClient:
    mock_orch = _make_mock_orchestrator()

    app = FastAPI()
    app.include_router(router)

    # Override auth and orchestrator dependencies so tests run without
    # a real JWT or LM Studio instance.
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch

    # Disable grounding gate (mock orchestrator returns no citations,
    # which would otherwise trigger abstain and rewrite the answer).
    class _StubSettings:
        grounding = {"enabled": False}
    app.state.settings = _StubSettings()

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
class TestQueryEndpoint:
    def test_standard_query_returns_200(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"query": "What is STM32F407?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data

    def test_query_response_schema(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"query": "test"})
        data = resp.json()
        assert "answer" in data
        assert "citations" in data
        assert isinstance(data["citations"], list)

    def test_query_answer_from_orchestrator(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Mock agent answer"


@pytest.mark.unit
class TestQueryUnavailable:
    """Query endpoint returns 503 when orchestrator is None."""

    def test_returns_503_when_no_orchestrator(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: _TEST_USER
        app.dependency_overrides[get_orchestrator] = lambda: None

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/v1/query", json={"query": "test"})
        assert resp.status_code == 503


@pytest.mark.unit
class TestSSEStreamEndpoint:
    def test_stream_returns_event_stream(self, client: TestClient) -> None:
        with client.stream("POST", "/api/v1/query/stream", json={"query": "hello world"}) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_contains_token_events(self, client: TestClient) -> None:
        events = []
        with client.stream("POST", "/api/v1/query/stream", json={"query": "hello"}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(payload)

        assert len(events) > 0
        event_types = {e["type"] for e in events}
        assert "done" in event_types

    def test_stream_ends_with_done_event(self, client: TestClient) -> None:
        last_event = None
        with client.stream("POST", "/api/v1/query/stream", json={"query": "test"}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    last_event = json.loads(line[6:])

        assert last_event is not None
        assert last_event["type"] == "done"

    def test_done_event_has_trace_id(self, client: TestClient) -> None:
        done_event = None
        with client.stream("POST", "/api/v1/query/stream", json={"query": "test"}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    if payload["type"] == "done":
                        done_event = payload

        assert done_event is not None
        assert "trace_id" in done_event
        assert "citations" in done_event

    def test_stream_no_cache_header(self, client: TestClient) -> None:
        with client.stream("POST", "/api/v1/query/stream", json={"query": "hi"}) as resp:
            assert resp.headers.get("cache-control") == "no-cache"
