"""Reranker factory — select backend via settings.yaml ``rerank.provider``."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseReranker, NoneReranker

logger = logging.getLogger(__name__)


class RerankerFactory:
    """Registry-based factory for reranker backends."""

    _registry: dict[str, type[BaseReranker]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseReranker]) -> None:
        cls._registry[name] = backend_cls

    @classmethod
    def create(cls, config: dict[str, Any]) -> BaseReranker:
        rr_cfg = config.get("rerank", {})
        provider = rr_cfg.get("provider", "none")

        if provider not in cls._registry:
            raise ValueError(
                f"Unknown reranker provider '{provider}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_cls = cls._registry[provider]
        kwargs: dict[str, Any] = {}
        if "base_url" in rr_cfg:
            kwargs["base_url"] = rr_cfg["base_url"]
        if "timeout" in rr_cfg:
            kwargs["timeout"] = rr_cfg["timeout"]

        return backend_cls(**kwargs)


def _auto_register() -> None:
    from .bce_client import BCERerankerClient
    RerankerFactory.register("bce", BCERerankerClient)
    RerankerFactory.register("none", NoneReranker)


_auto_register()
