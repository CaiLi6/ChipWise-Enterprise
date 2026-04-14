"""BCE reranker client — calls the :8002 microservice (§2.3)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import BaseReranker, RerankResult

logger = logging.getLogger(__name__)


class BCERerankerClient(BaseReranker):
    """HTTP client for the bce-reranker microservice.

    Sends ``POST /rerank`` and parses scored results.
    Retries up to 3 times with exponential backoff (0.5–10 s).
    """

    def __init__(self, base_url: str = "http://localhost:8002", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, ConnectionError)),
        reraise=True,
    )
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        payload: dict[str, Any] = {
            "query": query,
            "documents": documents,
            "top_k": top_k,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/rerank", json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append(RerankResult(
                index=item["index"],
                score=item["score"],
                text=item.get("text", documents[item["index"]] if item["index"] < len(documents) else ""),
            ))

        # Ensure descending score order
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
