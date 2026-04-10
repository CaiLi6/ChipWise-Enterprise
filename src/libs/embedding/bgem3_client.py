"""BGE-M3 embedding client — calls the :8001 microservice (§2.3, §4.7)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseEmbedding, EmbeddingResult

logger = logging.getLogger(__name__)


class BGEM3Client(BaseEmbedding):
    """HTTP client for the BGE-M3 embedding microservice.

    Sends ``POST /encode`` and parses dense + sparse vectors from the response.
    Retries up to 3 times with exponential backoff (0.5–10 s).
    """

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, ConnectionError)),
        reraise=True,
    )
    async def encode(
        self,
        texts: list[str],
        return_sparse: bool = True,
    ) -> EmbeddingResult:
        payload: dict[str, Any] = {"texts": texts, "return_sparse": return_sparse}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/encode", json=payload)
            resp.raise_for_status()
            data = resp.json()

        dense = data.get("dense", [])
        sparse = data.get("sparse", [])
        # Convert sparse from list-of-dicts with string keys to int keys
        sparse_parsed: list[dict[int, float]] = []
        for s in sparse:
            if isinstance(s, dict):
                sparse_parsed.append({int(k): float(v) for k, v in s.items()})
            else:
                sparse_parsed.append({})

        dimensions = len(dense[0]) if dense else 0
        return EmbeddingResult(dense=dense, sparse=sparse_parsed, dimensions=dimensions)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
