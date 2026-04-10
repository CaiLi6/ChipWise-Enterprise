"""BGE-M3 Embedding FastAPI microservice (port 8001).

Loads BAAI/bge-m3 at startup and exposes:
- POST /encode — produce dense (1024-dim) + optional sparse vectors
- GET  /health — readiness probe
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("embedding_service")

# ── Request / Response schemas ──────────────────────────────────────

MAX_BATCH_SIZE = 64
MODEL_NAME = "BAAI/bge-m3"


class EncodeRequest(BaseModel):
    texts: list[str]
    return_sparse: bool = True


class EncodeResponse(BaseModel):
    dense: list[list[float]]
    sparse: list[dict[str, float]] | None = None
    dimensions: int
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    ready: bool


# ── Global model state ──────────────────────────────────────────────

_model: Any = None
_model_ready: bool = False


def load_model(model_name: str = MODEL_NAME) -> Any:
    """Load BGE-M3 via FlagEmbedding. Called at startup."""
    global _model, _model_ready
    try:
        from FlagEmbedding import BGEM3FlagModel

        logger.info("Loading model %s ...", model_name)
        _model = BGEM3FlagModel(model_name, use_fp16=True)
        _model_ready = True
        logger.info("Model %s loaded successfully.", model_name)
        return _model
    except Exception:
        logger.exception("Failed to load model %s", model_name)
        _model_ready = False
        raise


# ── Lifespan ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup; cleanup on shutdown."""
    try:
        load_model()
    except Exception:
        logger.warning("Model failed to load — service will report not ready.")
    yield


# ── FastAPI app ─────────────────────────────────────────────────────

app = FastAPI(title="ChipWise Embedding Service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if _model_ready else "loading",
        model=MODEL_NAME,
        ready=_model_ready,
    )


@app.post("/encode", response_model=EncodeResponse)
async def encode(request: EncodeRequest) -> EncodeResponse:
    if not _model_ready or _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if len(request.texts) == 0:
        raise HTTPException(status_code=400, detail="texts must not be empty")

    if len(request.texts) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"Batch size {len(request.texts)} exceeds maximum of {MAX_BATCH_SIZE}",
        )

    result = _model.encode(
        request.texts,
        return_dense=True,
        return_sparse=request.return_sparse,
        return_colbert_vecs=False,
    )

    dense_vectors: list[list[float]] = result["dense_vecs"].tolist()

    sparse_vectors: list[dict[str, float]] | None = None
    if request.return_sparse and "lexical_weights" in result:
        sparse_vectors = [
            {str(k): float(v) for k, v in token_weights.items()}
            for token_weights in result["lexical_weights"]
        ]

    return EncodeResponse(
        dense=dense_vectors,
        sparse=sparse_vectors,
        dimensions=len(dense_vectors[0]) if dense_vectors else 0,
        model=MODEL_NAME,
    )
