"""Core data contracts (§4.3 Data Contracts).

Five types flow through the entire pipeline. Extend via subclasses,
never break the base contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """Ingested file metadata."""
    doc_id: str
    title: str = ""
    source_url: str = ""
    file_path: str = ""
    file_hash: str = ""
    doc_type: str = "datasheet"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """Text segment with position info."""
    chunk_id: str
    doc_id: str
    content: str
    chunk_index: int = 0
    page_number: int | None = None
    section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    """Chunk + embedding vectors, ready for vector store upsert."""
    chunk_id: str
    doc_id: str
    content: str
    dense_vector: list[float] = field(default_factory=list)
    sparse_vector: dict[int, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedQuery:
    """Rewritten query + conversation context + extracted entities."""
    original_query: str
    rewritten_query: str = ""
    entities: list[str] = field(default_factory=list)
    context: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Ranked chunk with citation and score."""
    chunk_id: str
    doc_id: str
    content: str
    score: float = 0.0
    source: str = ""
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

