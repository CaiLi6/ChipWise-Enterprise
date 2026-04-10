"""Watchdog filesystem monitor for auto-ingestion (§3C2)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 5
IGNORED_PATTERNS = {"~$", ".tmp", ".part", ".swp"}
ALLOWED_EXTENSIONS = {".pdf"}


class DatasheetWatchdog:
    """Monitor a directory for new PDF files and trigger Celery ingestion."""

    def __init__(self, watch_dir: str, celery_app: Any = None) -> None:
        self._watch_dir = Path(watch_dir)
        self._celery_app = celery_app
        self._pending: dict[str, float] = {}  # path → last_modified_time
        self._running = False

    def start(self) -> None:
        """Start the watchdog observer."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileCreatedEvent

            handler = _Handler(self)
            observer = Observer()
            observer.schedule(handler, str(self._watch_dir), recursive=True)
            observer.start()
            self._running = True
            logger.info("Watchdog monitoring: %s", self._watch_dir)
        except ImportError:
            logger.error("watchdog package not installed")

    def stop(self) -> None:
        self._running = False

    def on_file_created(self, file_path: str) -> None:
        """Handle a new file event (with debounce)."""
        path = Path(file_path)

        # Filter by extension
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return

        # Ignore temp files
        if any(pat in path.name for pat in IGNORED_PATTERNS):
            return

        # Debounce: record file and wait for it to stabilize
        self._pending[file_path] = time.time()

    def process_pending(self) -> list[str]:
        """Process files that have been stable for DEBOUNCE_SECONDS."""
        now = time.time()
        ready: list[str] = []

        for path, mtime in list(self._pending.items()):
            if now - mtime >= DEBOUNCE_SECONDS:
                ready.append(path)
                del self._pending[path]
                self._submit_ingestion(path)

        return ready

    def _submit_ingestion(self, file_path: str) -> None:
        """Submit file to Celery ingestion chain."""
        logger.info("Submitting %s for ingestion", file_path)
        try:
            if self._celery_app:
                from src.ingestion.tasks import create_ingestion_chain
                chain = create_ingestion_chain(
                    url=file_path,
                    manufacturer=self._detect_manufacturer(file_path),
                    priority=5,
                )
                chain.apply_async()
        except Exception:
            logger.exception("Failed to submit ingestion for %s", file_path)

    @staticmethod
    def _detect_manufacturer(file_path: str) -> str:
        """Guess manufacturer from directory name."""
        parts = Path(file_path).parts
        for part in parts:
            part_lower = part.lower()
            if part_lower in ("st", "ti", "nxp", "infineon", "microchip"):
                return part
        return "unknown"


class _Handler:
    """Watchdog event handler adapter."""

    def __init__(self, watchdog: DatasheetWatchdog) -> None:
        self._watchdog = watchdog

    def on_created(self, event: Any) -> None:
        if not event.is_directory:
            self._watchdog.on_file_created(event.src_path)

    def dispatch(self, event: Any) -> None:
        if hasattr(event, "is_directory") and not event.is_directory:
            if event.event_type == "created":
                self.on_created(event)
