"""Unit tests for Celery config and tasks (§3B1-3B4)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import config.celery_config as cfg


@pytest.mark.unit
class TestCeleryConfig:
    def test_broker_url(self) -> None:
        assert "redis://" in cfg.broker_url

    def test_result_backend(self) -> None:
        assert "redis://" in cfg.result_backend

    def test_acks_late(self) -> None:
        assert cfg.task_acks_late is True

    def test_prefetch_multiplier(self) -> None:
        assert cfg.worker_prefetch_multiplier == 1

    def test_task_routes_heavy(self) -> None:
        assert cfg.task_routes["src.ingestion.tasks.extract_tables"]["queue"] == "heavy"

    def test_task_routes_embedding(self) -> None:
        assert cfg.task_routes["src.ingestion.tasks.embed_chunks"]["queue"] == "embedding"

    def test_task_routes_crawler(self) -> None:
        assert cfg.task_routes["src.ingestion.tasks.crawl_manufacturer"]["queue"] == "crawler"

    def test_time_limit(self) -> None:
        assert cfg.task_time_limit == 600
        assert cfg.task_soft_time_limit == 540
