"""Query router: standard + SSE streaming endpoints (§6A2)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.middleware.auth import get_current_user
from src.api.schemas.auth import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

# ---------------------------------------------------------------------------
# Singleton orchestrator — created lazily on the first request.
# None when LLM / dependencies are unavailable (graceful degradation).
# ---------------------------------------------------------------------------
_orchestrator: Any = None
_orchestrator_initialized = False


def _get_or_create_orchestrator() -> Any:
    """Return (or create) the singleton AgentOrchestrator.

    Returns None when the LLM or tool dependencies are unavailable so that
    callers can degrade gracefully rather than crash.

    When LM Studio recovers after being down, resets the singleton so the
    orchestrator can be rebuilt on the next request.
    """
    global _orchestrator, _orchestrator_initialized
    if _orchestrator_initialized:
        return _orchestrator

    _orchestrator_initialized = True
    try:
        from src.agent.orchestrator import AgentConfig, AgentOrchestrator
        from src.agent.tool_registry import ToolRegistry
        from src.api.dependencies import get_settings
        from src.libs.llm.factory import LLMFactory

        settings = get_settings()
        llm = LLMFactory.create(settings.model_dump(), role="primary")

        registry = ToolRegistry()
        registry.discover()

        config = AgentConfig(
            max_iterations=settings.agent.max_iterations,
            max_total_tokens=settings.agent.max_total_tokens,
            parallel_tool_calls=settings.agent.parallel_tool_calls,
            temperature=settings.agent.temperature,
            tool_timeout=settings.agent.tool_timeout,
        )
        _orchestrator = AgentOrchestrator(llm=llm, tool_registry=registry, config=config)
        logger.info(
            "AgentOrchestrator initialised with %d tools: %s",
            len(registry),
            registry.list_tools(),
        )
    except Exception as exc:
        logger.warning("AgentOrchestrator unavailable: %s", exc)
        _orchestrator = None

    return _orchestrator


def get_orchestrator() -> Any:
    """FastAPI-compatible dependency for the AgentOrchestrator singleton."""
    return _get_or_create_orchestrator()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    citations: list[dict] = []
    trace_id: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_citations(tool_calls_log: list[Any]) -> list[dict[str, Any]]:
    """Pull citation dicts out of tool observation payloads."""
    citations: list[dict[str, Any]] = []
    for step in tool_calls_log:
        for obs in step.observations:
            if isinstance(obs, dict):
                citations.extend(obs.get("citations", []))
    return citations


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    orchestrator: Any = Depends(get_orchestrator),  # noqa: B008
) -> QueryResponse:
    """Standard (non-streaming) query endpoint — delegates to AgentOrchestrator.

    Returns 503 with a descriptive message when the LLM service is unavailable.
    """
    trace_id = getattr(request.state, "trace_id", "")

    # Fast-fail: check LM Studio health before entering orchestrator
    lm_status = getattr(request.app.state, "lmstudio_status", None)
    if lm_status:
        primary = lm_status.get("lmstudio_primary", {})
        if not primary.get("healthy", True):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service temporarily unavailable",
                headers={"Retry-After": "30"},
            )
        # Auto-heal: if LM Studio recovered but orchestrator is still None, rebuild
        if primary.get("healthy") and orchestrator is None:
            global _orchestrator_initialized
            _orchestrator_initialized = False
            orchestrator = _get_or_create_orchestrator()

    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Agent Orchestrator unavailable — "
                "check that LM Studio is running and tools are configured"
            ),
        )

    from src.observability.trace_context import TraceContext

    trace = TraceContext(trace_id=trace_id)

    try:
        result = await orchestrator.run(query=req.query, trace=trace)
    except Exception as exc:
        logger.error("Agent run failed (trace=%s): %s", trace_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent error: {exc}",
        ) from exc

    return QueryResponse(
        answer=result.answer,
        citations=_extract_citations(result.tool_calls_log),
        trace_id=trace_id,
    )


@router.post("/query/stream")
async def stream_query(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    orchestrator: Any = Depends(get_orchestrator),  # noqa: B008
) -> StreamingResponse:
    """SSE streaming query endpoint.

    Streams LLM tokens as Server-Sent Events::

        data: {"type": "token", "content": "..."}\n\n
        data: {"type": "done", "citations": [...], "trace_id": "..."}\n\n

    Returns a single ``error`` event when the Agent is unavailable.
    """
    trace_id = getattr(request.state, "trace_id", "")

    async def _generate() -> AsyncGenerator[str, None]:
        # Fast-fail: check LM Studio health
        lm_status = getattr(request.app.state, "lmstudio_status", None)
        if lm_status:
            primary = lm_status.get("lmstudio_primary", {})
            if not primary.get("healthy", True):
                err = json.dumps({
                    "type": "error",
                    "content": "LLM service temporarily unavailable",
                })
                yield f"data: {err}\n\n"
                return

        if orchestrator is None:
            err = json.dumps({
                "type": "error",
                "content": "Agent Orchestrator unavailable — check LM Studio",
            })
            yield f"data: {err}\n\n"
            return

        try:
            from src.observability.trace_context import TraceContext

            trace = TraceContext(trace_id=trace_id)
            result = await orchestrator.run(query=req.query, trace=trace)

            # Emit answer word-by-word as token events
            words = result.answer.split()
            for word in words:
                payload = json.dumps({"type": "token", "content": word + " "})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)  # yield control between words

            citations = _extract_citations(result.tool_calls_log)
            done = json.dumps({
                "type": "done",
                "citations": citations,
                "trace_id": trace_id,
            })
            yield f"data: {done}\n\n"

        except asyncio.CancelledError:
            logger.debug("SSE client disconnected (trace=%s)", trace_id)
        except Exception:
            logger.exception("SSE stream error (trace=%s)", trace_id)
            err = json.dumps({"type": "error", "content": "Stream failed"})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
