"""bce-reranker FastAPI microservice (port 8002).

Loads maidalun1020/bce-reranker-base_v1 at startup and exposes:
- POST /rerank — rerank documents against a query
- GET  /health — readiness probe
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("reranker_service")

# ── Request / Response schemas ──────────────────────────────────────

MODEL_NAME = "maidalun1020/bce-reranker-base_v1"


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int = Field(default=10, ge=1)


class RerankResult(BaseModel):
    index: int
    score: float
    text: str


class RerankResponse(BaseModel):
    results: list[RerankResult]
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    ready: bool


# ── Global model state ──────────────────────────────────────────────

_model: Any = None
_model_ready: bool = False


def load_model(model_name: str = MODEL_NAME) -> Any:
    """Load bce-reranker via sentence-transformers CrossEncoder. Called at startup."""
    global _model, _model_ready
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

        logger.info("Loading model %s ...", model_name)
        _model = CrossEncoder(model_name)
        _model_ready = True
        logger.info("Model %s loaded successfully.", model_name)
        return _model
    except Exception:
        logger.exception("Failed to load model %s", model_name)
        _model_ready = False
        raise


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Load model on startup; cleanup on shutdown."""
    try:
        load_model()
    except Exception:
        logger.warning("Model failed to load — service will report not ready.")
    yield


# ── FastAPI app ─────────────────────────────────────────────────────

app = FastAPI(title="ChipWise Reranker Service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if _model_ready else "loading",
        model=MODEL_NAME,
        ready=_model_ready,
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    if not _model_ready or _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if len(request.documents) == 0:
        return RerankResponse(results=[], model=MODEL_NAME)

    # Build query-document pairs for CrossEncoder
    pairs = [[request.query, doc] for doc in request.documents]
    scores = _model.predict(pairs)

    # Convert numpy array to list of floats
    if hasattr(scores, "tolist"):
        scores = scores.tolist()

    # Build indexed results and sort by score descending
    indexed_results = [
        RerankResult(index=i, score=float(s), text=request.documents[i])
        for i, s in enumerate(scores)
    ]
    indexed_results.sort(key=lambda r: r.score, reverse=True)

    # Apply top_k truncation
    truncated = indexed_results[: request.top_k]

    return RerankResponse(results=truncated, model=MODEL_NAME)
