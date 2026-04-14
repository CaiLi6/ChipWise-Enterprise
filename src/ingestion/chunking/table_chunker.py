"""Table-specific chunker: preserves headers across chunks (§3A4)."""

from __future__ import annotations

from src.core.types import Chunk


class TableChunker:
    """Chunk extracted tables for vector search, preserving headers."""

    def __init__(self, chunk_size: int = 1024) -> None:
        self.chunk_size = chunk_size

    def chunk_table(
        self,
        table_rows: list[list[str]],
        chip_name: str = "",
        section: str = "",
        page: int = 0,
        doc_id: str = "",
        start_index: int = 0,
    ) -> list[Chunk]:
        """Split a table into one or more chunks.

        Small tables (fits in chunk_size): single chunk as Markdown table.
        Large tables: split by row groups, each chunk keeps the header row.
        """
        if not table_rows:
            return []

        md_full = self._to_markdown_table(table_rows)

        # Small table → single chunk
        if len(md_full) <= self.chunk_size:
            return [
                Chunk(
                    chunk_id=f"{doc_id}_t{start_index}",
                    doc_id=doc_id,
                    content=md_full,
                    chunk_index=start_index,
                    page_number=page,
                    metadata={
                        "is_table": True,
                        "section": section,
                        "chip_name": chip_name,
                        "page": page,
                    },
                )
            ]

        # Large table → split by row groups, keep header
        header = table_rows[0] if table_rows else []
        data_rows = table_rows[1:]
        chunks: list[Chunk] = []
        idx = start_index
        group: list[list[str]] = []

        for row in data_rows:
            test_rows = [header] + group + [row]
            test_md = self._to_markdown_table(test_rows)
            if len(test_md) > self.chunk_size and group:
                # Flush current group
                md = self._to_markdown_table([header] + group)
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_t{idx}",
                    doc_id=doc_id,
                    content=md,
                    chunk_index=idx,
                    page_number=page,
                    metadata={
                        "is_table": True,
                        "section": section,
                        "chip_name": chip_name,
                        "page": page,
                    },
                ))
                idx += 1
                group = [row]
            else:
                group.append(row)

        # Remaining rows
        if group:
            md = self._to_markdown_table([header] + group)
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_t{idx}",
                doc_id=doc_id,
                content=md,
                chunk_index=idx,
                page_number=page,
                metadata={
                    "is_table": True,
                    "section": section,
                    "chip_name": chip_name,
                    "page": page,
                },
            ))

        return chunks

    @staticmethod
    def _to_markdown_table(rows: list[list[str]]) -> str:
        """Convert a 2D list to Markdown table format."""
        if not rows:
            return ""

        # Normalize column count
        max_cols = max(len(r) for r in rows)
        normalized = [r + [""] * (max_cols - len(r)) for r in rows]

        lines: list[str] = []
        # Header
        lines.append("| " + " | ".join(normalized[0]) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        # Data rows
        for row in normalized[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)
