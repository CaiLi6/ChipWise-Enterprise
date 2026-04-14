"""Fine-grained chunker: sentence-level splits (~256 chars)."""

from __future__ import annotations

import re
from typing import Any

from src.core.types import Chunk
from src.ingestion.chunking.base import BaseChunker

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+")


class FineGrainedChunker(BaseChunker):
    """Split text into small, sentence-level chunks for maximum retrieval precision."""

    def __init__(self, chunk_size: int = 256, chunk_overlap: int = 32) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(
        self,
        text: str,
        tables: list[Any] | None = None,
        doc_id: str = "",
    ) -> list[Chunk]:
        if not text.strip():
            return []

        sentences = _SENTENCE_RE.split(text.strip())
        chunks: list[Chunk] = []
        buf = ""
        idx = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            candidate = f"{buf} {sent}".strip() if buf else sent

            if len(candidate) > self.chunk_size and buf:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=buf,
                    chunk_index=idx,
                ))
                idx += 1
                # Overlap: keep tail of previous buffer
                overlap_text = buf[-self.chunk_overlap:] if self.chunk_overlap else ""
                buf = f"{overlap_text} {sent}".strip() if overlap_text else sent
            else:
                buf = candidate

        if buf.strip():
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_c{idx}",
                doc_id=doc_id,
                content=buf.strip(),
                chunk_index=idx,
            ))

        return chunks
