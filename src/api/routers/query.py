"""Query router: standard + SSE streaming endpoints (§6A2)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.dependencies import get_db_pool, get_redis
from src.api.middleware.auth import get_current_user
from src.api.schemas.auth import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

# ---------------------------------------------------------------------------
# Singleton orchestrator — created lazily on the first request.
# None when LLM / dependencies are unavailable (graceful degradation).
# ---------------------------------------------------------------------------
_orchestrator: Any = None
_orchestrator_initialized = False


def _get_or_create_orchestrator(db_pool: Any = None) -> Any:
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
        from src.agent.tools.knowledge_search import KnowledgeSearchTool
        from src.agent.tools.rag_search import RAGSearchTool
        from src.agent.tools.sql_query import SQLQueryTool
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

        if db_pool is not None:
            try:
                registry.register(SQLQueryTool(db_pool=db_pool))
            except Exception:
                logger.warning("SQLQueryTool register failed", exc_info=True)

        if hybrid is not None:
            try:
                registry.register(KnowledgeSearchTool(hybrid_search=hybrid))
            except Exception:
                logger.warning("KnowledgeSearchTool register failed", exc_info=True)

        # Discover remaining zero-arg (or optional-arg) tools
        registry.discover(skip_names={"sql_query", "knowledge_search"})

        config = AgentConfig(
            max_iterations=settings.agent.max_iterations,
            max_total_tokens=settings.agent.max_total_tokens,
            parallel_tool_calls=settings.agent.parallel_tool_calls,
            temperature=settings.agent.temperature,
            tool_timeout=settings.agent.tool_timeout,
            max_observation_chars=settings.agent.max_observation_chars,
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


def get_orchestrator(db_pool: Any = Depends(get_db_pool)) -> Any:  # noqa: B008
    """FastAPI-compatible dependency for the AgentOrchestrator singleton."""
    return _get_or_create_orchestrator(db_pool=db_pool)


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
            numeric_abstain_mode=str(cfg.get("numeric_abstain_mode", "warn")),
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


def _memory_user_key(current_user: UserInfo) -> str:
    """Stable per-user namespace for backend memory."""
    return (current_user.sub or current_user.username or "anonymous").strip() or "anonymous"


def _normalize_session_id(raw_session_id: str | None, request: Request) -> str:
    """Validate frontend-provided session id before using it in Redis keys."""
    session_id = (raw_session_id or "default").strip()
    try:
        settings = request.app.state.settings if hasattr(request.app.state, "settings") else None
        max_len = int(getattr(getattr(settings, "memory", None), "session_id_max_length", 128))
    except Exception:
        max_len = 128
    if not session_id or len(session_id) > max_len or not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return session_id


def _extract_tools_used(tool_calls_log: list[Any]) -> list[str]:
    tools: list[str] = []
    for step in tool_calls_log:
        for tool_call in getattr(step, "tool_calls", []):
            name = getattr(tool_call, "tool_name", "")
            if name and name not in tools:
                tools.append(name)
    return tools


def _should_cache_answer(
    answer: str,
    result: Any,
    grounding_meta: dict[str, Any],
) -> bool:
    if not answer.strip():
        return False
    if getattr(result, "stopped_reason", "complete") != "complete":
        return False
    return not grounding_meta.get("abstained")


async def _load_memory_context(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo,
    redis: Any,
    trace: Any,
) -> tuple[str, str, list[dict[str, str]], Any]:
    """Load Redis short-term memory and return session/user/history/manager."""
    from src.api.dependencies import (
        get_conversation_manager_for_redis,
        get_memory_retriever_for_settings,
        get_settings,
    )

    settings = request.app.state.settings if hasattr(request.app.state, "settings") else get_settings()
    session_id = _normalize_session_id(req.session_id, request)
    user_key = _memory_user_key(current_user)
    manager = get_conversation_manager_for_redis(redis, settings)
    if manager is None:
        trace.record_stage("memory_degraded", {"reason": "redis_unavailable_or_disabled"})
        return session_id, user_key, [], None

    try:
        context = await manager.load_context(user_key, session_id)
        retriever = get_memory_retriever_for_settings(settings)
        messages = retriever.select_messages(context, req.query)
        trace.record_stage("memory_load", {
            "session_id": session_id,
            "turns": len(context.turns),
            "selected_messages": len(messages),
            "has_summary": bool(context.summary),
            "entities": context.entities,
        })
        return session_id, user_key, messages, manager
    except Exception:
        logger.warning("Conversation memory load failed", exc_info=True)
        trace.record_stage("memory_degraded", {"reason": "load_failed"})
        return session_id, user_key, [], None


async def _rewrite_query_if_needed(
    raw_query: str,
    history: list[dict[str, str]],
    request: Request,
    trace: Any,
) -> str:
    if not history:
        return raw_query
    try:
        from src.api.dependencies import get_query_rewriter_for_settings, get_settings

        settings = request.app.state.settings if hasattr(request.app.state, "settings") else get_settings()
        rewriter = get_query_rewriter_for_settings(settings)
        if rewriter is None:
            trace.record_stage("query_rewrite", {"enabled": False, "reason": "unavailable"})
            return raw_query
        rewritten = await rewriter.rewrite(raw_query, history)
        trace.record_stage("query_rewrite", {
            "enabled": True,
            "changed": rewritten != raw_query,
            "rewritten_query": rewritten if rewritten != raw_query else "",
        })
        return rewritten
    except Exception:
        logger.warning("Query rewrite failed", exc_info=True)
        trace.record_stage("query_rewrite", {"enabled": False, "reason": "failed"})
        return raw_query


async def _get_cached_response(
    rewritten_query: str,
    request: Request,
    redis: Any,
    trace: Any,
) -> Any:
    try:
        from src.api.dependencies import get_semantic_cache_for_redis, get_settings

        settings = request.app.state.settings if hasattr(request.app.state, "settings") else get_settings()
        cache = get_semantic_cache_for_redis(redis, settings)
        if cache is None:
            trace.record_stage("cache_lookup", {"enabled": False})
            return None
        cached = await cache.get(rewritten_query, trace=trace)
        trace.record_stage("cache_lookup", {
            "enabled": True,
            "hit": cached is not None,
            "similarity": round(cached.similarity, 4) if cached else 0.0,
        })
        return cached
    except Exception:
        logger.warning("Semantic cache lookup failed", exc_info=True)
        trace.record_stage("cache_lookup", {"enabled": False, "reason": "failed"})
        return None


async def _put_cached_response(
    rewritten_query: str,
    answer: str,
    citations: list[dict[str, Any]],
    tools_used: list[str],
    request: Request,
    redis: Any,
    session_id: str,
    user_key: str,
    trace: Any,
) -> None:
    try:
        from src.api.dependencies import get_semantic_cache_for_redis, get_settings

        settings = request.app.state.settings if hasattr(request.app.state, "settings") else get_settings()
        cache = get_semantic_cache_for_redis(redis, settings)
        if cache is None:
            return
        await cache.put(
            rewritten_query,
            {"answer": answer, "citations": citations, "trace_id": trace.trace_id},
            tools_used=tools_used,
            metadata={
                "session_id": session_id,
                "user_key": user_key,
                "citation_count": len(citations),
            },
        )
        trace.record_stage("cache_store", {"stored": True, "tools_used": tools_used})
    except Exception:
        logger.warning("Semantic cache store failed", exc_info=True)
        trace.record_stage("cache_store", {"stored": False, "reason": "failed"})


async def _append_memory_exchange(
    manager: Any,
    user_key: str,
    session_id: str,
    user_query: str,
    assistant_answer: str,
    trace: Any,
) -> None:
    if manager is None:
        return
    try:
        await manager.append_exchange(user_key, session_id, user_query, assistant_answer)
        trace.record_stage("memory_store", {"session_id": session_id, "stored": True})
    except Exception:
        logger.warning("Conversation memory store failed", exc_info=True)
        trace.record_stage("memory_store", {"session_id": session_id, "stored": False})


async def _load_governed_memory_messages(
    db_pool: Any,
    user_key: str,
    trace: Any,
) -> list[dict[str, str]]:
    """Load confirmed user/project memories as advisory prompt context."""
    try:
        from src.core.memory_governance import MemoryGovernanceStore

        records = await MemoryGovernanceStore(db_pool).list_memories(
            owner_key=user_key,
            status="confirmed",
            limit=8,
        )
        if not records:
            return []
        lines = ["Confirmed user/project memories (advisory; do not override citations):"]
        for rec in records[:8]:
            kind = rec.get("kind", "memory")
            content = str(rec.get("content", "")).strip()
            if content:
                lines.append(f"- [{kind}] {content[:300]}")
        trace.record_stage("governed_memory", {"loaded": len(lines) - 1})
        return [{"role": "system", "content": "\n".join(lines)}] if len(lines) > 1 else []
    except Exception:
        logger.warning("Governed memory load failed", exc_info=True)
        trace.record_stage("governed_memory", {"loaded": 0, "reason": "failed"})
        return []


async def _load_procedure_messages(
    db_pool: Any,
    query: str,
    trace: Any,
) -> list[dict[str, str]]:
    """Load procedural memory hints for tool selection."""
    try:
        from src.core.procedural_memory import ProceduralMemoryStore

        store = ProceduralMemoryStore(db_pool)
        hints = await store.get_hints(query)
        content = store.format_hints(hints)
        trace.record_stage("procedural_memory", {
            "hints": [h.intent for h in hints],
        })
        return [{"role": "system", "content": content}] if content else []
    except Exception:
        logger.warning("Procedural memory load failed", exc_info=True)
        trace.record_stage("procedural_memory", {"hints": [], "reason": "failed"})
        return []


async def _record_episode_and_learn(
    *,
    db_pool: Any,
    user_key: str,
    session_id: str,
    trace_id: str,
    raw_query: str,
    rewritten_query: str,
    answer: str,
    tools_used: list[str],
    citations: list[dict[str, Any]],
    grounding_meta: dict[str, Any],
    outcome: str,
    trace: Any,
) -> None:
    """Persist episodic/procedural/governed memory. Never blocks responses."""
    try:
        from src.core.episodic_memory import EpisodicMemoryStore, MemoryEpisode
        from src.core.memory_consolidator import MemoryConsolidator
        from src.core.memory_governance import MemoryGovernanceStore, explicit_memory_from_query
        from src.core.procedural_memory import ProceduralMemoryStore

        episode = MemoryEpisode(
            user_key=user_key,
            session_id=session_id,
            trace_id=trace_id,
            query_text=raw_query,
            rewritten_query=rewritten_query,
            tools_used=tools_used,
            citations=citations[:20],
            grounding=grounding_meta,
            answer_preview=answer[:1000],
            outcome=outcome,
        )
        episode_id = await EpisodicMemoryStore(db_pool).record_episode(episode)
        success = outcome in {"success", "cache_hit"}
        await ProceduralMemoryStore(db_pool).record_outcome(rewritten_query or raw_query, tools_used, success)

        governance = MemoryGovernanceStore(db_pool)
        explicit = explicit_memory_from_query(raw_query, owner_key=user_key, trace_id=trace_id)
        explicit_id = await governance.create_memory(explicit) if explicit else None

        candidate = MemoryConsolidator().propose_from_episode(episode)
        candidate_id = await governance.create_memory(candidate) if candidate else None
        trace.record_stage("episodic_memory", {
            "episode_id": episode_id,
            "outcome": outcome,
            "explicit_memory_id": explicit_id,
            "candidate_memory_id": candidate_id,
        })
    except Exception:
        logger.warning("Episode/procedure memory recording failed", exc_info=True)
        trace.record_stage("episodic_memory", {"stored": False, "reason": "failed"})


async def _execute_query_with_memory(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo,
    orchestrator: Any,
    redis: Any,
    db_pool: Any = None,
) -> dict[str, Any]:
    """Shared query execution for standard and SSE endpoints."""
    from src.observability.trace_context import TraceContext

    raw_query = req.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    trace_id = getattr(request.state, "trace_id", "")
    trace = TraceContext(trace_id=trace_id)
    trace.record_stage("request", {"query": raw_query, "user": current_user.username, "session_id": req.session_id})

    session_id, user_key, history, manager = await _load_memory_context(
        req, request, current_user, redis, trace,
    )
    rewritten_query = await _rewrite_query_if_needed(raw_query, history, request, trace)
    governed_messages = await _load_governed_memory_messages(db_pool, user_key, trace)
    procedure_messages = await _load_procedure_messages(db_pool, rewritten_query, trace)

    cached = await _get_cached_response(rewritten_query, request, redis, trace)
    if cached is not None:
        cached_response = cached.response if isinstance(cached.response, dict) else {}
        answer = str(cached_response.get("answer") or "")
        citations = cached_response.get("citations") if isinstance(cached_response.get("citations"), list) else []
        if answer:
            await _append_memory_exchange(manager, user_key, session_id, raw_query, answer, trace)
            await _record_episode_and_learn(
                db_pool=db_pool,
                user_key=user_key,
                session_id=session_id,
                trace_id=trace_id,
                raw_query=raw_query,
                rewritten_query=rewritten_query,
                answer=answer,
                tools_used=list(getattr(cached, "tools_used", []) or []),
                citations=citations,
                grounding_meta={"enabled": False, "cache_hit": True},
                outcome="cache_hit",
                trace=trace,
            )
            trace.record_stage("response", {
                "answer": answer[:800],
                "citation_count": len(citations),
                "iterations": 0,
                "total_tokens": 0,
                "stopped_reason": "cache_hit",
                "cache_hit": True,
            })
            trace.flush()
            _schedule_online_eval(
                request=request,
                trace_id=trace_id,
                query=raw_query,
                answer=answer,
                citations=citations,
                iterations=0,
                duration_ms=(trace._stages[-1].timestamp - trace._start) * 1000 if trace._stages else 0,  # noqa: SLF001
            )
            return {
                "answer": answer,
                "citations": citations,
                "trace_id": trace_id,
                "grounding": {"enabled": False, "cache_hit": True},
                "cache_hit": True,
            }

    try:
        result = await orchestrator.run(
            query=rewritten_query,
            conversation_history=[*governed_messages, *procedure_messages, *history],
            trace=trace,
        )
    except Exception as exc:
        logger.error("Agent run failed (trace=%s): %s", trace_id, exc)
        trace.record_stage("error", {"detail": str(exc)[:500]})
        trace.flush()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent error: {exc}",
        ) from exc

    citations = _extract_citations(result.tool_calls_log)
    grounded_answer, grounding_meta = _apply_grounding(
        result.answer, citations, trace, request,
        stopped_reason=result.stopped_reason,
    )
    tools_used = _extract_tools_used(result.tool_calls_log)
    outcome = "success"
    if grounding_meta.get("abstained"):
        outcome = "abstained"
    elif result.stopped_reason != "complete":
        outcome = result.stopped_reason

    await _append_memory_exchange(manager, user_key, session_id, raw_query, grounded_answer, trace)
    await _record_episode_and_learn(
        db_pool=db_pool,
        user_key=user_key,
        session_id=session_id,
        trace_id=trace_id,
        raw_query=raw_query,
        rewritten_query=rewritten_query,
        answer=grounded_answer,
        tools_used=tools_used,
        citations=citations,
        grounding_meta=grounding_meta,
        outcome=outcome,
        trace=trace,
    )
    if _should_cache_answer(grounded_answer, result, grounding_meta):
        await _put_cached_response(
            rewritten_query,
            grounded_answer,
            citations,
            tools_used,
            request,
            redis,
            session_id,
            user_key,
            trace,
        )

    trace.record_stage("response", {
        "answer": grounded_answer[:800],
        "citation_count": len(citations),
        "iterations": result.iterations,
        "total_tokens": result.total_tokens,
        "stopped_reason": result.stopped_reason,
        "cache_hit": False,
        "tools_used": tools_used,
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
        query=raw_query,
        answer=grounded_answer,
        citations=citations,
        iterations=result.iterations,
        duration_ms=(trace._stages[-1].timestamp - trace._start) * 1000 if trace._stages else 0,  # noqa: SLF001
    )

    return {
        "answer": grounded_answer,
        "citations": citations,
        "trace_id": trace_id,
        "grounding": grounding_meta,
        "cache_hit": False,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    orchestrator: Any = Depends(get_orchestrator),  # noqa: B008
    redis: Any = Depends(get_redis),  # noqa: B008
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> QueryResponse:
    """Standard (non-streaming) query endpoint — delegates to AgentOrchestrator.

    Returns 503 with a descriptive message when the LLM service is unavailable.
    """
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
            orchestrator = _get_or_create_orchestrator(db_pool=db_pool)

    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Agent Orchestrator unavailable — "
                "check that LM Studio is running and tools are configured"
            ),
        )

    execution = await _execute_query_with_memory(req, request, current_user, orchestrator, redis, db_pool)
    return QueryResponse(
        answer=execution["answer"],
        citations=execution["citations"],
        trace_id=execution["trace_id"],
    )


@router.post("/query/stream")
async def stream_query(
    req: QueryRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),  # noqa: B008
    orchestrator: Any = Depends(get_orchestrator),  # noqa: B008
    redis: Any = Depends(get_redis),  # noqa: B008
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> StreamingResponse:
    """SSE streaming query endpoint.

    Streams progress + answer chunks as Server-Sent Events::

        data: {"type": "status", "content": "正在检索..."}\n\n
        data: {"type": "token", "content": "..."}\n\n
        data: {"type": "done", "citations": [...], "trace_id": "..."}\n\n

    Returns a single ``error`` event when the Agent is unavailable.
    """
    trace_id = getattr(request.state, "trace_id", "")

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def _generate() -> AsyncGenerator[str, None]:
        # Fast-fail: check LM Studio health
        lm_status = getattr(request.app.state, "lmstudio_status", None)
        if lm_status:
            primary = lm_status.get("lmstudio_primary", {})
            if not primary.get("healthy", True):
                yield _sse({
                    "type": "error",
                    "content": "LLM service temporarily unavailable",
                })
                return

        if orchestrator is None:
            yield _sse({
                "type": "error",
                "content": "Agent Orchestrator unavailable — check LM Studio",
            })
            return

        task: asyncio.Task[dict[str, Any]] | None = None
        try:
            task = asyncio.create_task(_execute_query_with_memory(
                req, request, current_user, orchestrator, redis, db_pool,
            ))
            status_messages = [
                "正在加载会话记忆与语义缓存…",
                "正在选择工具并检索芯片资料…",
                "正在进行 Agent 推理与工具调用…",
                "正在校验引用、数字一致性并写入记忆…",
            ]
            status_idx = 0
            while not task.done():
                yield _sse({
                    "type": "status",
                    "content": status_messages[min(status_idx, len(status_messages) - 1)],
                    "trace_id": trace_id,
                })
                status_idx += 1
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                except TimeoutError:
                    continue

            execution = await task
            grounded_answer = execution["answer"]
            citations = execution["citations"]
            grounding_meta = execution["grounding"]

            yield _sse({
                "type": "status",
                "content": "正在流式输出答案…",
                "trace_id": execution["trace_id"],
            })

            # Emit answer in small chunks while preserving all whitespace
            # (newlines, blank lines) so the frontend markdown renderer can
            # recognize headings, lists, tables, etc.
            chunk_size = 24
            for i in range(0, len(grounded_answer), chunk_size):
                chunk = grounded_answer[i : i + chunk_size]
                yield _sse({"type": "token", "content": chunk})
                await asyncio.sleep(0)

            yield _sse({
                "type": "done",
                "citations": citations,
                "trace_id": execution["trace_id"],
                "grounding": grounding_meta,
            })

        except asyncio.CancelledError:
            logger.debug("SSE client disconnected (trace=%s)", trace_id)
            if task is not None:
                task.cancel()
            raise
        except HTTPException as exc:
            content = exc.detail if isinstance(exc.detail, str) else "Stream failed"
            yield _sse({"type": "error", "content": content})
        except Exception:
            logger.exception("SSE stream error (trace=%s)", trace_id)
            yield _sse({"type": "error", "content": "Stream failed"})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
