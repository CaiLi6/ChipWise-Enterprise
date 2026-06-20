"""Dependency injection container for the ChipWise FastAPI gateway.

Provides singleton ``Settings``, lazy connection pools (PostgreSQL, Redis),
and HTTP clients for model microservices. All resources are created lazily
and released during application shutdown via the ``lifespan`` context manager.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI

from src.core.settings import Settings, load_settings

logger = logging.getLogger("chipwise.dependencies")

# ── Singleton settings ──────────────────────────────────────────────

_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance (loaded once from YAML)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = load_settings()
    return _settings_instance


def override_settings(settings: Settings) -> None:
    """Override the singleton settings (for testing)."""
    global _settings_instance
    _settings_instance = settings


# ── Database pool (asyncpg) ─────────────────────────────────────────

_db_pool: Any = None


async def _create_db_pool(settings: Settings) -> Any:
    """Create an asyncpg connection pool. Returns None on failure."""
    global _db_pool
    try:
        import asyncpg  # type: ignore[import-untyped,import-not-found]

        db = settings.database
        _db_pool = await asyncpg.create_pool(
            host=db.host,
            port=db.port,
            database=db.database,
            user=db.user,
            password=db.password,
            min_size=2,
            max_size=db.pool_size,
            command_timeout=10,
        )
        logger.info("PostgreSQL connection pool created.")
        return _db_pool
    except Exception as exc:
        logger.warning("Failed to create DB pool (will retry on demand): %s", exc)
        _db_pool = None
        return None


async def get_db_pool(settings: Settings = Depends(get_settings)) -> Any:  # noqa: B008
    """FastAPI Depends: return the asyncpg pool (may be None if unavailable)."""
    global _db_pool
    if _db_pool is None:
        await _create_db_pool(settings)
    return _db_pool


# ── Redis client (async) ───────────────────────────────────────────

_redis_client: Any = None


async def _create_redis(settings: Settings) -> Any:
    """Create an async Redis client. Returns None on failure."""
    global _redis_client
    try:
        import redis.asyncio as aioredis

        rs = settings.redis
        url = f"redis://{rs.host}:{rs.port}/{rs.db}"
        if rs.password:
            url = f"redis://:{rs.password}@{rs.host}:{rs.port}/{rs.db}"
        _redis_client = aioredis.from_url(
            url,
            socket_connect_timeout=3,
            socket_timeout=3,
            decode_responses=True,
        )
        await _redis_client.ping()
        logger.info("Redis client connected.")
        return _redis_client
    except Exception as exc:
        logger.warning("Failed to connect Redis (will retry on demand): %s", exc)
        _redis_client = None
        return None


async def get_redis(settings: Settings = Depends(get_settings)) -> Any:  # noqa: B008
    """FastAPI Depends: return the async Redis client (may be None)."""
    global _redis_client
    if _redis_client is None:
        await _create_redis(settings)
    return _redis_client


# ── Memory helpers (Redis short-term memory + semantic cache) ─────────

_conversation_manager: Any = None
_conversation_manager_redis_id: int | None = None
_semantic_cache: Any = None
_semantic_cache_redis_id: int | None = None
_query_rewriter: Any = None
_memory_retriever: Any = None


def get_conversation_manager_for_redis(
    redis: Any,
    settings: Settings | None = None,
) -> Any:
    """Return a Redis-backed ConversationManager for the given Redis client.

    This is intentionally not a FastAPI dependency: query endpoints already
    receive the Redis client and can skip memory when Redis is unavailable.
    """
    if redis is None:
        return None
    settings = settings or get_settings()
    memory_cfg = getattr(settings, "memory", None)
    if memory_cfg is not None and not getattr(memory_cfg, "enabled", True):
        return None

    global _conversation_manager, _conversation_manager_redis_id
    redis_id = id(redis)
    if _conversation_manager is not None and _conversation_manager_redis_id == redis_id:
        return _conversation_manager

    from src.core.conversation_manager import ConversationManager
    from src.core.memory_summarizer import MemorySummarizer

    summarizer = MemorySummarizer()
    if getattr(memory_cfg, "llm_summarization_enabled", False):
        try:
            from src.libs.llm.factory import LLMFactory

            cfg = settings.model_dump()
            llm = LLMFactory.create(cfg, role=getattr(memory_cfg, "summarizer_role", "router"))
            summarizer = MemorySummarizer(llm=llm)
        except Exception as exc:
            logger.warning("Memory summarizer LLM unavailable; using fallback: %s", exc)

    _conversation_manager = ConversationManager(
        redis,
        session_ttl=getattr(memory_cfg, "session_ttl", 1800),
        max_turns=getattr(memory_cfg, "max_turns", 10),
        compression_threshold=getattr(memory_cfg, "compression_threshold", 10),
        summary_max_chars=getattr(memory_cfg, "summary_max_chars", 2000),
        compaction_budget_chars=getattr(memory_cfg, "compaction_budget_chars", 8000),
        checkpoint_limit=getattr(memory_cfg, "checkpoint_limit", 5),
        pinned_limit=getattr(memory_cfg, "pinned_limit", 20),
        summarizer=summarizer,
    )
    _conversation_manager_redis_id = redis_id
    return _conversation_manager


def get_query_rewriter_for_settings(settings: Settings | None = None) -> Any:
    """Return a lazy QueryRewriter backed by the router LLM."""
    global _query_rewriter
    if _query_rewriter is not None:
        return _query_rewriter
    try:
        from src.core.query_rewriter import QueryRewriter
        from src.libs.llm.factory import LLMFactory

        cfg = (settings or get_settings()).model_dump()
        try:
            llm = LLMFactory.create(cfg, role="router")
        except Exception:
            llm = LLMFactory.create(cfg, role="primary")
        _query_rewriter = QueryRewriter(llm)
    except Exception as exc:
        logger.warning("QueryRewriter unavailable: %s", exc)
        _query_rewriter = None
    return _query_rewriter


def get_memory_retriever_for_settings(settings: Settings | None = None) -> Any:
    """Return a prompt-budgeted short-term memory retriever."""
    global _memory_retriever
    if _memory_retriever is not None:
        return _memory_retriever
    from src.core.memory_retriever import MemoryRetrievalConfig, MemoryRetriever

    memory_cfg = getattr(settings or get_settings(), "memory", None)
    _memory_retriever = MemoryRetriever(
        MemoryRetrievalConfig(
            prompt_budget_chars=getattr(memory_cfg, "prompt_budget_chars", 6000),
            recent_turns_always=getattr(memory_cfg, "recent_turns_always", 4),
            min_relevance_score=getattr(memory_cfg, "min_relevance_score", 0.12),
        )
    )
    return _memory_retriever


def get_semantic_cache_for_redis(redis: Any, settings: Settings | None = None) -> Any:
    """Return a settings-driven SemanticCache for the given Redis client."""
    if redis is None:
        return None
    settings = settings or get_settings()
    cache_cfg = getattr(settings, "cache", None)
    if cache_cfg is not None and not getattr(cache_cfg, "enabled", True):
        return None

    global _semantic_cache, _semantic_cache_redis_id
    redis_id = id(redis)
    if _semantic_cache is not None and _semantic_cache_redis_id == redis_id:
        return _semantic_cache

    try:
        from src.cache.semantic_cache import SemanticCache
        from src.libs.embedding.factory import EmbeddingFactory

        embedding = EmbeddingFactory.create(settings.model_dump())
        _semantic_cache = SemanticCache(
            embedding,
            redis,
            similarity_threshold=getattr(cache_cfg, "similarity_threshold", 0.95),
            ttl_conversational=getattr(cache_cfg, "ttl_conversational", 3600),
            ttl_comparison=getattr(cache_cfg, "ttl_comparison", 14400),
            bucket_size=getattr(cache_cfg, "bucket_size", 8),
        )
        _semantic_cache_redis_id = redis_id
    except Exception as exc:
        logger.warning("SemanticCache unavailable: %s", exc)
        _semantic_cache = None
    return _semantic_cache


# ── HTTP clients for model services ─────────────────────────────────


class EmbeddingClient:
    """Thin HTTP wrapper around the BGE-M3 embedding microservice."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def encode(
        self, texts: list[str], return_sparse: bool = True
    ) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/encode",
                json={"texts": texts, "return_sparse": return_sparse},
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def health(self) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200 and resp.json().get("ready", False)  # type: ignore[no-any-return]
        except Exception:
            return False


class RerankerClient:
    """Thin HTTP wrapper around the bce-reranker microservice."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def rerank(
        self, query: str, documents: list[str], top_k: int = 10
    ) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/rerank",
                json={"query": query, "documents": documents, "top_k": top_k},
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

    async def health(self) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200 and resp.json().get("ready", False)  # type: ignore[no-any-return]
        except Exception:
            return False


def get_embedding_client(settings: Settings = Depends(get_settings)) -> EmbeddingClient:  # noqa: B008
    """FastAPI Depends: return an EmbeddingClient."""
    return EmbeddingClient(
        base_url=settings.embedding.base_url,
        timeout=settings.embedding.timeout,
    )


def get_reranker_client(settings: Settings = Depends(get_settings)) -> RerankerClient:  # noqa: B008
    """FastAPI Depends: return a RerankerClient (or None if disabled)."""
    return RerankerClient(
        base_url=settings.rerank.base_url,
        timeout=settings.rerank.timeout,
    )


# ── Kùzu graph store (process-wide singleton) ───────────────────────
#
# Kùzu is embedded; a single process must hold exactly one writable
# Database instance to avoid IO lock contention. Both the Agent (read
# via GraphQueryTool) and the ingestion path (write via
# GraphSynchronizer) must share this instance.

_graph_store: Any = None


def get_graph_store(settings: Settings | None = None) -> Any:
    """Return the singleton ``BaseGraphStore`` (lazy, may return None on failure).

    Not a FastAPI Depends — call it directly from any code path that
    needs the shared graph instance.
    """
    global _graph_store
    if _graph_store is not None:
        return _graph_store
    try:
        from src.libs.graph_store.factory import GraphStoreFactory
        cfg = (settings or get_settings()).model_dump()
        _graph_store = GraphStoreFactory.create(cfg)
        logger.info("KuzuGraphStore singleton created.")
    except Exception as exc:
        logger.warning("Failed to create graph store singleton: %s", exc)
        _graph_store = None
    return _graph_store


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan: create pools on startup, close on shutdown."""
    settings = get_settings()
    app.state.settings = settings

    # Startup: create pools (best-effort, don't crash if service is down)
    await _create_db_pool(settings)
    await _create_redis(settings)

    yield

    # Shutdown: release resources
    global _db_pool, _redis_client
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("PostgreSQL pool closed.")

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed.")
