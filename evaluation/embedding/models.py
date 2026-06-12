"""Model registry + unified embedding runner for the benchmark.

All five dense models are loaded through a single backend (``sentence-transformers``)
so the comparison measures the *model*, not the loader. Each model carries its
official query/passage convention (prefix text and/or ST prompt/task kwargs).

The BGE-M3 hybrid (dense+sparse) reference uses ``FlagEmbedding`` and lives in
:mod:`evaluation.embedding.hybrid`, deliberately kept out of the apples-to-apples path.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    """Static, picklable description of a benchmark model and its conventions."""

    key: str
    hf_id: str
    dim: int
    trust_remote_code: bool = False
    # Literal text prepended to inputs (official retrieval conventions).
    query_prefix: str = ""
    passage_prefix: str = ""
    # Extra kwargs passed to SentenceTransformer.encode for query/passage.
    query_encode_kwargs: dict[str, Any] = field(default_factory=dict)
    passage_encode_kwargs: dict[str, Any] = field(default_factory=dict)
    max_len: int = 512
    normalize: bool = True
    notes: str = ""


# ── Registry (user-approved default set) ────────────────────────────────────
# Conventions sourced from each model's official card.
REGISTRY: dict[str, ModelSpec] = {
    "bge-m3": ModelSpec(
        key="bge-m3",
        hf_id="BAAI/bge-m3",
        dim=1024,
        query_prefix="",
        passage_prefix="",
        max_len=512,
        notes="Production baseline (dense path). No query/passage prefix.",
    ),
    "bge-large-zh": ModelSpec(
        key="bge-large-zh",
        hf_id="BAAI/bge-large-zh-v1.5",
        dim=1024,
        query_prefix="为这个句子生成表示以用于检索相关文章：",
        passage_prefix="",
        max_len=512,
        notes="Chinese retrieval instruction on the query side only.",
    ),
    "jina-v3": ModelSpec(
        key="jina-v3",
        hf_id="jinaai/jina-embeddings-v3",
        dim=1024,
        trust_remote_code=True,
        query_encode_kwargs={"task": "retrieval.query"},
        passage_encode_kwargs={"task": "retrieval.passage"},
        max_len=512,
        notes="Task-specific LoRA via encode(task=...); needs einops + remote code.",
    ),
    "qwen3-0.6b": ModelSpec(
        key="qwen3-0.6b",
        hf_id="Qwen/Qwen3-Embedding-0.6B",
        dim=1024,
        query_encode_kwargs={"prompt_name": "query"},
        passage_encode_kwargs={},
        max_len=512,
        notes="Instruct prompt on queries via ST prompt_name='query'; last-token pooling.",
    ),
    "e5-large": ModelSpec(
        key="e5-large",
        hf_id="intfloat/multilingual-e5-large",
        dim=1024,
        query_prefix="query: ",
        passage_prefix="passage: ",
        max_len=512,
        notes="Mandatory query:/passage: prefixes.",
    ),
}

DEFAULT_ORDER = ["bge-m3", "bge-large-zh", "jina-v3", "qwen3-0.6b", "e5-large"]


def apply_thread_limits(threads: int) -> None:
    """Pin BLAS / torch thread counts for reproducible speed numbers.

    Must be called *before* importing torch where possible (env vars), and again
    after import (torch.set_num_threads).
    """
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(var, str(threads))


@dataclass
class EncodeStats:
    """Per-encode bookkeeping for fairness auditing."""

    n_texts: int = 0
    truncated: int = 0
    nan_or_zero: int = 0

    @property
    def truncation_rate(self) -> float:
        return self.truncated / self.n_texts if self.n_texts else 0.0


class EmbeddingRunner:
    """Loads one model and produces L2-normalized dense vectors.

    Lazily imports torch / sentence-transformers so this module stays cheap to
    import in the parent (orchestrator) process. Intended to run inside a
    per-model subprocess for clean memory isolation.
    """

    def __init__(self, spec: ModelSpec, threads: int = 4, device: str | None = None) -> None:
        self.spec = spec
        self.threads = threads
        self._requested_device = device
        self.device: str = "cpu"
        self.dtype: str = "float32"
        self.revision: str = "unknown"
        self._model: Any = None
        self._tokenizer: Any = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    def load(self) -> None:
        apply_thread_limits(self.threads)
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(self.threads)

        if self._requested_device:
            self.device = self._requested_device
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        # fp16 only pays off on GPU; CPU matmul in fp16 is slow/unsupported.
        self.dtype = "float16" if self.device == "cuda" else "float32"
        model_kwargs: dict[str, Any] = {}
        if self.device == "cuda":
            model_kwargs["torch_dtype"] = torch.float16

        logger.info("Loading %s on %s (%s)", self.spec.hf_id, self.device, self.dtype)
        self._model = SentenceTransformer(
            self.spec.hf_id,
            trust_remote_code=self.spec.trust_remote_code,
            device=self.device,
            model_kwargs=model_kwargs or None,
        )
        try:
            self._model.max_seq_length = self.spec.max_len
        except Exception:  # noqa: BLE001 — some custom models manage their own limit
            logger.debug("Could not set max_seq_length on %s", self.spec.key)
        self._tokenizer = getattr(self._model, "tokenizer", None)
        self.revision = self._resolve_revision()

    def _resolve_revision(self) -> str:
        # Read the cached commit hash locally (instant, offline-safe) rather than
        # hitting the network, which is slow/flaky here.
        try:
            from huggingface_hub.constants import HF_HUB_CACHE

            org_name = self.spec.hf_id.replace("/", "--")
            ref = Path(HF_HUB_CACHE) / f"models--{org_name}" / "refs" / "main"
            if ref.exists():
                return ref.read_text().strip()[:40] or "unknown"
        except Exception:  # noqa: BLE001
            pass
        return "unknown"

    # ── encoding ───────────────────────────────────────────────────────────
    def _encode(
        self,
        texts: list[str],
        prefix: str,
        encode_kwargs: dict[str, Any],
        batch_size: int,
    ) -> tuple[Any, EncodeStats]:
        import numpy as np

        prepared = [prefix + t for t in texts] if prefix else list(texts)
        stats = EncodeStats(n_texts=len(texts), truncated=self._count_truncated(prepared))

        kwargs: dict[str, Any] = dict(
            batch_size=batch_size,
            normalize_embeddings=self.spec.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        kwargs.update(encode_kwargs)
        vecs = self._encode_with_fallback(prepared, kwargs)

        vecs = np.asarray(vecs, dtype=np.float32)
        bad = ~np.isfinite(vecs).all(axis=1) | (np.abs(vecs).sum(axis=1) == 0)
        stats.nan_or_zero = int(bad.sum())
        return vecs, stats

    def _encode_with_fallback(self, texts: list[str], kwargs: dict[str, Any]) -> Any:
        """Encode, retrying without model-specific kwargs the backend rejects."""
        try:
            return self._model.encode(texts, **kwargs)
        except TypeError as exc:
            for opt in ("task", "prompt_name"):
                if opt in kwargs:
                    logger.warning("encode() rejected %r for %s (%s); retrying without it",
                                   opt, self.spec.key, exc)
                    kwargs.pop(opt, None)
            return self._model.encode(texts, **kwargs)

    def encode_queries(self, texts: list[str], batch_size: int = 16) -> tuple[Any, EncodeStats]:
        return self._encode(texts, self.spec.query_prefix, dict(self.spec.query_encode_kwargs), batch_size)

    def encode_passages(self, texts: list[str], batch_size: int = 32) -> tuple[Any, EncodeStats]:
        return self._encode(texts, self.spec.passage_prefix, dict(self.spec.passage_encode_kwargs), batch_size)

    # ── helpers ────────────────────────────────────────────────────────────
    def _count_truncated(self, texts: list[str]) -> int:
        if self._tokenizer is None:
            return 0
        truncated = 0
        try:
            for t in texts:
                ids = self._tokenizer.encode(t, add_special_tokens=True)
                if len(ids) > self.spec.max_len:
                    truncated += 1
        except Exception:  # noqa: BLE001
            return 0
        return truncated
