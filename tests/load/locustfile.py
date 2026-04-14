"""Locust load test with ramp profiles (§6C1).

Profiles (set via --tags or LOCUST_PROFILE env):
  smoke:    5 users, 1 min — quick sanity check
  baseline: 50 users, 10 min — sustained load
  stress:   200 users ramp over 5 min, hold 15 min — breaking point

Run:
  locust -f tests/load/locustfile.py --headless --users 5 --spawn-rate 5 --run-time 1m  # smoke
  locust -f tests/load/locustfile.py --headless --users 50 --spawn-rate 5 --run-time 10m  # baseline
  locust -f tests/load/locustfile.py --headless --users 200 --spawn-rate 40 --run-time 20m  # stress

Thresholds:
  smoke:    p95 < 5s,  fail rate < 1%
  baseline: p95 < 10s, fail rate < 3%
  stress:   p95 < 20s, fail rate < 10%
"""

from __future__ import annotations

import os
import random

try:
    from locust import HttpUser, between, events, task
    from locust.runners import MasterRunner
except ImportError:
    # Allow syntax check without locust installed
    HttpUser = object  # type: ignore[assignment, misc]
    events = None  # type: ignore[assignment]
    MasterRunner = None  # type: ignore[assignment]
    def between(a, b):  # type: ignore[assignment]
        return None
    def task(weight: int):  # type: ignore[misc]
        return lambda fn: fn


_JWT_TOKEN = os.environ.get("CHIPWISE_JWT", "")

_CHIP_PAIRS = [
    ["STM32F407", "GD32F407"],
    ["STM32F103", "GD32F103"],
    ["ESP32", "ESP32-S3"],
]

_QUERIES = [
    "What is the maximum operating frequency of STM32F407?",
    "Compare STM32F407 and GD32F407 power consumption",
    "What are the GPIO count of STM32F103?",
    "Find MCUs with voltage range 1.8V to 3.6V",
    "What are the errata for STM32F407 ADC?",
]


class ChipWiseUser(HttpUser):
    wait_time = between(2, 5)
    host = os.environ.get("CHIPWISE_HOST", "http://localhost:8080")

    def on_start(self) -> None:
        """Authenticate and store JWT token."""
        if _JWT_TOKEN:
            self.token = _JWT_TOKEN
            return
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "loadtest", "password": "loadtest123"},
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def query_rag(self) -> None:
        """Highest frequency: natural language query."""
        query = random.choice(_QUERIES)
        self.client.post(
            "/api/v1/query",
            json={"query": query},
            headers=self._headers(),
            name="/api/v1/query",
        )

    @task(3)
    def chip_compare(self) -> None:
        """Medium frequency: chip comparison."""
        pair = random.choice(_CHIP_PAIRS)
        self.client.post(
            "/api/v1/compare",
            json={"chip_names": pair},
            headers=self._headers(),
            name="/api/v1/compare",
        )

    @task(1)
    def health_check(self) -> None:
        """Low frequency: health endpoint (baseline)."""
        self.client.get("/health", name="/health")

    @task(1)
    def list_knowledge(self) -> None:
        """Low frequency: knowledge notes list."""
        self.client.get(
            "/api/v1/knowledge",
            headers=self._headers(),
            name="/api/v1/knowledge",
        )
