"""Evaluation ingest — chunk + embed corpus with a given strategy into an isolated Milvus collection."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.types import Chunk

logger = logging.getLogger(__name__)


def ingest_for_eval(
    strategy: str,
    corpus_dir: str | Path,
    collection_name: str | None = None,
) -> tuple[str, list[Chunk]]:
    """Ingest documents from *corpus_dir* using the given chunking *strategy*.

    This is a **synchronous** call (no Celery) that:
    1. Extracts text from PDFs
    2. Chunks using the specified strategy
    3. Embeds via BGE-M3
    4. Upserts into an isolated Milvus collection

    Args:
        strategy: Chunking strategy name (e.g. ``"datasheet"``, ``"fine"``).
        corpus_dir: Directory containing sampled PDF files.
        collection_name: Milvus collection name.  Defaults to
            ``chipwise_eval_{strategy}_{timestamp}``.

    Returns:
        Tuple of (collection_name, all_chunks).
    """
    corpus_dir = Path(corpus_dir)

    if collection_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        collection_name = f"chipwise_eval_{strategy}_{ts}"

    from src.ingestion.chunking.factory import create_chunker

    chunker = create_chunker(strategy)
    all_chunks: list[Chunk] = []

    pdfs = sorted(corpus_dir.glob("*.pdf"))
    logger.info("Ingesting %d PDFs with strategy=%s → collection=%s", len(pdfs), strategy, collection_name)

    for pdf_path in pdfs:
        text = _extract_text(pdf_path)
        if not text:
            continue
        doc_id = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]
        chunks = chunker.split(text, doc_id=doc_id)
        all_chunks.extend(chunks)

    logger.info("Total chunks: %d", len(all_chunks))

    if all_chunks:
        _embed_and_store(all_chunks, collection_name)

    return collection_name, all_chunks


def _extract_text(pdf_path: Path) -> str:
    """Extract full text from a PDF."""
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    except Exception as e:
        logger.error("Text extraction failed for %s: %s", pdf_path, e)
        return ""


def _embed_and_store(chunks: list[Chunk], collection_name: str) -> None:
    """Embed chunks and upsert into Milvus (best-effort)."""
    try:
        from src.libs.embedding.factory import create_embedding

        embedder = create_embedding()
        texts = [c.content for c in chunks]
        embeddings = embedder.embed(texts)

        from src.libs.vector_store.factory import create_vector_store

        store = create_vector_store()
        store.upsert(
            collection_name=collection_name,
            chunks=chunks,
            embeddings=embeddings,
        )
        logger.info("Stored %d chunks in Milvus collection %s", len(chunks), collection_name)
    except Exception as e:
        logger.warning("Embed/store failed (eval will use text-only metrics): %s", e)
