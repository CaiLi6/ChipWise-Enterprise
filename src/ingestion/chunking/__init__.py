"""Text chunking strategies (pluggable via BaseChunker + factory)."""

from src.ingestion.chunking.base import BaseChunker
from src.ingestion.chunking.factory import create_chunker

__all__ = ["BaseChunker", "create_chunker"]
