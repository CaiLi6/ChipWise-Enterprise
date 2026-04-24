"""Lightweight in-process e2e smoke for /api/v1/query.

Covers the full FastAPI request path without LM Studio, Milvus, PostgreSQL,
or Redis: JWT auth → orchestrator dependency → ResponseBuilder → grounding.
Suitable for CI; runs in well under one second.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.agent.orchestrator import AgentResult, AgentStep, ToolCallRequest
from src.api.main import create_app
from src.api.middleware.auth import get_current_user
from src.api.routers.query import get_orchestrator
from src.api.schemas.auth import UserInfo
from src.core.settings import Settings


class _StubOrchestrator:
    """Deterministic stand-in that returns a grounded answer with citations."""

    async def run(self, *, query: str, trace: Any) -> AgentResult:  # noqa: ARG002
        observation = {
            "results": [
                {
                    "chunk_id": "c1",
                    "doc_id": 1,
                    "content": "PCIe user clock 10 MHz to 300 MHz",
                    "score": 0.92,
                    "page_number": 11,
                    "metadata": {
                        "doc_name": "stub.pdf",
                        "part_number": "XCKU5PFFVD900",
                    },
                },
                {
                    "chunk_id": "c2",
                    "doc_id": 1,
                    "content": "Gen4 x8 supports up to 300 MHz application clock",
                    "score": 0.88,
                    "page_number": 12,
                    "metadata": {
                        "doc_name": "stub.pdf",
                        "part_number": "XCKU5PFFVD900",
                    },
                },
            ]
        }
        step = AgentStep(
            thought="search",
            tool_calls=[ToolCallRequest(tool_name="rag_search", arguments={})],
            observations=[observation],
        )
        return AgentResult(
            answer=(
                "## 结论\n\nXCKU5PFFVD900 PCIe 用户时钟范围为 10 MHz 到 300 MHz。"
            ),
            tool_calls_log=[step],
            iterations=1,
            stopped_reason="complete",
        )


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
        embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        sub="u-1", username="smoke", role="user"
    )
    app.dependency_overrides[get_orchestrator] = lambda: _StubOrchestrator()
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
class TestQuerySmoke:
    def test_query_end_to_end(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/query",
            json={"query": "XCKU5PFFVD900 PCIe 用户时钟频率范围"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "answer" in data
        assert "10 MHz" in data["answer"]
        assert "300 MHz" in data["answer"]
        # Citations propagated from rag_search tool result through ResponseBuilder
        assert isinstance(data.get("citations"), list)
        assert len(data["citations"]) >= 1

    def test_query_returns_503_when_orchestrator_unavailable(
        self, client: TestClient
    ) -> None:
        client.app.dependency_overrides[get_orchestrator] = lambda: None
        resp = client.post("/api/v1/query", json={"query": "anything"})
        assert resp.status_code == 503
