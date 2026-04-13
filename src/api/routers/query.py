"""Query router: standard + SSE streaming endpoints (§6A2)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    citations: list[dict] = []
    trace_id: str = ""


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Standard (non-streaming) query endpoint."""
    # Delegates to Agent Orchestrator when wired up via DI
    return QueryResponse(
        answer=f"Query received: {req.query}",
        citations=[],
        trace_id="",
    )


@router.post("/query/stream")
async def stream_query(req: QueryRequest) -> StreamingResponse:
    """SSE streaming query endpoint.

    Streams LLM tokens as Server-Sent Events:
      data: {"type": "token", "content": "..."}\n\n
      data: {"type": "done", "citations": [...], "trace_id": "..."}\n\n
    """

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            # Placeholder streaming — replace with real Agent SSE in integration
            words = req.query.split()
            for word in words:
                payload = json.dumps({"type": "token", "content": word + " "})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.05)  # Simulate streaming delay

            done = json.dumps({
                "type": "done",
                "citations": [],
                "trace_id": "stream-placeholder",
            })
            yield f"data: {done}\n\n"
        except asyncio.CancelledError:
            # Client disconnected — clean exit, no resource leak
            logger.debug("SSE client disconnected")
        except Exception:
            logger.exception("SSE stream error")
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
