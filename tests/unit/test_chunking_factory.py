"""Unit tests for chunking factory (create_chunker)."""

from __future__ import annotations

import pytest
from src.ingestion.chunking.factory import create_chunker


@pytest.mark.unit
class TestChunkingFactory:
    """Verify factory reads settings, applies kwargs, rejects unknown strategies."""

    def test_create_datasheet_chunker(self) -> None:
        chunker = create_chunker("datasheet")
        assert chunker is not None
        assert "datasheet" in type(chunker).__name__.lower() or "splitter" in type(chunker).__name__.lower()

    def test_create_fine_chunker(self) -> None:
        chunker = create_chunker("fine")
        assert chunker is not None

    def test_create_coarse_chunker(self) -> None:
        chunker = create_chunker("coarse")
        assert chunker is not None

    def test_create_parent_child_chunker(self) -> None:
        chunker = create_chunker("parent_child")
        assert chunker is not None

    def test_create_semantic_chunker(self) -> None:
        chunker = create_chunker("semantic")
        assert chunker is not None

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises((ValueError, KeyError)):
            create_chunker("nonexistent_strategy_xyz")

    def test_kwargs_override(self) -> None:
        """Factory should pass kwargs to the chunker constructor."""
        chunker = create_chunker("parent_child", child_size=128)
        assert chunker.child_size == 128

    def test_default_strategy_from_settings(self) -> None:
        """When strategy=None, factory reads from settings."""
        chunker = create_chunker(None)
        assert chunker is not None
