"""Coarse-grained chunker: section-level splits (~2048 chars)."""

from __future__ import annotations

import re
from typing import Any

from src.core.types import Chunk
from src.ingestion.chunking.base import BaseChunker

_SECTION_PATTERN = re.compile(
    r"^(?:"
    r"#{1,4}\s+.+|"
    r"\d+(?:\.\d+)*\s+[A-Z].+|"
    r"[A-Z][A-Z\s]{3,}$"
    r")",
    re.MULTILINE,
)


class CoarseGrainedChunker(BaseChunker):
    """Split text into large, context-rich chunks (~2048 chars)."""

    def __init__(self, chunk_size: int = 2048, chunk_overlap: int = 256) -> None:
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

        sections = self._split_by_sections(text)
        chunks: list[Chunk] = []
        idx = 0
        buf = ""
        current_title = ""

        for title, body in sections:
            segment = body.strip()
            if not segment:
                continue

            if title:
                current_title = title

            candidate = f"{buf}\n\n{segment}".strip() if buf else segment

            if len(candidate) > self.chunk_size and buf:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=buf,
                    chunk_index=idx,
                    metadata={"section_title": current_title},
                ))
                idx += 1
                overlap_text = buf[-self.chunk_overlap:] if self.chunk_overlap else ""
                buf = f"{overlap_text}\n\n{segment}".strip() if overlap_text else segment
            else:
                buf = candidate

        if buf.strip():
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_c{idx}",
                doc_id=doc_id,
                content=buf.strip(),
                chunk_index=idx,
                metadata={"section_title": current_title},
            ))

        return chunks

    @staticmethod
    def _split_by_sections(text: str) -> list[tuple[str, str]]:
        matches = list(_SECTION_PATTERN.finditer(text))
        if not matches:
            return [("", text)]

        sections: list[tuple[str, str]] = []
        if matches[0].start() > 0:
            sections.append(("", text[: matches[0].start()]))

        for i, m in enumerate(matches):
            title = m.group(0).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((title, text[start:end]))

        return sections
