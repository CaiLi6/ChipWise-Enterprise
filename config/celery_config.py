"""Celery configuration for ChipWise ingestion pipeline (§3B1)."""

from __future__ import annotations

# Broker & backend
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/1"

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
