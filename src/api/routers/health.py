"""Health and readiness endpoints for the ChipWise API gateway."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


# ── Schemas ─────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: float


class ServiceStatusDetail(BaseModel):
    healthy: bool
    message: str


class ReadinessResponse(BaseModel):
    status: str  # "ready" | "degraded"
    services: dict[str, ServiceStatusDetail]


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe — only checks that the app itself is alive."""
    from src.api.main import APP_VERSION, _start_time

    uptime = time.time() - _start_time if _start_time > 0 else 0.0
    return HealthResponse(status="ok", version=APP_VERSION, uptime=round(uptime, 2))


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness_check(request: Request) -> ReadinessResponse:
    """Readiness probe — checks downstream service connectivity.

    Returns ``degraded`` instead of 500 when services are unavailable.
    """
    settings = request.app.state.settings
    services: dict[str, ServiceStatusDetail] = {}

    # PostgreSQL
    services["postgres"] = _check_postgres(settings)

    # Redis
    services["redis"] = _check_redis(settings)

    # Milvus
    services["milvus"] = _check_milvus(settings)

    # Embedding service
    services["embedding"] = _check_http_service(
        settings.embedding.base_url, "/health", "Embedding"
    )

    # Reranker service
    if settings.rerank.enabled:
        services["reranker"] = _check_http_service(
            settings.rerank.base_url, "/health", "Reranker"
        )

    all_healthy = all(s.healthy for s in services.values())
    return ReadinessResponse(
        status="ready" if all_healthy else "degraded",
        services=services,
    )


# ── Internal health checks (best-effort, non-blocking) ─────────────


def _check_postgres(settings: Any) -> ServiceStatusDetail:
    try:
        from sqlalchemy import create_engine, text

        db = settings.database
        dsn = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"
        engine = create_engine(dsn, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return ServiceStatusDetail(healthy=True, message="OK")
    except Exception as exc:
        return ServiceStatusDetail(healthy=False, message=str(exc))


def _check_redis(settings: Any) -> ServiceStatusDetail:
    try:
        import redis as redis_lib

        rs = settings.redis
        url = f"redis://{rs.host}:{rs.port}/{rs.db}"
        if rs.password:
            url = f"redis://:{rs.password}@{rs.host}:{rs.port}/{rs.db}"
        client = redis_lib.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        client.ping()
        client.close()
        return ServiceStatusDetail(healthy=True, message="OK")
    except Exception as exc:
        return ServiceStatusDetail(healthy=False, message=str(exc))


def _check_milvus(settings: Any) -> ServiceStatusDetail:
    try:
        from pymilvus import connections, utility

        ms = settings.vector_store.milvus
        connections.connect(alias="readiness", host=ms.host, port=ms.port, timeout=3)
        has = utility.has_collection(ms.collection_name, using="readiness")
        connections.disconnect("readiness")
        if has:
            return ServiceStatusDetail(healthy=True, message="OK")
        return ServiceStatusDetail(
            healthy=False, message=f"Collection '{ms.collection_name}' not found"
        )
    except Exception as exc:
        return ServiceStatusDetail(healthy=False, message=str(exc))


def _check_http_service(base_url: str, path: str, name: str) -> ServiceStatusDetail:
    try:
        import httpx

        resp = httpx.get(f"{base_url}{path}", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ready", True):
                return ServiceStatusDetail(healthy=True, message="OK")
            return ServiceStatusDetail(healthy=False, message=f"{name} not ready")
        return ServiceStatusDetail(
            healthy=False, message=f"HTTP {resp.status_code}"
        )
    except Exception as exc:
        return ServiceStatusDetail(healthy=False, message=str(exc))
