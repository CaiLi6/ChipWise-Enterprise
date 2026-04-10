"""FastAPI application factory — creates the main ChipWise gateway app."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.settings import Settings, load_settings

# ── Version / startup time ──────────────────────────────────────────

APP_VERSION = "0.1.0"
_start_time: float = 0.0

# ── Global exception handlers ──────────────────────────────────────


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions → uniform JSON error."""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": str(exc),
            "trace_id": trace_id,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic / query-param validation errors → 422 JSON."""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "detail": str(exc),
            "trace_id": trace_id,
        },
    )


# ── App factory ─────────────────────────────────────────────────────


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional pre-loaded Settings; loads from default YAML if None.
    """
    global _start_time
    _start_time = time.time()

    if settings is None:
        try:
            settings = load_settings()
        except Exception:
            settings = Settings(
                llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
                embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
            )

    app = FastAPI(
        title="ChipWise Enterprise",
        description="Chip data intelligence retrieval and analysis platform",
        version=APP_VERSION,
    )

    # Store settings on app state for DI
    app.state.settings = settings

    # CORS — allow frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:7860",
            "http://127.0.0.1:7860",
            "http://localhost:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trace ID middleware — inject X-Request-ID on every response
    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response

    # Exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Register routers
    from src.api.routers.health import router as health_router
    from src.api.routers.auth import router as auth_router
    from src.api.routers.documents import router as documents_router
    from src.api.routers.tasks import router as tasks_router
    from src.api.routers.compare import router as compare_router
    from src.api.routers.knowledge import router as knowledge_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(tasks_router)
    app.include_router(compare_router)
    app.include_router(knowledge_router)

    return app


# ── Module-level app (for `uvicorn src.api.main:app`) ──────────────

app = create_app()
