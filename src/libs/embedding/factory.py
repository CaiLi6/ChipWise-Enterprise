"""Embedding factory — select backend via settings.yaml ``embedding.provider``."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseEmbedding

logger = logging.getLogger(__name__)


class EmbeddingFactory:
    """Registry-based factory for embedding backends."""

    _registry: dict[str, type[BaseEmbedding]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseEmbedding]) -> None:
        cls._registry[name] = backend_cls

    @classmethod
    def create(cls, config: dict[str, Any]) -> BaseEmbedding:
        emb_cfg = config.get("embedding", {})
        provider = emb_cfg.get("provider", "bgem3")

        if provider not in cls._registry:
            raise ValueError(
                f"Unknown embedding provider '{provider}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_cls = cls._registry[provider]
        kwargs: dict[str, Any] = {}
        if "base_url" in emb_cfg:
            kwargs["base_url"] = emb_cfg["base_url"]
        if "timeout" in emb_cfg:
            kwargs["timeout"] = emb_cfg["timeout"]

        return backend_cls(**kwargs)


def _auto_register() -> None:
    from .bgem3_client import BGEM3Client
    EmbeddingFactory.register("bgem3", BGEM3Client)


_auto_register()
