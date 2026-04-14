"""Chunker factory — mirrors ``src/libs/llm/factory.py``."""

from __future__ import annotations

import logging
from typing import Any

from src.ingestion.chunking.base import BaseChunker

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[BaseChunker]] = {}


def _ensure_registry() -> dict[str, type[BaseChunker]]:
    """Lazily populate the strategy registry to avoid circular imports."""
    if _REGISTRY:
        return _REGISTRY

    from src.ingestion.chunking.coarse_chunker import CoarseGrainedChunker
    from src.ingestion.chunking.datasheet_splitter import DatasheetSplitter
    from src.ingestion.chunking.fine_chunker import FineGrainedChunker
    from src.ingestion.chunking.parent_child_chunker import ParentChildChunker
    from src.ingestion.chunking.semantic_chunker import SemanticChunker

    _REGISTRY.update({
        "datasheet": DatasheetSplitter,
        "fine": FineGrainedChunker,
        "coarse": CoarseGrainedChunker,
        "parent_child": ParentChildChunker,
        "semantic": SemanticChunker,
    })
    return _REGISTRY


def create_chunker(strategy: str | None = None, **kwargs: Any) -> BaseChunker:
    """Create a chunker instance for the given *strategy*.

    If *strategy* is ``None``, the value is read from
    ``settings.ingestion.chunking.strategy`` (default ``"datasheet"``).

    Extra *kwargs* override per-strategy ``params`` from settings.
    """
    from src.core.settings import load_settings

    try:
        settings = load_settings()
        ingestion_cfg = getattr(settings, "ingestion", None)
        chunking_cfg = getattr(ingestion_cfg, "chunking", None) if ingestion_cfg else None
    except Exception:
        chunking_cfg = None

    if strategy is None:
        strategy = getattr(chunking_cfg, "strategy", "datasheet") if chunking_cfg else "datasheet"

    assert strategy is not None
    registry = _ensure_registry()
    cls = registry.get(strategy)
    if cls is None:
        raise ValueError(f"Unknown chunking strategy: {strategy!r}. Available: {sorted(registry)}")

    # Merge per-strategy params from config with caller overrides
    params: dict[str, Any] = {}
    if chunking_cfg is not None:
        all_params = getattr(chunking_cfg, "params", None)
        if all_params and isinstance(all_params, dict):
            params.update(all_params.get(strategy, {}))
    params.update(kwargs)

    logger.debug("Creating chunker strategy=%s params=%s", strategy, params)
    return cls(**params)
