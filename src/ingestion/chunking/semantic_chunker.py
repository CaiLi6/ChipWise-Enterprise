"""Semantic chunker: embedding-based breakpoint detection (optional).

Uses BGE-M3 sentence embeddings to find natural semantic boundaries.
Expensive — intended as a comparison baseline, not production default.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.core.types import Chunk
from src.ingestion.chunking.base import BaseChunker

logger = logging.getLogger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class SemanticChunker(BaseChunker):
    """Chunk by detecting cosine-similarity breakpoints between sentences."""

    def __init__(
        self,
        min_size: int = 200,
        max_size: int = 1500,
        similarity_threshold: float = 0.7,
    ) -> None:
        self.min_size = min_size
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold

    def split(
        self,
        text: str,
        tables: list[Any] | None = None,
        doc_id: str = "",
    ) -> list[Chunk]:
        if not text.strip():
            return []

        sentences = [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]
        if not sentences:
            return [Chunk(chunk_id=f"{doc_id}_c0", doc_id=doc_id, content=text.strip(), chunk_index=0)]

        embeddings = self._embed_sentences(sentences)

        # If embedding service unavailable, fall back to simple size-based split
        if embeddings is None:
            return self._fallback_split(sentences, doc_id)

        breakpoints = self._find_breakpoints(embeddings)
        return self._build_chunks(sentences, breakpoints, doc_id)

    def _embed_sentences(self, sentences: list[str]) -> list[list[float]] | None:
        """Get sentence embeddings from BGE-M3 service."""
        try:
            from src.libs.embedding.factory import EmbeddingFactory

            client = EmbeddingFactory.create({})
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                client.encode(sentences, return_sparse=False)
            )
            return result.dense if result.dense else None
        except Exception:
            logger.warning("Embedding service unavailable; semantic chunker falling back to size-based split")
            return None

    def _find_breakpoints(self, embeddings: list[list[float]]) -> list[int]:
        """Find indices where consecutive similarity drops below threshold."""
        breaks: list[int] = []
        for i in range(1, len(embeddings)):
            sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
            if sim < self.similarity_threshold:
                breaks.append(i)
        return breaks

    def _build_chunks(
        self, sentences: list[str], breakpoints: list[int], doc_id: str
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0
        start = 0

        all_breaks = breakpoints + [len(sentences)]

        for bp in all_breaks:
            segment = " ".join(sentences[start:bp]).strip()
            if not segment:
                start = bp
                continue

            # Enforce max_size: split oversized segments
            while len(segment) > self.max_size:
                cut = segment.rfind(". ", 0, self.max_size)
                if cut == -1:
                    cut = self.max_size
                else:
                    cut += 2
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=segment[:cut].strip(),
                    chunk_index=idx,
                ))
                idx += 1
                segment = segment[cut:].strip()

            if segment:
                # Merge small segments with previous chunk
                if chunks and len(segment) < self.min_size:
                    chunks[-1] = Chunk(
                        chunk_id=chunks[-1].chunk_id,
                        doc_id=doc_id,
                        content=f"{chunks[-1].content} {segment}".strip(),
                        chunk_index=chunks[-1].chunk_index,
                    )
                else:
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}_c{idx}",
                        doc_id=doc_id,
                        content=segment,
                        chunk_index=idx,
                    ))
                    idx += 1

            start = bp

        return chunks

    def _fallback_split(self, sentences: list[str], doc_id: str) -> list[Chunk]:
        """Simple size-based fallback when embeddings are unavailable."""
        chunks: list[Chunk] = []
        buf = ""
        idx = 0

        for sent in sentences:
            candidate = f"{buf} {sent}".strip() if buf else sent
            if len(candidate) > self.max_size and buf:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=buf,
                    chunk_index=idx,
                ))
                idx += 1
                buf = sent
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
