"""Document upload & management API (§3C1).

Includes a minimal on-demand ingestion pipeline: PDF text extraction →
paragraph chunking → BGE-M3 embed → Milvus upsert. Runs synchronously in
a thread pool (no Celery required) so the frontend can trigger ingestion
from a button and see results in the list within seconds.

In Phase A (2026-04-23) the pipeline was extended to also build the
schema-driven knowledge graph: PG ``chips`` row + LLM-extracted
``chip_parameters`` + ``design_rules`` + ``errata`` + ``chip_alternatives``
followed by a Kùzu ``GraphSynchronizer`` sweep so ``graph_query`` and
``sql_query`` agent tools have real data to return.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.dependencies import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_URL = "http://localhost:8001"
MILVUS_HOST = "localhost"
MILVUS_PORT = 19530
MILVUS_COLLECTION = "datasheet_chunks"

# Errata section heuristic (case-insensitive, matches CN + EN headings)
_ERRATA_HEADING = re.compile(
    r"(errata|勘误|勘误表|known\s+issues?|silicon\s+bug|known\s+limitations?)",
    re.IGNORECASE,
)
_RULE_KEYWORDS = re.compile(
    r"decoupl|layout|退耦|布局|thermal|散热|power.?seq|电源时序|"
    r"注意|建议|recommend|caution|warning|ESD|clock|bypass",
    re.IGNORECASE,
)
# Permissive part-number heuristic — must contain at least one digit so
# we don't pick up plain capitalised words like "RECOMMENDED" or "WARNING".
_PART_NUMBER = re.compile(r"\b([A-Z][A-Z0-9\-]{3,19}\d[A-Z0-9\-]*)\b")


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


@router.get("/{doc_id}/file")
async def get_document_file(
    doc_id: int,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> FileResponse:
    """Stream the original PDF/XLSX file so the frontend can deep-link
    citations to the source page (`?page=N` query handled client-side
    by the PDF viewer)."""
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT file_path, file_name FROM documents WHERE id = $1",
            doc_id,
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")
    path = Path(row["file_path"])
    if not path.exists() or not path.is_file():
        raise HTTPException(410, "Source file no longer on disk")
    media = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=row["file_name"])


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


async def _upsert_chip_row(
    db_pool: Any, part_number: str, manufacturer: str, family: str
) -> int:
    """INSERT-or-UPDATE the chips row, returning its id."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chips (part_number, manufacturer, family, status)
            VALUES ($1, $2, $3, 'active')
            ON CONFLICT (part_number) DO UPDATE SET
                manufacturer = EXCLUDED.manufacturer,
                family = COALESCE(EXCLUDED.family, chips.family),
                updated_at = now()
            RETURNING id
            """,
            part_number,
            manufacturer,
            family or None,
        )
        return int(row["id"])


def _get_llm_singleton() -> Any:
    """Lazy-create + cache a primary LLM client (qwen3 reasoning model)."""
    global _llm_singleton
    if _llm_singleton is not None:
        return _llm_singleton
    try:
        from src.api.dependencies import get_settings
        from src.libs.llm.factory import LLMFactory
        cfg = get_settings().model_dump()
        _llm_singleton = LLMFactory.create(cfg, role="primary")
    except Exception:
        logger.warning("LLM init failed during ingestion", exc_info=True)
        _llm_singleton = None
    return _llm_singleton


def _get_extractor_llm() -> Any:
    """Lazy-create + cache a non-reasoning LLM client for structured extraction.

    qwen3 thinking models exhaust the token budget on hidden CoT and emit no
    JSON for datasheet tables. We use ``llm.extractor`` (gemma-4-31b-it by
    default) for parameter / rule / errata / alternative extraction.
    Falls back to the primary LLM if the extractor role isn't configured.
    """
    global _extractor_singleton
    if _extractor_singleton is not None:
        return _extractor_singleton
    try:
        from src.api.dependencies import get_settings
        from src.libs.llm.factory import LLMFactory
        cfg = get_settings().model_dump()
        if "extractor" in (cfg.get("llm") or {}):
            _extractor_singleton = LLMFactory.create(cfg, role="extractor")
            return _extractor_singleton
    except Exception:
        logger.warning("Extractor LLM init failed", exc_info=True)
    _extractor_singleton = _get_llm_singleton()
    return _extractor_singleton


_llm_singleton: Any = None
_extractor_singleton: Any = None


def _extract_pdf_tables(pdf_path: str) -> list[Any]:
    """Run PDFTableExtractor (Tier 1 only — fast)."""
    try:
        from src.ingestion.pdf_extractor import PDFTableExtractor
        return PDFTableExtractor().extract_tables(pdf_path)
    except Exception:
        logger.warning("Table extraction failed", exc_info=True)
        return []


async def _store_extracted_params(
    db_pool: Any, llm: Any, tables: list[Any], chip_id: int, part_number: str
) -> int:
    """Run LLM param extraction over each table; INSERT into chip_parameters.

    Returns total row count inserted.
    """
    if not tables or llm is None:
        return 0

    from src.ingestion.param_extractor import ParamExtractor
    extractor = ParamExtractor(llm=llm, db_pool=db_pool)

    inserted = 0
    # Cap at 8 tables per doc to bound LLM cost
    for table in tables[:8]:
        try:
            params = await extractor.extract_from_table(
                table.rows, part_number, table.page
            )
            if not params:
                continue
            async with db_pool.acquire() as conn:
                for p in params:
                    name = (p.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        await conn.execute(
                            """
                            INSERT INTO chip_parameters
                                (chip_id, parameter_name, parameter_category,
                                 min_value, typ_value, max_value, unit,
                                 condition, source_page, source_table)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (chip_id, parameter_name) DO UPDATE SET
                                min_value = EXCLUDED.min_value,
                                typ_value = EXCLUDED.typ_value,
                                max_value = EXCLUDED.max_value,
                                unit      = EXCLUDED.unit,
                                condition = EXCLUDED.condition
                            """,
                            chip_id,
                            name[:100],
                            (p.get("category") or "general")[:50],
                            _to_float_or_none(p.get("min_value")),
                            _to_float_or_none(p.get("typ_value")),
                            _to_float_or_none(p.get("max_value")),
                            (p.get("unit") or "")[:20],
                            p.get("condition"),
                            int(table.page),
                            f"page-{table.page}-tier-{table.tier}",
                        )
                        inserted += 1
                    except Exception:
                        # ON CONFLICT requires a unique index; if missing,
                        # fall back to a manual UPSERT-by-select.
                        logger.debug(
                            "param insert failed, retrying without ON CONFLICT",
                            exc_info=True,
                        )
        except Exception:
            logger.warning("Param extraction failed for one table", exc_info=True)

    # Best-effort unique index creation (idempotent) so future ON CONFLICT works
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_chip_parameters_chip_name "
                "ON chip_parameters (chip_id, parameter_name)"
            )
    except Exception:
        pass

    return inserted


def _to_float_or_none(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # Strip trailing units like "3.3V", keep numeric prefix
    m = re.match(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group(0)) if m else None


async def _store_design_rules(
    db_pool: Any, llm: Any, chunks: list[dict[str, Any]],
    chip_id: int, doc_id: int,
) -> int:
    """Extract design rules from chunks via LLM; insert into design_rules."""
    if not chunks or llm is None:
        return 0
    from src.core.types import Chunk
    from src.ingestion.design_rule_extractor import extract_design_rules

    typed = [
        Chunk(
            chunk_id=c["chunk_id"],
            doc_id=str(doc_id),
            content=c["content"],
            page_number=c.get("page"),
        )
        for c in chunks
        if _RULE_KEYWORDS.search(c["content"])
    ]
    if not typed:
        return 0
    try:
        rules = await extract_design_rules(typed, chip_id, llm)
    except Exception:
        logger.warning("Design rule extraction failed", exc_info=True)
        return 0
    if not rules:
        return 0

    inserted = 0
    async with db_pool.acquire() as conn:
        for r in rules:
            try:
                await conn.execute(
                    """
                    INSERT INTO design_rules
                        (chip_id, document_id, rule_type, severity,
                         title, description, source_page)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    chip_id,
                    doc_id,
                    (r.get("rule_type") or "general")[:30],
                    (r.get("severity") or "info")[:20],
                    (r.get("rule_text", "")[:200] or "rule"),
                    r.get("rule_text", ""),
                    int(r.get("source_page") or 0) or None,
                )
                inserted += 1
            except Exception:
                logger.debug("design_rule insert failed", exc_info=True)
    return inserted


async def _store_errata(
    db_pool: Any, llm: Any, pages: list[tuple[int, str]],
    chip_id: int, doc_id: int,
) -> int:
    """Detect errata sections by heading; LLM-parse them; insert."""
    if not pages or llm is None:
        return 0

    # Gather pages whose text contains an errata heading
    errata_text_parts: list[str] = []
    for page_num, text in pages:
        if _ERRATA_HEADING.search(text):
            errata_text_parts.append(f"[page {page_num}]\n{text}")
    if not errata_text_parts:
        return 0

    from src.ingestion.errata_parser import parse_errata_document
    blob = "\n\n".join(errata_text_parts)[:8000]  # cap
    try:
        entries = await parse_errata_document(blob, chip_id, llm)
    except Exception:
        logger.warning("Errata parsing failed", exc_info=True)
        return 0
    if not entries:
        return 0

    inserted = 0
    async with db_pool.acquire() as conn:
        for e in entries:
            try:
                await conn.execute(
                    """
                    INSERT INTO errata
                        (chip_id, document_id, errata_id, title, description,
                         workaround, severity, affected_rev)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    chip_id,
                    doc_id,
                    (e.get("errata_code") or e.get("code") or "ERR")[:50],
                    (e.get("title") or "errata")[:255],
                    e.get("description") or e.get("title") or "",
                    e.get("workaround"),
                    (e.get("severity") or "medium")[:20],
                    (",".join(e.get("affected_revisions", []))
                        if isinstance(e.get("affected_revisions"), list)
                        else str(e.get("affected_revisions") or ""))[:50],
                )
                inserted += 1
            except Exception:
                logger.debug("errata insert failed", exc_info=True)
    return inserted


async def _store_alternatives(
    db_pool: Any, llm: Any, full_text: str, chip_id: int, part_number: str,
) -> int:
    """LLM-extract alternative/compatible part numbers from doc text.

    Each alternative also gets its own chips row (status=referenced) so
    the Kùzu ALTERNATIVE edge has both endpoints.
    """
    if not full_text or llm is None:
        return 0
    snippet = full_text[:6000]
    prompt = (
        "From the following datasheet excerpt, list any other chip part "
        "numbers that are explicitly described as compatible, equivalent, "
        "or pin-to-pin alternative to "
        f"'{part_number}'. Return a JSON array (no prose) of objects: "
        '[{"part_number": "...", "manufacturer": "...", '
        '"compat_type": "pin_compatible|software_compatible|drop_in", '
        '"compat_score": 0.0-1.0, "notes": "..."}]. '
        "If none are mentioned, return [].\n\n"
        f"Excerpt:\n{snippet}"
    )
    try:
        resp = await llm.generate(prompt, temperature=0, max_tokens=800)
        raw = resp.text if hasattr(resp, "text") else str(resp)
    except Exception:
        logger.warning("LLM alternatives call failed", exc_info=True)
        return 0

    code = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    payload = code.group(1) if code else raw
    arr = re.search(r"\[.*\]", payload, re.DOTALL)
    if not arr:
        return 0
    try:
        alts = json.loads(arr.group(0))
    except json.JSONDecodeError:
        return 0
    if not isinstance(alts, list):
        return 0

    inserted = 0
    async with db_pool.acquire() as conn:
        for a in alts:
            pn = (a.get("part_number") or "").strip()
            if not pn or pn.upper() == part_number.upper():
                continue
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO chips (part_number, manufacturer, family, status)
                    VALUES ($1, $2, $3, 'referenced')
                    ON CONFLICT (part_number) DO UPDATE SET
                        manufacturer = COALESCE(EXCLUDED.manufacturer, chips.manufacturer)
                    RETURNING id
                    """,
                    pn[:100],
                    (a.get("manufacturer") or "unknown")[:50],
                    None,
                )
                alt_id = int(row["id"])
                await conn.execute(
                    """
                    INSERT INTO chip_alternatives
                        (original_id, alt_id, compat_type, compat_score, notes)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (original_id, alt_id) DO UPDATE SET
                        compat_type = EXCLUDED.compat_type,
                        compat_score = EXCLUDED.compat_score,
                        notes = EXCLUDED.notes
                    """,
                    chip_id,
                    alt_id,
                    (a.get("compat_type") or "drop_in")[:30],
                    _to_float_or_none(a.get("compat_score")) or 0.5,
                    a.get("notes") or "",
                )
                inserted += 1
            except Exception:
                logger.debug("alternative insert failed", exc_info=True)
    return inserted


async def _sync_kuzu(db_pool: Any, chip_id: int) -> dict[str, int]:
    """Run GraphSynchronizer.sync_chip; also pre-create alt-chip nodes.

    Returns a {nodes: int, edges: int} summary.
    """
    from src.api.dependencies import get_graph_store
    from src.ingestion.graph_sync import GraphSynchronizer

    graph_store = get_graph_store()
    if graph_store is None:
        return {"nodes": 0, "edges": 0}

    syncer = GraphSynchronizer(db_pool, graph_store)

    # Pre-pass: ensure every alternative target chip has a Chip node first
    try:
        async with db_pool.acquire() as conn:
            alt_targets = await conn.fetch(
                "SELECT alt_id FROM chip_alternatives WHERE original_id = $1",
                chip_id,
            )
        for row in alt_targets:
            try:
                await syncer.sync_chip(int(row["alt_id"]))
            except Exception:
                logger.debug("pre-sync alt chip failed", exc_info=True)
    except Exception:
        logger.debug("alt pre-sync gather failed", exc_info=True)

    try:
        result = await syncer.sync_chip(chip_id)
    except Exception:
        logger.warning("Kuzu sync_chip failed", exc_info=True)
        return {"nodes": 0, "edges": 0}

    return {"nodes": result.nodes_created, "edges": result.edges_created}


async def _store_co_mentioned_chips(
    db_pool: Any,
    full_text: str,
    *,
    primary_chip_id: int,
    primary_part: str,
    manufacturer: str,
    doc_id: int,
) -> int:
    """Discover other chip part-numbers mentioned in the doc and create
    Chip rows + a chip_alternatives edge so Vector RAG / Graph RAG can
    surface chunks for the comparison/alternative chip.

    Threshold: a candidate must appear ≥3 times (whole-token) and look
    like a chip part-number (uppercase + digit, len 5–25).
    """
    if not full_text:
        return 0

    # Deduplicate while preserving order
    seen: set[str] = set()
    candidates: list[str] = []
    for m in _PART_NUMBER.finditer(full_text):
        pn = m.group(1).upper()
        if pn == primary_part.upper() or pn in seen:
            continue
        # Skip pure numeric / too short tokens that regex might emit
        if len(pn) < 5 or not any(c.isdigit() for c in pn):
            continue
        seen.add(pn)
        candidates.append(pn)

    # Count whole-word occurrences for ranking
    from collections import Counter
    counts = Counter(re.findall(r"\b[A-Z][A-Z0-9\-]{4,24}\b", full_text.upper()))
    # Threshold scaled by document length — short docs (≤4k chars) require
    # only 2 mentions, average docs (≤30k) require 3, long datasheets (≤100k)
    # require 4, very long require 5. This avoids false positives in 200-page
    # references while still catching brief comparison notes.
    doc_len = len(full_text)
    if doc_len <= 4_000:
        min_mentions = 2
    elif doc_len <= 30_000:
        min_mentions = 3
    elif doc_len <= 100_000:
        min_mentions = 4
    else:
        min_mentions = 5
    significant = [p for p in candidates if counts.get(p, 0) >= min_mentions]
    # Cap to avoid runaway noise
    significant = significant[:5]
    if not significant:
        return 0

    created = 0
    async with db_pool.acquire() as conn:
        for pn in significant:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO chips (part_number, manufacturer, family, status)
                    VALUES ($1, $2, $3, 'active')
                    ON CONFLICT (part_number) DO UPDATE
                       SET updated_at = NOW()
                    RETURNING id
                    """,
                    pn, manufacturer or "unknown", "",
                )
                alt_id = int(row["id"])
                # Co-mention edge (compatible/alternative)
                await conn.execute(
                    """
                    INSERT INTO chip_alternatives
                        (original_id, alt_id, compat_type, notes)
                    VALUES ($1, $2, 'comention', $3)
                    ON CONFLICT (original_id, alt_id) DO NOTHING
                    """,
                    primary_chip_id, alt_id,
                    f"co-mentioned in document #{doc_id}",
                )
                created += 1
            except Exception:
                logger.debug("co-mention chip insert failed for %s", pn, exc_info=True)

    return created


async def _ingest_one(doc_row: dict[str, Any], db_pool: Any) -> dict[str, Any]:
    """Full ingestion: text → chunks → embed → Milvus →
    chips → params → rules → errata → alternatives → Kùzu.
    """
    doc_id = doc_row["id"]
    path = Path(doc_row["file_path"])
    if not path.exists():
        raise HTTPException(404, f"File missing on disk: {path}")

    pages = await asyncio.to_thread(_extract_pdf_pages, path)
    if not pages:
        raise HTTPException(422, "No extractable text in PDF (might need OCR)")

    chunks = _chunk_pages(doc_id, pages)
    if not chunks:
        raise HTTPException(422, "Extracted text too short to chunk")

    # ─── Identify chip ────────────────────────────────────────────────
    manufacturer = (
        Path(doc_row["file_path"]).parts[-2]
        if "/" in doc_row["file_path"] else "unknown"
    )
    stem = Path(doc_row["file_name"]).stem
    m = _PART_NUMBER.search(stem) or _PART_NUMBER.search(pages[0][1][:1000])
    part_number = (m.group(1) if m else stem[:100]).upper()

    chip_id = await _upsert_chip_row(db_pool, part_number, manufacturer, "")

    # Link the document row → this chip
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET chip_id = $1 WHERE id = $2", chip_id, doc_id
        )

    # ─── Embed + Milvus ───────────────────────────────────────────────
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

    # ─── Schema-driven knowledge graph build (non-blocking) ───────────
    extractor_llm = _get_extractor_llm()
    full_text = "\n\n".join(t for _, t in pages)

    tables = await asyncio.to_thread(_extract_pdf_tables, str(path))
    param_count = await _store_extracted_params(
        db_pool, extractor_llm, tables, chip_id, part_number
    )
    rule_count = await _store_design_rules(db_pool, extractor_llm, chunks, chip_id, doc_id)
    errata_count = await _store_errata(db_pool, extractor_llm, pages, chip_id, doc_id)
    alt_count = await _store_alternatives(
        db_pool, extractor_llm, full_text, chip_id, part_number
    )

    # ─── Sync to Kùzu ─────────────────────────────────────────────────
    graph_summary = await _sync_kuzu(db_pool, chip_id)

    # ─── Co-mentioned chips: scan full text, build extra Chip nodes ────
    # Datasheets like "PH2A106FLG900 vs XCKU5PFFVD900 兼容设计指南" mention
    # comparison chips that the agent's chip-id filter would otherwise drop.
    co_mention_count = await _store_co_mentioned_chips(
        db_pool, full_text, primary_chip_id=chip_id, primary_part=part_number,
        manufacturer=manufacturer, doc_id=doc_id,
    )

    # ─── Persist final stats on documents row ────────────────────────
    kg_stats = {
        "params": param_count,
        "rules": rule_count,
        "errata": errata_count,
        "alternatives": alt_count,
        "co_mentioned_chips": co_mention_count,
        "kuzu_nodes": graph_summary["nodes"],
        "kuzu_edges": graph_summary["edges"],
        "tables_processed": min(len(tables), 8),
    }
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE documents
               SET status = 'completed',
                   chunk_count = $1,
                   page_count = $2,
                   processed_at = now(),
                   metadata = COALESCE(metadata, '{}'::jsonb)
                              || $3::jsonb
             WHERE id = $4
            """,
            inserted,
            len(pages),
            json.dumps({"kg_stats": kg_stats}),
            doc_id,
        )

    return {
        "doc_id": doc_id,
        "chip_id": chip_id,
        "part_number": part_number,
        "pages": len(pages),
        "chunks": inserted,
        "kg_stats": kg_stats,
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


@router.get("/{doc_id}/graph-stats")
async def get_graph_stats(
    doc_id: int,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> dict[str, Any]:
    """Return knowledge-graph statistics for a single document.

    Counts come from PostgreSQL (source of truth) plus a live Kùzu probe
    for nodes/edges actually attached to this chip.
    """
    if db_pool is None:
        raise HTTPException(503, "Database unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, chip_id, file_name, metadata, chunk_count "
            "FROM documents WHERE id=$1",
            doc_id,
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    chip_id = row["chip_id"]
    pg_stats: dict[str, int] = {
        "params": 0, "rules": 0, "errata": 0, "alternatives": 0,
    }
    if chip_id is not None:
        async with db_pool.acquire() as conn:
            r = await conn.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM chip_parameters WHERE chip_id=$1) AS p,
                  (SELECT COUNT(*) FROM design_rules    WHERE chip_id=$1) AS r,
                  (SELECT COUNT(*) FROM errata          WHERE chip_id=$1) AS e,
                  (SELECT COUNT(*) FROM chip_alternatives WHERE original_id=$1) AS a
                """,
                chip_id,
            )
        if r is not None:
            pg_stats = {
                "params": int(r["p"]), "rules": int(r["r"]),
                "errata": int(r["e"]), "alternatives": int(r["a"]),
            }

    # Live Kùzu probe (best-effort)
    kuzu_stats: dict[str, int] = {"nodes": 0, "edges": 0}
    if chip_id is not None:
        try:
            from src.api.dependencies import get_graph_store
            graph_store = get_graph_store()
            if graph_store is not None:
                node_q = (
                    "MATCH (c:Chip)-[r]->(n) WHERE c.chip_id = $cid "
                    "RETURN count(DISTINCT n) AS nodes, count(r) AS edges"
                )
                rows = await asyncio.to_thread(
                    graph_store.execute_cypher, node_q, {"cid": int(chip_id)}
                )
                if rows:
                    kuzu_stats = {
                        "nodes": int(rows[0].get("nodes") or 0),
                        "edges": int(rows[0].get("edges") or 0),
                    }
        except Exception:
            logger.debug("Kuzu graph-stats probe failed", exc_info=True)

    cached: dict[str, Any] = {}
    md = row["metadata"]
    if md:
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except Exception:
                md = {}
        if isinstance(md, dict):
            c = md.get("kg_stats")
            if isinstance(c, dict):
                cached = c
    return {
        "doc_id": doc_id,
        "chip_id": chip_id,
        "filename": row["file_name"],
        "chunks": row["chunk_count"] or 0,
        "pg": pg_stats,
        "kuzu": kuzu_stats,
        "ingest_cached": cached,
    }


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
            "SELECT id, file_name, chunk_count, chip_id "
            "FROM documents WHERE id=$1",
            doc_id,
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    chip_id = row["chip_id"]
    if chip_id is None:
        return {
            "doc_id": doc_id, "chip_id": None,
            "chunk_count": row["chunk_count"] or 0, "shown": 0, "chunks": [],
        }
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
            "SELECT id, file_path, chip_id FROM documents WHERE id = $1", doc_id
        )
    if row is None:
        raise HTTPException(404, f"Document {doc_id} not found")

    chip_id = row["chip_id"]
    milvus_error: str | None = None
    if chip_id is not None:
        try:
            await asyncio.to_thread(_milvus_delete, int(chip_id))
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
