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
        from src.agent.tools.graph_query import GraphQueryTool
        from src.agent.tools.rag_search import RAGSearchTool
        from src.api.dependencies import get_settings
        from src.libs.embedding.factory import EmbeddingFactory
        from src.libs.llm.factory import LLMFactory
        from src.libs.reranker.factory import RerankerFactory
        from src.libs.vector_store.factory import VectorStoreFactory
        from src.retrieval.graph_search import GraphSearch
        from src.retrieval.hybrid_search import HybridSearch
        from src.retrieval.reranker import CoreReranker

        settings = get_settings()
        cfg = settings.model_dump()
        llm = LLMFactory.create(cfg, role="primary")

        registry = ToolRegistry()

        # Manually register tools that require injected dependencies. Each
        # block is isolated so a single backend failure does not block the
        # rest of the toolset.
        hybrid: HybridSearch | None = None
        core_reranker: CoreReranker | None = None
        graph_search: GraphSearch | None = None

        try:
            embedding = EmbeddingFactory.create(cfg)
            vector_store = VectorStoreFactory.create(cfg)
            sparse = cfg.get("retrieval", {}).get("sparse_method", "bgem3")
            hybrid = HybridSearch(embedding, vector_store, sparse_method=sparse)
        except Exception:
            logger.warning("HybridSearch init failed", exc_info=True)

        try:
            reranker_backend = RerankerFactory.create(cfg)
            core_reranker = CoreReranker(reranker_backend)
        except Exception:
            logger.warning("CoreReranker init failed", exc_info=True)

        try:
            from src.api.dependencies import get_graph_store
            graph_store = get_graph_store(settings)
            if graph_store is not None:
                graph_search = GraphSearch(graph_store)
        except Exception:
            logger.warning("GraphSearch init failed", exc_info=True)

        if hybrid is not None and core_reranker is not None:
            try:
                registry.register(RAGSearchTool(hybrid, core_reranker, graph_search))
            except Exception:
                logger.warning("RAGSearchTool register failed", exc_info=True)
        else:
            logger.warning("RAGSearchTool skipped: hybrid or reranker unavailable")

        if graph_search is not None:
            try:
                registry.register(GraphQueryTool(graph_search))
            except Exception:
                logger.warning("GraphQueryTool register failed", exc_info=True)

        # Discover remaining zero-arg (or optional-arg) tools
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
# Online evaluation sampling
# ---------------------------------------------------------------------------

_judge_llm: Any = None
_judge_model_name: str = ""
_judge_resolved: bool = False


def _get_judge_llm() -> tuple[Any, str]:
    """Lazy-initialize the online-eval judge (router 1.7B by default)."""
    global _judge_llm, _judge_model_name, _judge_resolved
    if _judge_resolved:
        return _judge_llm, _judge_model_name
    _judge_resolved = True
    try:
        from src.api.dependencies import get_settings
        from src.libs.llm.factory import LLMFactory

        settings = get_settings()
        cfg = settings.model_dump()
        _judge_llm = LLMFactory.create(cfg, role="router")
        _judge_model_name = cfg.get("llm", {}).get("router", {}).get("model", "router")
    except Exception as exc:  # noqa: BLE001
        logger.warning("online-eval judge unavailable: %s", exc)
        _judge_llm = None
        _judge_model_name = ""
    return _judge_llm, _judge_model_name


def _schedule_online_eval(
    request: Request,
    trace_id: str,
    query: str,
    answer: str,
    citations: list[dict[str, Any]],
    iterations: int,
    duration_ms: float,
) -> None:
    """Fire-and-forget trigger for the online eval sampler.

    Sample rate and enablement come from settings (defaults to 10% when the
    evaluation config block is absent so the feature is on by default).
    """
    try:
        from src.api.dependencies import get_settings
        from src.evaluation.online_sampler import maybe_evaluate

        settings = get_settings()
        eval_cfg = getattr(settings, "evaluation", None)
        if eval_cfg and getattr(eval_cfg, "online_enabled", True) is False:
            return
        sample_rate = getattr(eval_cfg, "online_sample_rate", 0.1) if eval_cfg else 0.1

        judge_llm, judge_name = _get_judge_llm()
        if judge_llm is None:
            return

        sample = {
            "trace_id": trace_id,
            "query": query,
            "answer": answer,
            "contexts": [c.get("content", "") for c in citations if c.get("content")],
            "citations": citations,
            "duration_ms": duration_ms,
            "iterations": iterations,
        }
        maybe_evaluate(
            sample,
            judge_llm=judge_llm,
            judge_model_name=judge_name,
            sample_rate=sample_rate,
        )
    except Exception:  # noqa: BLE001
        logger.warning("online-eval schedule failed", exc_info=True)


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


def _build_grounding_config(request: Request) -> Any:
    """Read grounding thresholds from settings; return ``None`` on any failure."""
    try:
        from src.evaluation.grounding import RetrievalGateConfig

        settings = request.app.state.settings if hasattr(request.app.state, "settings") else None
        cfg: dict[str, Any] = {}
        if settings is not None:
            cfg = getattr(settings, "grounding", None) or {}
            if hasattr(cfg, "model_dump"):
                cfg = cfg.model_dump()
            elif not isinstance(cfg, dict):
                cfg = {}
        if not cfg:
            from src.api.dependencies import get_settings
            dumped = get_settings().model_dump()
            cfg = dumped.get("grounding", {}) or {}
        if not cfg.get("enabled", True):
            return None
        return RetrievalGateConfig(
            enabled=True,
            min_citations=int(cfg.get("min_citations", 2)),
            min_top_score=float(cfg.get("min_top_score", 0.35)),
            min_mean_score=float(cfg.get("min_mean_score", 0.25)),
            max_unsupported_ratio=float(cfg.get("max_unsupported_ratio", 0.40)),
        )
    except Exception:  # noqa: BLE001
        logger.debug("grounding config load failed", exc_info=True)
        return None


def _apply_grounding(
    answer: str,
    citations: list[dict[str, Any]],
    trace: Any,
    request: Request,
    stopped_reason: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run grounding check; return (possibly annotated) answer + report meta.

    Never raises — grounding failures fall back to the original answer. The
    returned meta dict is persisted in the trace and the eval record for
    later analysis.
    """
    meta: dict[str, Any] = {"enabled": False}
    try:
        from src.evaluation.grounding import annotate_answer, check_grounding

        cfg = _build_grounding_config(request)
        if cfg is None:
            return answer, meta
        report = check_grounding(
            answer, citations, config=cfg, stopped_reason=stopped_reason,
        )
        new_answer = annotate_answer(answer, report)
        meta = {
            "enabled": True,
            "abstained": report.abstain,
            "reason": report.reason,
            "coverage": round(report.coverage, 3),
            "total": report.total,
            "unsupported": [f.raw for f in report.unsupported[:10]],
            "retrieval_score": round(report.retrieval_score, 3),
            "retrieval_mean": round(report.retrieval_mean, 3),
            "stopped_reason": stopped_reason,
        }
        if trace is not None:
            trace.record_stage("grounding", meta)
        return new_answer, meta
    except Exception:  # noqa: BLE001
        logger.warning("grounding check failed", exc_info=True)
        return answer, meta


def _extract_citations(tool_calls_log: list[Any]) -> list[dict[str, Any]]:
    """Pull citation dicts out of tool observation payloads.

    Handles both shapes:
    - RAG search: ``{"results": [{chunk_id, content, score, ...}, ...]}``
    - Pre-built: ``{"citations": [...]}``
    """
    citations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for step in tool_calls_log:
        for obs in step.observations:
            if not isinstance(obs, dict):
                continue
            for c in obs.get("citations", []):
                cid = str(c.get("chunk_id", ""))
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    citations.append(c)
            for r in obs.get("results", []):
                if not isinstance(r, dict):
                    continue
                cid = str(r.get("chunk_id", ""))
                if not cid or cid in seen_ids:
                    continue
                seen_ids.add(cid)
                meta = r.get("metadata") or {}
                citations.append({
                    "chunk_id": cid,
                    "doc_id": str(r.get("doc_id", "")),
                    "content": r.get("content", ""),
                    "score": float(r.get("score", 0.0) or 0.0),
                    "source": meta.get("part_number") or r.get("source", ""),
                    "page_number": r.get("page_number"),
                    "metadata": meta,
                })
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
    trace.record_stage("request", {"query": req.query, "user": current_user.username})

    try:
        result = await orchestrator.run(query=req.query, trace=trace)
    except Exception as exc:
        logger.error("Agent run failed (trace=%s): %s", trace_id, exc)
        trace.record_stage("error", {"detail": str(exc)[:500]})
        trace.flush()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent error: {exc}",
        ) from exc

    citations = _extract_citations(result.tool_calls_log)
    grounded_answer, _grounding_meta = _apply_grounding(
        result.answer, citations, trace, request,
        stopped_reason=result.stopped_reason,
    )
    trace.record_stage("response", {
        "answer": grounded_answer[:800],
        "citation_count": len(citations),
        "iterations": result.iterations,
        "total_tokens": result.total_tokens,
        "stopped_reason": result.stopped_reason,
        "citations_preview": [
            {"chunk_id": c.get("chunk_id"), "source": c.get("source"),
             "page": c.get("page_number"), "score": c.get("score"),
             "content": (c.get("content") or "")[:800]}
            for c in citations[:10]
        ],
    })
    trace.flush()

    _schedule_online_eval(
        request=request,
        trace_id=trace_id,
        query=req.query,
        answer=grounded_answer,
        citations=citations,
        iterations=result.iterations,
        duration_ms=(trace._stages[-1].timestamp - trace._start) * 1000 if trace._stages else 0,  # noqa: SLF001
    )

    return QueryResponse(
        answer=grounded_answer,
        citations=citations,
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

        from src.observability.trace_context import TraceContext

        trace = TraceContext(trace_id=trace_id)
        trace.record_stage("request", {"query": req.query, "user": current_user.username})
        try:
            result = await orchestrator.run(query=req.query, trace=trace)
            citations = _extract_citations(result.tool_calls_log)
            grounded_answer, grounding_meta = _apply_grounding(
                result.answer, citations, trace, request,
                stopped_reason=result.stopped_reason,
            )

            # Emit answer in small chunks while preserving all whitespace
            # (newlines, blank lines) so the frontend markdown renderer can
            # recognize headings, lists, tables, etc.
            chunk_size = 24
            for i in range(0, len(grounded_answer), chunk_size):
                chunk = grounded_answer[i : i + chunk_size]
                payload = json.dumps({"type": "token", "content": chunk})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)

            trace.record_stage("response", {
                "answer": grounded_answer[:800],
                "citation_count": len(citations),
                "iterations": result.iterations,
                "total_tokens": result.total_tokens,
                "stopped_reason": result.stopped_reason,
                "citations_preview": [
                    {"chunk_id": c.get("chunk_id"), "source": c.get("source"),
                     "page": c.get("page_number"), "score": c.get("score"),
                     "content": (c.get("content") or "")[:800]}
                    for c in citations[:10]
                ],
            })
            trace.flush()
            _schedule_online_eval(
                request=request,
                trace_id=trace_id,
                query=req.query,
                answer=grounded_answer,
                citations=citations,
                iterations=result.iterations,
                duration_ms=(trace._stages[-1].timestamp - trace._start) * 1000 if trace._stages else 0,  # noqa: SLF001
            )
            done = json.dumps({
                "type": "done",
                "citations": citations,
                "trace_id": trace_id,
                "grounding": grounding_meta,
            })
            yield f"data: {done}\n\n"

        except asyncio.CancelledError:
            logger.debug("SSE client disconnected (trace=%s)", trace_id)
            trace.flush()
        except Exception as exc:
            logger.exception("SSE stream error (trace=%s)", trace_id)
            trace.record_stage("error", {"detail": str(exc)[:500]})
            trace.flush()
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
