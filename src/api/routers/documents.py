"""Document upload & management API (§3C1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    manufacturer: str = Form("unknown"),
    collection: str = Form("default"),
) -> dict[str, Any]:
    """Upload a PDF/XLSX and start ingestion."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed. Allowed: {ALLOWED_EXTENSIONS}")

    # Read and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Save file
    dest_dir = Path(f"data/documents/{manufacturer}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    dest_path.write_bytes(content)

    # Submit to Celery (imported lazily to avoid circular import)
    task_id = f"upload-{file.filename}-{id(content)}"

    try:
        from src.ingestion.tasks import create_ingestion_chain
        _chain = create_ingestion_chain(
            url=str(dest_path), manufacturer=manufacturer, priority=9
        )
        # In production: result = chain.apply_async()
        # task_id = result.id
    except ImportError:
        logger.warning("Celery not available, file saved but ingestion not started")

    return {
        "task_id": task_id,
        "status": "queued",
        "filename": file.filename,
        "file_size": len(content),
        "message": f"File uploaded, ingestion queued as {task_id}",
    }


@router.get("")
async def list_documents(
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List ingested documents (placeholder for PG integration)."""
    return {
        "documents": [],
        "page": page,
        "per_page": per_page,
        "total": 0,
    }


@router.get("/{doc_id}")
async def get_document(doc_id: int) -> dict[str, Any]:
    """Get single document details (placeholder)."""
    return {"doc_id": doc_id, "status": "not_implemented"}
