"""Task progress API + WebSocket push (§3B5)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Injected at app startup
_redis = None


def set_redis(redis: Any) -> None:
    global _redis
    _redis = redis


@router.get("/{task_id}")
async def get_task_progress(task_id: str) -> dict[str, Any]:
    """Poll task progress from Redis."""
    if _redis is None:
        raise HTTPException(503, "Redis not available")

    key = f"task:progress:{task_id}"
    data = await _redis.hgetall(key)
    if not data:
        raise HTTPException(404, "Task not found")

    return {
        "task_id": task_id,
        "status": data.get("status", "unknown"),
        "progress": int(data.get("progress", 0)),
        "stage": data.get("stage", ""),
        "message": data.get("message", ""),
    }


@router.websocket("/{task_id}/ws")
async def task_progress_ws(websocket: WebSocket, task_id: str) -> None:
    """Stream task progress via WebSocket until completion."""
    await websocket.accept()

    if _redis is None:
        await websocket.send_json({"error": "Redis not available"})
        await websocket.close()
        return

    key = f"task:progress:{task_id}"
    last_progress = -1

    try:
        while True:
            data = await _redis.hgetall(key)
            if not data:
                await websocket.send_json({"error": "Task not found"})
                await websocket.close()
                return

            progress = int(data.get("progress", 0))
            status = data.get("status", "unknown")

            if progress != last_progress:
                await websocket.send_json({
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "stage": data.get("stage", ""),
                    "message": data.get("message", ""),
                })
                last_progress = progress

            if status in ("completed", "failed"):
                await websocket.close()
                return

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for task %s", task_id)
