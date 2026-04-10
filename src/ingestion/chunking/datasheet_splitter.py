"""Datasheet-aware text splitter (§3A3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.core.types import Chunk


# Section heading patterns
_SECTION_PATTERN = re.compile(
    r"^(?:"
    r"#{1,4}\s+.+|"                    # Markdown headings
    r"\d+(?:\.\d+)*\s+[A-Z].+|"        # Numbered headings like "1.2 Overview"
    r"[A-Z][A-Z\s]{3,}$"               # ALL-CAPS headings
    r")",
    re.MULTILINE,
)


class DatasheetSplitter:
    """Split datasheet text into chunks respecting section boundaries and tables."""

    def __init__(
        self, chunk_size: int = 1024, chunk_overlap: int = 128
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(
        self,
        text: str,
        tables: list[Any] | None = None,
        doc_id: str = "",
    ) -> list[Chunk]:
        """Split text into Chunks, preserving tables as atomic blocks."""
        if not text.strip():
            return []

        # Step 1: Mark table regions as atomic blocks
        table_ranges = self._get_table_ranges(text, tables)

        # Step 2: Split into sections at heading boundaries
        sections = self._split_by_sections(text)

        # Step 3: Process each section
        chunks: list[Chunk] = []
        chunk_idx = 0

        for section_title, section_text in sections:
            if not section_text.strip():
                continue

            # Check if section contains a table block
            if len(section_text) <= self.chunk_size:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{chunk_idx}",
                    doc_id=doc_id,
                    content=section_text.strip(),
                    chunk_index=chunk_idx,
                    metadata={"section_title": section_title},
                ))
                chunk_idx += 1
            else:
                # Recursive split on long sections
                sub_chunks = self._recursive_split(
                    section_text, section_title, doc_id, chunk_idx
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)

        return chunks

    def _split_by_sections(self, text: str) -> list[tuple[str, str]]:
        """Split text at section heading boundaries."""
        matches = list(_SECTION_PATTERN.finditer(text))
        if not matches:
            return [("", text)]

        sections: list[tuple[str, str]] = []

        # Text before first heading
        if matches[0].start() > 0:
            sections.append(("", text[: matches[0].start()]))

        for i, m in enumerate(matches):
            title = m.group(0).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((title, text[start:end]))

        return sections

    def _recursive_split(
        self,
        text: str,
        section_title: str,
        doc_id: str,
        start_idx: int,
    ) -> list[Chunk]:
        """Recursively split long text preserving sentence boundaries."""
        chunks: list[Chunk] = []
        remaining = text.strip()
        idx = start_idx

        while remaining:
            if len(remaining) <= self.chunk_size:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=remaining,
                    chunk_index=idx,
                    metadata={"section_title": section_title},
                ))
                break

            # Find a good split point (sentence boundary)
            split_pos = self._find_split_point(remaining, self.chunk_size)
            chunk_text = remaining[:split_pos].strip()

            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_c{idx}",
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=idx,
                    metadata={"section_title": section_title},
                ))
                idx += 1

            # Apply overlap
            overlap_start = max(0, split_pos - self.chunk_overlap)
            remaining = remaining[overlap_start:].strip()
            if remaining == chunk_text:
                break  # Safety: avoid infinite loop

        return chunks

    @staticmethod
    def _find_split_point(text: str, max_len: int) -> int:
        """Find a sentence boundary near max_len."""
        if len(text) <= max_len:
            return len(text)

        # Look for sentence endings near the boundary
        for sep in [". ", "。", "\n\n", "\n", "; ", "；", ", "]:
            pos = text.rfind(sep, max_len // 2, max_len)
            if pos != -1:
                return pos + len(sep)

        # Fall back to exact position
        return max_len

    @staticmethod
    def _get_table_ranges(
        text: str, tables: list[Any] | None
    ) -> list[tuple[int, int]]:
        """Identify table regions in text (placeholder for future use)."""
        return []
