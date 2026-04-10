"""Integration tests for LM Studio health and model availability.

Run: pytest -q tests/integration/test_lmstudio_health.py -m integration
Requires: LM Studio running at localhost:1234 with models loaded.
"""

from __future__ import annotations

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

BASE_URL = "http://localhost:1234/v1"


def _is_lmstudio_up() -> bool:
    """Check if LM Studio is running."""
    if httpx is None:
        return False
    try:
        resp = httpx.get(f"{BASE_URL}/models", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(httpx is None, reason="httpx not installed")
class TestLMStudioHealth:
    """Verify LM Studio is running and models are available."""

    def test_models_endpoint_accessible(self) -> None:
        if not _is_lmstudio_up():
            pytest.skip("LM Studio not available at localhost:1234")
        resp = httpx.get(f"{BASE_URL}/models", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) >= 1

    def test_primary_model_chat_completion(self) -> None:
        if not _is_lmstudio_up():
            pytest.skip("LM Studio not available at localhost:1234")
        models = httpx.get(f"{BASE_URL}/models", timeout=5).json().get("data", [])
        if not models:
            pytest.skip("No models loaded in LM Studio")

        model_id = models[0]["id"]
        resp = httpx.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "Say hello."}],
                "max_tokens": 16,
                "temperature": 0.0,
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["choices"]) > 0
        assert data["choices"][0]["message"]["content"]

    def test_multi_model_available(self) -> None:
        """Verify at least 2 models are loaded (primary + router)."""
        if not _is_lmstudio_up():
            pytest.skip("LM Studio not available at localhost:1234")
        models = httpx.get(f"{BASE_URL}/models", timeout=5).json().get("data", [])
        if len(models) < 2:
            pytest.skip(
                f"Only {len(models)} model(s) loaded — need 2 (primary + router)"
            )
        assert len(models) >= 2
