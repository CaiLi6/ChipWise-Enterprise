"""Shared helpers: raw config loading + a synchronous LLM wrapper.

The production factories consume a raw settings *dict* (with env resolution),
not the pydantic ``Settings`` object, so we reload the YAML the same way
``src.core.settings.load_settings`` does.
"""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Structured extraction/judging prefers an instruction-tuned model that emits
# clean JSON with no reasoning tokens. Override via EMBED_EVAL_LLM.
DEFAULT_EVAL_MODEL = os.environ.get("EMBED_EVAL_LLM", "gemma-4-31b-it")


@lru_cache(maxsize=1)
def load_raw_config(path: str = "config/settings.yaml") -> dict[str, Any]:
    """Load settings.yaml as a raw dict with env placeholders/overrides applied."""
    import yaml
    from src.core.settings import _apply_env_overrides, _resolve_env_placeholders

    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    raw = _resolve_env_placeholders(raw)
    raw = _apply_env_overrides(raw)
    return raw


def _extract_reasoning(raw: dict[str, Any]) -> str:
    """Fallback for reasoning models: pull text out of reasoning_content."""
    try:
        msg = raw["choices"][0]["message"]
        return msg.get("reasoning_content") or msg.get("content") or ""
    except (KeyError, IndexError, TypeError):
        return ""


def llm_generate(
    prompt: str,
    role: str = "primary",
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.1,
    no_think: bool = False,
) -> str:
    """Synchronously call an LLM and return its text.

    By default routes to :data:`DEFAULT_EVAL_MODEL` (an instruction-tuned model
    that returns clean JSON). Pass ``model=""`` to use the configured ``role``
    model instead. Qwen3-style reasoning models otherwise spend the token budget
    on a ``<think>`` block and return empty ``content``; ``no_think`` adds the
    ``/no_think`` switch and a ``reasoning_content`` fallback guards either way.
    """
    from src.libs.llm.factory import LLMFactory

    cfg = load_raw_config()
    chosen = DEFAULT_EVAL_MODEL if model is None else model
    if chosen:
        base = cfg.get("llm", {}).get(role, {})
        client_cls = LLMFactory._registry[base.get("provider", "openai_compatible")]
        llm = client_cls(
            base_url=base.get("base_url", "http://localhost:1234/v1"),
            model=chosen,
            api_key=base.get("api_key", "lm-studio"),
            timeout=base.get("timeout", 180),
        )
    else:
        llm = LLMFactory.create(cfg, role=role)
    if no_think and "/no_think" not in prompt:
        prompt = f"{prompt}\n/no_think"

    async def _run() -> str:
        resp = await llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
        text = (resp.text or "").strip()
        if not text:
            text = _extract_reasoning(resp.raw).strip()
        # Strip any leftover <think>…</think> wrapper.
        if "</think>" in text:
            text = text.rsplit("</think>", 1)[-1].strip()
        return text

    return asyncio.run(_run())
