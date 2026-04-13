"""Auto-validate Locust load test results against SLA targets (§6C1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.load


def _load_stats(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        pytest.skip(f"Load test stats file not found: {path}")
    with open(p) as f:
        return json.load(f)


@pytest.mark.unit
class TestLoadSLATargets:
    """Validate SLA targets when load test results are available."""

    def test_stats_file_is_present_or_skip(self) -> None:
        """This test passes trivially; real validation requires a stats file."""
        stats_path = os.environ.get("LOAD_STATS_FILE", "tests/load/locust_stats.json")
        if not Path(stats_path).exists():
            pytest.skip("Load test not run yet. Execute locust first.")

    def test_p95_below_8s(self) -> None:
        stats_path = os.environ.get("LOAD_STATS_FILE", "tests/load/locust_stats.json")
        stats = _load_stats(stats_path)
        for entry in stats.get("stats", []):
            p95 = entry.get("response_time_percentile_0.95", 0)
            assert p95 < 8000, (
                f"{entry['name']}: P95={p95}ms exceeds 8s SLA"
            )

    def test_no_5xx_errors(self) -> None:
        stats_path = os.environ.get("LOAD_STATS_FILE", "tests/load/locust_stats.json")
        stats = _load_stats(stats_path)
        for entry in stats.get("stats", []):
            failures = entry.get("num_failures", 0)
            assert failures == 0, (
                f"{entry['name']}: {failures} failures detected"
            )

    def test_failure_rate_zero(self) -> None:
        stats_path = os.environ.get("LOAD_STATS_FILE", "tests/load/locust_stats.json")
        stats = _load_stats(stats_path)
        total_requests = sum(e.get("num_requests", 0) for e in stats.get("stats", []))
        total_failures = sum(e.get("num_failures", 0) for e in stats.get("stats", []))
        if total_requests > 0:
            failure_rate = total_failures / total_requests
            assert failure_rate == 0.0, f"Failure rate {failure_rate:.2%} must be 0%"
