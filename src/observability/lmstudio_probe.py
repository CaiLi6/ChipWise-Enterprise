"""Background periodic health probe for LM Studio models.

Started as an ``asyncio`` task during FastAPI startup.  Every
``interval`` seconds it pings ``GET /v1/models`` on LM Studio and
caches the result in ``app.state.lmstudio_status`` so that the
``/readiness`` endpoint and query router can read it without
blocking on a synchronous HTTP call.

Usage (in ``src/api/main.py``)::

    from src.observability.lmstudio_probe import start_lmstudio_probe
    # inside create_app() or lifespan:
    start_lmstudio_probe(app)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("chipwise.lmstudio_probe")

_DEFAULT_INTERVAL = 15  # seconds


async def _probe_once(llm_cfg: Any) -> dict[str, Any]:
    """Check if a specific LM Studio model is loaded. Returns serializable dict."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(
                f"{llm_cfg.base_url}/models",
                headers={"Authorization": f"Bearer {llm_cfg.api_key}"},
            )
        if resp.status_code != 200:
            return {"healthy": False, "message": f"HTTP {resp.status_code}"}
        models = [m["id"] for m in resp.json().get("data", [])]
        if llm_cfg.model not in models:
            return {
                "healthy": False,
                "message": f"Model '{llm_cfg.model}' not loaded; available: {models[:3]}",
            }
        return {"healthy": True, "message": "OK"}
    except Exception as exc:
        return {"healthy": False, "message": str(exc)}


async def _probe_loop(app: Any, interval: int = _DEFAULT_INTERVAL) -> None:
    """Infinite loop that probes LM Studio every ``interval`` seconds."""
    while True:
        try:
            settings = app.state.settings
            primary = await _probe_once(settings.llm.primary)
            router = await _probe_once(settings.llm.router)

            app.state.lmstudio_status = {
                "lmstudio_primary": primary,
                "lmstudio_router": router,
                "checked_at": time.time(),
            }

            if not primary["healthy"] or not router["healthy"]:
                logger.warning(
                    "LM Studio probe: primary=%s router=%s",
                    primary["message"], router["message"],
                )
        except asyncio.CancelledError:
            logger.info("LM Studio probe stopped.")
            return
        except Exception:
            logger.exception("LM Studio probe unexpected error")

        await asyncio.sleep(interval)


def start_lmstudio_probe(app: Any, interval: int = _DEFAULT_INTERVAL) -> None:
    """Start the background probe task. Safe to call during app startup."""
    # Initialize with unknown status so readiness doesn't crash
    app.state.lmstudio_status = {
        "lmstudio_primary": {"healthy": False, "message": "probe not yet run"},
        "lmstudio_router": {"healthy": False, "message": "probe not yet run"},
        "checked_at": 0,
    }
    task = asyncio.create_task(_probe_loop(app, interval))
    # Store task reference to prevent GC
    app.state._lmstudio_probe_task = task
    logger.info("LM Studio background probe started (interval=%ds)", interval)
