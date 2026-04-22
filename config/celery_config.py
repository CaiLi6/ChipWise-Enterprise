"""Celery configuration for ChipWise ingestion pipeline (§3B1)."""

from __future__ import annotations

import os
from urllib.parse import quote

_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
_REDIS_PW = os.environ.get("REDIS_PASSWORD", "")
_REDIS_AUTH = f":{quote(_REDIS_PW)}@" if _REDIS_PW else ""

broker_url = f"redis://{_REDIS_AUTH}{_REDIS_HOST}:{_REDIS_PORT}/0"
result_backend = f"redis://{_REDIS_AUTH}{_REDIS_HOST}:{_REDIS_PORT}/1"

# Serialization
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# Reliability
task_acks_late = True
worker_prefetch_multiplier = 1

# Timeouts
task_time_limit = 600       # 10 min hard limit
task_soft_time_limit = 540  # 9 min soft limit

# Concurrency
worker_concurrency = 3

# Task routing
task_routes = {
    "src.ingestion.tasks.extract_tables": {"queue": "heavy"},
    "src.ingestion.tasks.embed_chunks": {"queue": "embedding"},
    "src.ingestion.tasks.crawl_manufacturer": {"queue": "crawler"},
}

# Retry defaults
task_default_retry_delay = 5
task_max_retries = 3

# Result expiration
result_expires = 86400  # 24 hours
