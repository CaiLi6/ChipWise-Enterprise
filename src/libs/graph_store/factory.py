"""GraphStore factory — select backend via settings.yaml ``graph_store.backend``."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGraphStore

logger = logging.getLogger(__name__)


class GraphStoreFactory:
    """Registry-based factory for graph store backends."""

    _registry: dict[str, type[BaseGraphStore]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseGraphStore]) -> None:
        cls._registry[name] = backend_cls
        logger.debug("Registered graph store backend: %s", name)

    @classmethod
    def create(cls, config: dict[str, Any]) -> BaseGraphStore:
        """Instantiate a graph store from config.

        Parameters
        ----------
        config : dict
            Expects ``{"graph_store": {"backend": "kuzu", "db_path": "...", ...}}``.
        """
        gs_cfg = config.get("graph_store", {})
        backend = gs_cfg.get("backend", "kuzu")

        if backend not in cls._registry:
            raise ValueError(
                f"Unknown graph store backend '{backend}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_cls = cls._registry[backend]
        init_kwargs: dict[str, Any] = {}
        if "db_path" in gs_cfg:
            init_kwargs["db_path"] = gs_cfg["db_path"]
        if "read_only" in gs_cfg:
            init_kwargs["read_only"] = gs_cfg["read_only"]

        return backend_cls(**init_kwargs)


def _auto_register() -> None:
    """Register built-in backends."""
    from .kuzu_store import KuzuGraphStore  # noqa: F811

    GraphStoreFactory.register("kuzu", KuzuGraphStore)


_auto_register()
