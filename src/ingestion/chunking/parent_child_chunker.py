"""Parent-child (small-to-big) chunker.

Child chunks (~256 chars) are used for vector retrieval; each stores a
``parent_id`` in metadata pointing to a larger parent chunk (~2048 chars)
that is returned as context.  Parent chunks are emitted with
``metadata["is_parent"] = True`` so the caller can store them separately.
"""

from __future__ import annotations

import re
from typing import Any

from src.core.types import Chunk
from src.ingestion.chunking.base import BaseChunker

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+")


class ParentChildChunker(BaseChunker):
    """Small-to-big chunker: child chunks for ANN, parent chunks for context."""

    def __init__(
        self,
        child_size: int = 256,
        parent_size: int = 2048,
        child_overlap: int = 32,
    ) -> None:
        self.child_size = child_size
        self.parent_size = parent_size
        self.child_overlap = child_overlap

    def split(
        self,
        text: str,
        tables: list[Any] | None = None,
        doc_id: str = "",
    ) -> list[Chunk]:
        if not text.strip():
            return []

        parent_chunks = self._make_parents(text, doc_id)
        all_chunks: list[Chunk] = []
        global_idx = 0

        for parent in parent_chunks:
            # Re-index parent with global counter
            parent = Chunk(
                chunk_id=parent.chunk_id,
                doc_id=parent.doc_id,
                content=parent.content,
                chunk_index=global_idx,
                metadata=parent.metadata,
            )
            all_chunks.append(parent)
            global_idx += 1

            children = self._make_children(
                parent.content, doc_id, parent.chunk_id, global_idx
            )
            all_chunks.extend(children)
            global_idx += len(children)

        return all_chunks

    # ── internal helpers ────────────────────────────────────────────

    def _make_parents(self, text: str, doc_id: str) -> list[Chunk]:
        paragraphs = text.split("\n\n")
        parents: list[Chunk] = []
        buf = ""
        idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = f"{buf}\n\n{para}".strip() if buf else para
            if len(candidate) > self.parent_size and buf:
                parents.append(Chunk(
                    chunk_id=f"{doc_id}_p{idx}",
                    doc_id=doc_id,
                    content=buf,
                    chunk_index=idx,
                    metadata={"is_parent": True},
                ))
                idx += 1
                buf = para
            else:
                buf = candidate

        if buf.strip():
            parents.append(Chunk(
                chunk_id=f"{doc_id}_p{idx}",
                doc_id=doc_id,
                content=buf.strip(),
                chunk_index=idx,
                metadata={"is_parent": True},
            ))

        return parents

    def _make_children(
        self, parent_text: str, doc_id: str, parent_id: str, start_idx: int
    ) -> list[Chunk]:
        sentences = _SENTENCE_RE.split(parent_text.strip())
        children: list[Chunk] = []
        buf = ""
        idx = start_idx

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            candidate = f"{buf} {sent}".strip() if buf else sent
            if len(candidate) > self.child_size and buf:
                children.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=buf,
                    chunk_index=idx,
                    metadata={"parent_id": parent_id, "is_parent": False},
                ))
                idx += 1
                overlap = buf[-self.child_overlap:] if self.child_overlap else ""
                buf = f"{overlap} {sent}".strip() if overlap else sent
            else:
                buf = candidate

        if buf.strip():
            children.append(Chunk(
                chunk_id=f"{doc_id}_c{idx}",
                doc_id=doc_id,
                content=buf.strip(),
                chunk_index=idx,
                metadata={"parent_id": parent_id, "is_parent": False},
            ))

        return children
