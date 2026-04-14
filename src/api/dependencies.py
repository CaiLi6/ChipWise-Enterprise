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
        import asyncpg  # type: ignore[import-not-found]

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
