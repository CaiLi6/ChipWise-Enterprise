"""VectorStore factory — select backend via settings.yaml ``vector_store.backend``."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Registry-based factory for vector store backends."""

    _registry: dict[str, type[BaseVectorStore]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseVectorStore]) -> None:
        cls._registry[name] = backend_cls
        logger.debug("Registered vector store backend: %s", name)

    @classmethod
    def create(cls, config: dict[str, Any]) -> BaseVectorStore:
        """Instantiate a vector store from config.

        Parameters
        ----------
        config : dict
            Expects ``{"vector_store": {"backend": "milvus", "host": "...", ...}}``.
        """
        vs_cfg = config.get("vector_store", {})
        backend = vs_cfg.get("backend", "milvus")

        if backend not in cls._registry:
            raise ValueError(
                f"Unknown vector store backend '{backend}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_cls = cls._registry[backend]
        init_kwargs: dict[str, Any] = {}
        if "host" in vs_cfg:
            init_kwargs["host"] = vs_cfg["host"]
        if "port" in vs_cfg:
            init_kwargs["port"] = vs_cfg["port"]
        if "default_collection" in vs_cfg:
            init_kwargs["default_collection"] = vs_cfg["default_collection"]

        return backend_cls(**init_kwargs)


def _auto_register() -> None:
    """Register built-in backends (lazy import to avoid hard dep on pymilvus)."""
    try:
        from .milvus_store import MilvusStore

        VectorStoreFactory.register("milvus", MilvusStore)
    except ImportError:
        logger.debug("pymilvus not available; MilvusStore not registered")


_auto_register()
