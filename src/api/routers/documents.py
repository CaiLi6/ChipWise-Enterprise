"""Document upload & management API (§3C1).

Includes a minimal on-demand ingestion pipeline: PDF text extraction →
paragraph chunking → BGE-M3 embed → Milvus upsert. Runs synchronously in
a thread pool (no Celery required) so the frontend can trigger ingestion
from a button and see results in the list within seconds.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.dependencies import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}

CHIP_ID_OFFSET = 10_000  # synthetic chip_id = CHIP_ID_OFFSET + documents.id
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_URL = "http://localhost:8001"
MILVUS_HOST = "localhost"
MILVUS_PORT = 19530
MILVUS_COLLECTION = "datasheet_chunks"


# ---------------------------------------------------------------------------
# Upload + list + detail
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    manufacturer: str = Form("unknown"),
    collection: str = Form("default"),
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Upload a PDF/XLSX and persist metadata in PG."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed. Allowed: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB")

    file_hash = hashlib.sha256(content).hexdigest()
    dest_dir = Path(f"data/documents/{manufacturer}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    dest_path.write_bytes(content)

    doc_type = "datasheet" if ext == ".pdf" else "parameter_sheet"

    doc_id: int | None = None
    if db_pool is not None:
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO documents
                        (file_hash, file_path, file_name, file_size, doc_type,
                         collection, source_type, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'upload', 'uploaded')
                    ON CONFLICT (file_hash) DO UPDATE
                        SET file_path = EXCLUDED.file_path,
                            processed_at = now()
                    RETURNING id
                    """,
                    file_hash,
                    str(dest_path),
                    file.filename,
                    len(content),
                    doc_type,
                    collection,
                )
                doc_id = row["id"]
        except Exception as exc:
            logger.error("Failed to insert document row: %s", exc, exc_info=True)

    return {
        "task_id": f"doc-{doc_id}" if doc_id else "unsaved",
        "doc_id": doc_id,
        "status": "uploaded",
        "filename": file.filename,
        "file_size": len(content),
        "message": f"{file.filename} saved ({len(content)} bytes). Click 'Ingest' to index.",
    }


@router.get("")
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """List uploaded documents (most recent first)."""
    if db_pool is None:
        return {"documents": [], "page": page, "per_page": per_page, "total": 0}

    offset = max(0, (page - 1) * per_page)
    try:
        async with db_pool.acquire() as conn:
            total_row = await conn.fetchrow("SELECT COUNT(*) AS n FROM documents")
            rows = await conn.fetch(
                """
                SELECT id, file_name, file_path, file_size, doc_type,
                       collection, status, chunk_count, page_count, processed_at
                FROM documents
                ORDER BY processed_at DESC NULLS LAST, id DESC
                LIMIT $1 OFFSET $2
                """,
                per_page,
                offset,
            )
    except Exception as exc:
        logger.error("Failed to list documents: %s", exc, exc_info=True)
        raise HTTPException(503, "Database unavailable") from exc

    documents = [
        {
            "doc_id": r["id"],
            "filename": r["file_name"],
            "file_path": r["file_path"],
            "doc_type": r["doc_type"],
            "status": r["status"],
            "metadata": {
                "file_size": r["file_size"],
                "collection": r["collection"],
                "chunk_count": r["chunk_count"],
                "page_count": r["page_count"],
                "processed_at": r["processed_at"].isoformat() if r["processed_at"] else None,
            },
        }
        for r in rows
    ]
    return {
        "documents": documents,
        "page": page,
        "per_page": per_page,
        "total": total_row["n"] if total_row else 0,
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: int,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Get single document details."""
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, file_hash, file_name, file_path, file_size, doc_type,
                   collection, status, chunk_count, page_count, processed_at,
                   celery_task_id
            FROM documents WHERE id = $1
            """,
            doc_id,
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")
    return {
        "doc_id": row["id"],
        "filename": row["file_name"],
        "file_path": row["file_path"],
        "file_hash": row["file_hash"],
        "doc_type": row["doc_type"],
        "status": row["status"],
        "metadata": {
            "file_size": row["file_size"],
            "collection": row["collection"],
            "chunk_count": row["chunk_count"],
            "page_count": row["page_count"],
            "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
            "celery_task_id": row["celery_task_id"],
        },
    }


# ---------------------------------------------------------------------------
# Ingestion (on-demand, synchronous pipeline)
# ---------------------------------------------------------------------------


def _extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Blocking PDF text extraction. Returns [(page_number, text), ...]."""
    import pdfplumber

    pages: list[tuple[int, str]] = []
    with pdfplumber.open(str(path)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((idx, text))
    return pages


def _chunk_pages(
    doc_id: int, pages: list[tuple[int, str]]
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for page_num, raw in pages:
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            continue
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            body = text[start:end].strip()
            if len(body) >= 50:
                chunks.append(
                    {
                        "chunk_id": f"doc{doc_id}-p{page_num}-c{idx}",
                        "page": page_num,
                        "content": body,
                    }
                )
            idx += 1
            if end == len(text):
                break
            start = end - CHUNK_OVERLAP
    return chunks


def _milvus_upsert(
    chip_id: int,
    part_number: str,
    manufacturer: str,
    doc_type: str,
    collection_name: str,
    chunks: list[dict[str, Any]],
    dense: list[list[float]],
    sparse_raw: list[Any],
) -> int:
    """Blocking Milvus upsert. Deletes prior chunks for chip_id first."""
    from pymilvus import Collection, connections  # type: ignore[import-untyped]

    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    col = Collection(MILVUS_COLLECTION)
    col.load()
    col.delete(expr=f"chip_id == {chip_id}")

    rows: list[dict[str, Any]] = []
    for c, d, s in zip(chunks, dense, sparse_raw, strict=True):
        row: dict[str, Any] = {
            "chunk_id": c["chunk_id"],
            "dense_vector": d,
            "chip_id": chip_id,
            "part_number": part_number[:100],
            "manufacturer": manufacturer[:50],
            "doc_type": (doc_type or "datasheet")[:30],
            "page": c["page"],
            "section": "uploaded-doc",
            "content": c["content"],
            "collection": collection_name[:100],
        }
        if isinstance(s, dict) and s:
            row["sparse_vector"] = {int(k): float(v) for k, v in s.items()}
        rows.append(row)

    if rows:
        col.insert(rows)
        col.flush()
    return len(rows)


def _milvus_delete(chip_id: int) -> None:
    from pymilvus import Collection, connections

    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    col = Collection(MILVUS_COLLECTION)
    col.load()
    col.delete(expr=f"chip_id == {chip_id}")
    col.flush()


async def _ingest_one(doc_row: dict[str, Any], db_pool: Any) -> dict[str, Any]:
    doc_id = doc_row["id"]
    chip_id = CHIP_ID_OFFSET + doc_id
    path = Path(doc_row["file_path"])
    if not path.exists():
        raise HTTPException(404, f"File missing on disk: {path}")

    pages = await asyncio.to_thread(_extract_pdf_pages, path)
    if not pages:
        raise HTTPException(422, "No extractable text in PDF (might need OCR)")

    chunks = _chunk_pages(doc_id, pages)
    if not chunks:
        raise HTTPException(422, "Extracted text too short to chunk")

    texts = [c["content"] for c in chunks]
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{EMBED_URL}/encode",
            json={"texts": texts, "return_sparse": True},
        )
        resp.raise_for_status()
        data = resp.json()
    dense = data["dense"]
    sparse_raw = data.get("sparse") or [{}] * len(texts)

    manufacturer = Path(doc_row["file_path"]).parts[-2] if "/" in doc_row["file_path"] else "unknown"
    stem = Path(doc_row["file_name"]).stem
    # Extract the first chip-like token (e.g. "PH2A106FLG900" from
    # "PH2A106FLG900 & XCKU5PFFVD900兼容设计指南--梅卡曼德").
    m = re.search(r"[A-Z][A-Z0-9]{4,19}", stem)
    part_number = m.group(0) if m else stem[:100]

    inserted = await asyncio.to_thread(
        _milvus_upsert,
        chip_id,
        part_number,
        manufacturer,
        doc_row["doc_type"] or "datasheet",
        doc_row["collection"] or "default",
        chunks,
        dense,
        sparse_raw,
    )

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE documents
               SET status = 'completed',
                   chunk_count = $1,
                   page_count = $2,
                   processed_at = now()
             WHERE id = $3
            """,
            inserted,
            len(pages),
            doc_id,
        )

    return {
        "doc_id": doc_id,
        "chip_id": chip_id,
        "pages": len(pages),
        "chunks": inserted,
    }


def _milvus_query_chunks(chip_id: int, limit: int) -> list[dict[str, Any]]:
    from pymilvus import Collection, connections

    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    col = Collection(MILVUS_COLLECTION)
    col.load()
    rows = col.query(
        expr=f"chip_id == {chip_id}",
        output_fields=["chunk_id", "page", "section", "part_number", "content"],
        limit=limit,
    )
    rows.sort(key=lambda r: (r.get("page") or 0, r.get("chunk_id") or ""))
    return [dict(r) for r in rows]


@router.get("/{doc_id}/chunks")
async def list_document_chunks(
    doc_id: int,
    limit: int = 10,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return up to `limit` indexed chunks for the given document."""
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, file_name, chunk_count FROM documents WHERE id=$1", doc_id
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    chip_id = CHIP_ID_OFFSET + doc_id
    try:
        chunks = await asyncio.to_thread(_milvus_query_chunks, chip_id, min(limit, 50))
    except Exception as exc:
        logger.warning("Milvus chunk query failed: %s", exc)
        chunks = []
    return {
        "doc_id": doc_id,
        "chip_id": chip_id,
        "chunk_count": row["chunk_count"] or 0,
        "shown": len(chunks),
        "chunks": chunks,
    }


@router.post("/{doc_id}/ingest")
async def ingest_single(
    doc_id: int,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, file_name, file_path, doc_type, collection FROM documents WHERE id = $1",
            doc_id,
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE documents SET status='processing' WHERE id=$1", doc_id)

    try:
        result = await _ingest_one(dict(row), db_pool)
    except HTTPException:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status='failed' WHERE id=$1", doc_id)
        raise
    except Exception as exc:
        logger.exception("Ingestion failed for doc %s", doc_id)
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status='failed' WHERE id=$1", doc_id)
        raise HTTPException(500, f"Ingestion failed: {exc}") from exc

    return {"status": "completed", **result}


@router.post("/ingest-all")
async def ingest_all(
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Ingest every document whose status is uploaded / pending / failed."""
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, file_name, file_path, doc_type, collection
            FROM documents
            WHERE status IN ('uploaded', 'pending', 'failed')
            ORDER BY id
            """,
        )

    processed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for r in rows:
        doc_id = r["id"]
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status='processing' WHERE id=$1", doc_id)
        try:
            result = await _ingest_one(dict(r), db_pool)
            processed.append(result)
        except Exception as exc:
            logger.exception("Ingestion failed for doc %s", doc_id)
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE documents SET status='failed' WHERE id=$1", doc_id)
            errors.append({"doc_id": doc_id, "error": str(exc)})

    return {
        "total": len(rows),
        "succeeded": len(processed),
        "failed": len(errors),
        "processed": processed,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Delete a document: Milvus chunks, PG row, and the file on disk."""
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, file_path FROM documents WHERE id = $1", doc_id
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    chip_id = CHIP_ID_OFFSET + doc_id
    milvus_error: str | None = None
    try:
        await asyncio.to_thread(_milvus_delete, chip_id)
    except Exception as exc:
        logger.warning("Milvus delete failed for chip_id=%s: %s", chip_id, exc)
        milvus_error = str(exc)

    file_removed = False
    try:
        path = Path(row["file_path"])
        if path.exists():
            path.unlink()
            file_removed = True
    except Exception as exc:
        logger.warning("Could not remove file %s: %s", row["file_path"], exc)

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM documents WHERE id=$1", doc_id)

    return {
        "doc_id": doc_id,
        "deleted": True,
        "file_removed": file_removed,
        "milvus_error": milvus_error,
    }
