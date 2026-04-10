"""LLM factory — select backend via settings.yaml ``llm.primary/router``."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseLLM

logger = logging.getLogger(__name__)


class LLMFactory:
    """Registry-based factory for LLM backends.

    Supports creating separate client instances for ``primary`` (35B reasoning)
    and ``router`` (1.7B lightweight) roles.
    """

    _registry: dict[str, type[BaseLLM]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type[BaseLLM]) -> None:
        cls._registry[name] = backend_cls

    @classmethod
    def create(cls, config: dict[str, Any], role: str = "primary") -> BaseLLM:
        """Create an LLM client for the given role.

        Parameters
        ----------
        config : dict
            Full settings dict. Reads from ``config["llm"][role]``.
        role : str
            ``"primary"`` for main reasoning model, ``"router"`` for lightweight routing.
        """
        llm_cfg = config.get("llm", {})
        role_cfg = llm_cfg.get(role, {})
        provider = role_cfg.get("provider", "openai_compatible")

        if provider not in cls._registry:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_cls = cls._registry[provider]
        kwargs: dict[str, Any] = {}
        if "base_url" in role_cfg:
            kwargs["base_url"] = role_cfg["base_url"]
        if "model" in role_cfg:
            kwargs["model"] = role_cfg["model"]
        if "api_key" in role_cfg:
            kwargs["api_key"] = role_cfg["api_key"]
        if "timeout" in role_cfg:
            kwargs["timeout"] = role_cfg["timeout"]

        return backend_cls(**kwargs)


def _auto_register() -> None:
    from .lmstudio_client import LMStudioClient
    LLMFactory.register("openai_compatible", LMStudioClient)


_auto_register()
