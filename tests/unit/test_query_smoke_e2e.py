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
from src.api.dependencies import get_redis
from src.api.main import create_app
from src.api.middleware.auth import get_current_user
from src.api.routers.query import get_orchestrator
from src.api.schemas.auth import UserInfo
from src.core.conversation_manager import ConversationManager
from src.core.settings import Settings


class _StubOrchestrator:
    """Deterministic stand-in that returns a grounded answer with citations."""

    def __init__(self) -> None:
        self.last_query = ""
        self.last_history: list[dict[str, Any]] = []

    async def run(
        self,
        *,
        query: str,
        trace: Any,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AgentResult:  # noqa: ARG002
        self.last_query = query
        self.last_history = conversation_history or []
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


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int = 0) -> None:  # noqa: ARG002
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture
def orchestrator() -> _StubOrchestrator:
    return _StubOrchestrator()


@pytest.fixture
def client(orchestrator: _StubOrchestrator) -> TestClient:
    settings = Settings(
        llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
        embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
    )
    settings.cache.enabled = False
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        sub="u-1", username="smoke", role="user"
    )
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_redis] = lambda: None
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

    def test_stream_query_emits_status_and_tokens(self, client: TestClient) -> None:
        with client.stream(
            "POST",
            "/api/v1/query/stream",
            json={"query": "XCKU5PFFVD900 PCIe 用户时钟频率范围"},
        ) as resp:
            body = "".join(resp.iter_text())
        assert resp.status_code == 200
        assert '"type": "status"' in body
        assert '"type": "token"' in body
        assert '"type": "done"' in body

    @pytest.mark.asyncio
    async def test_query_passes_backend_memory_and_stores_answer(
        self, orchestrator: _StubOrchestrator
    ) -> None:
        settings = Settings(
            llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
            embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
        )
        settings.cache.enabled = False
        app = create_app(settings)
        fake_redis = _FakeRedis()
        manager = ConversationManager(fake_redis)
        await manager.append_turn("u-1", "s1", "user", "先看 XCKU5PFFVD900")

        app.dependency_overrides[get_current_user] = lambda: UserInfo(
            sub="u-1", username="smoke", role="user"
        )
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator
        app.dependency_overrides[get_redis] = lambda: fake_redis

        with TestClient(app, raise_server_exceptions=False) as test_client:
            resp = test_client.post(
                "/api/v1/query",
                json={"query": "XCKU5PFFVD900 PCIe 用户时钟频率范围", "session_id": "s1"},
            )

        assert resp.status_code == 200, resp.text
        assert orchestrator.last_history
        assert any("先看 XCKU5PFFVD900" in m["content"] for m in orchestrator.last_history)
        stored_history = await manager.get_history("u-1", "s1")
        assert stored_history[-1]["role"] == "assistant"
        assert "10 MHz" in stored_history[-1]["content"]
