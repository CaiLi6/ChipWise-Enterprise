"""LM Studio setup helper: detect, verify, and configure LM Studio for ChipWise.

Usage:
    python scripts/setup_lmstudio.py              # check status
    python scripts/setup_lmstudio.py --verify      # verify models loaded
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass

logger = logging.getLogger("setup_lmstudio")

DEFAULT_BASE_URL = "http://localhost:1234/v1"


@dataclass
class ModelInfo:
    """Information about a loaded LM Studio model."""

    model_id: str
    owned_by: str = ""


def check_lmstudio(base_url: str = DEFAULT_BASE_URL) -> bool:
    """Check if LM Studio is running and responding at the given URL.

    Returns:
        True if LM Studio API is reachable, False otherwise.
    """
    try:
        import httpx

        resp = httpx.get(f"{base_url}/models", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def list_models(base_url: str = DEFAULT_BASE_URL) -> list[ModelInfo]:
    """List all models currently loaded in LM Studio.

    Returns:
        List of ModelInfo objects for loaded models.
    """
    try:
        import httpx

        resp = httpx.get(f"{base_url}/models", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = []
        for m in data.get("data", []):
            models.append(
                ModelInfo(
                    model_id=m.get("id", ""),
                    owned_by=m.get("owned_by", ""),
                )
            )
        return models
    except Exception as exc:
        logger.warning("Failed to list models: %s", exc)
        return []


def verify_chat_completion(
    model: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
) -> tuple[bool, float]:
    """Send a minimal chat completion request to verify model responds.

    Args:
        model: Model identifier to test.
        base_url: LM Studio API base URL.
        timeout: Max seconds to wait for response.

    Returns:
        (success, latency_seconds) tuple.
    """
    import time

    try:
        import httpx

        start = time.monotonic()
        resp = httpx.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Say hello in one word."}],
                "max_tokens": 16,
                "temperature": 0.0,
            },
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                return True, elapsed
        return False, elapsed
    except Exception as exc:
        logger.warning("Chat completion failed for %s: %s", model, exc)
        return False, 0.0


def generate_config(
    primary_model: str = "qwen3-35b-q5_k_m",
    router_model: str = "qwen3-1.7b-q5_k_m",
    port: int = 1234,
) -> dict:
    """Generate LM Studio configuration for ChipWise.

    Returns:
        Configuration dict suitable for settings.yaml llm section.
    """
    return {
        "llm": {
            "primary": {
                "provider": "openai_compatible",
                "base_url": f"http://localhost:{port}/v1",
                "model": primary_model,
                "api_key": "lm-studio",
            },
            "router": {
                "provider": "openai_compatible",
                "base_url": f"http://localhost:{port}/v1",
                "model": router_model,
                "api_key": "lm-studio",
            },
        }
    }


def main() -> int:
    """CLI entry point: check LM Studio status and optionally verify models."""
    import argparse

    parser = argparse.ArgumentParser(description="LM Studio setup helper")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="LM Studio base URL")
    parser.add_argument("--verify", action="store_true", help="Verify model chat completions")
    args = parser.parse_args()

    print(f"\nChecking LM Studio at {args.base_url} ...")
    if not check_lmstudio(args.base_url):
        print("✗ LM Studio is NOT reachable.")
        print("  Please start LM Studio and load models before running this script.")
        return 1

    print("✓ LM Studio is running.")

    models = list_models(args.base_url)
    if not models:
        print("✗ No models loaded.")
        return 1

    print(f"\nLoaded models ({len(models)}):")
    for m in models:
        print(f"  - {m.model_id}")

    if args.verify:
        print("\nVerifying chat completions ...")
        all_ok = True
        for m in models:
            ok, latency = verify_chat_completion(m.model_id, args.base_url)
            status = "✓" if ok else "✗"
            print(f"  {status} {m.model_id}: {'%.2f' % latency}s")
            if not ok:
                all_ok = False

        if not all_ok:
            print("\n✗ Some models failed verification.")
            return 1
        print("\n✓ All models verified successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
