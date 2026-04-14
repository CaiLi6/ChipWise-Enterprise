"""Unit tests for TokenTracker (§2.11, §6A3)."""

from __future__ import annotations

from datetime import date

import pytest
from src.observability.token_tracker import TokenTracker


@pytest.fixture
def tracker() -> TokenTracker:
    t = TokenTracker()
    t.reset()
    return t


@pytest.mark.unit
class TestTokenTrackerRecord:
    def test_record_increments_daily_counts(self, tracker: TokenTracker) -> None:
        tracker.record("qwen3-35b", "primary", prompt_tokens=100, completion_tokens=50)
        summary = tracker.get_daily_summary()
        assert summary["totals"]["prompt"] == 100
        assert summary["totals"]["completion"] == 50
        assert summary["totals"]["total"] == 150

    def test_record_multiple_calls_accumulate(self, tracker: TokenTracker) -> None:
        tracker.record("qwen3-35b", "primary", 100, 50)
        tracker.record("qwen3-35b", "primary", 200, 80)
        summary = tracker.get_daily_summary()
        assert summary["totals"]["prompt"] == 300
        assert summary["totals"]["completion"] == 130

    def test_record_different_models_tracked_separately(self, tracker: TokenTracker) -> None:
        tracker.record("qwen3-35b", "primary", 100, 50)
        tracker.record("qwen3-1.7b", "router", 10, 5)
        summary = tracker.get_daily_summary()
        assert "qwen3-35b:primary" in summary["by_model"]
        assert "qwen3-1.7b:router" in summary["by_model"]

    def test_record_zero_tokens_does_not_fail(self, tracker: TokenTracker) -> None:
        tracker.record("model", "role", 0, 0)
        summary = tracker.get_daily_summary()
        assert summary["totals"]["total"] == 0


@pytest.mark.unit
class TestTokenTrackerDailySummary:
    def test_summary_returns_today_by_default(self, tracker: TokenTracker) -> None:
        tracker.record("m", "r", 100, 50)
        summary = tracker.get_daily_summary()
        assert summary["date"] == str(date.today())

    def test_summary_for_specific_date(self, tracker: TokenTracker) -> None:
        summary = tracker.get_daily_summary("2026-01-01")
        assert summary["date"] == "2026-01-01"
        assert summary["totals"]["total"] == 0

    def test_summary_structure(self, tracker: TokenTracker) -> None:
        tracker.record("m", "r", 10, 5)
        summary = tracker.get_daily_summary()
        assert "date" in summary
        assert "by_model" in summary
        assert "totals" in summary
        assert "prompt" in summary["totals"]
        assert "completion" in summary["totals"]
        assert "total" in summary["totals"]


@pytest.mark.unit
class TestTokenTrackerWeeklySummary:
    def test_weekly_summary_returns_7_days(self, tracker: TokenTracker) -> None:
        weekly = tracker.get_weekly_summary()
        assert len(weekly) == 7

    def test_weekly_summary_ordered_oldest_first(self, tracker: TokenTracker) -> None:
        weekly = tracker.get_weekly_summary()
        dates = [w["date"] for w in weekly]
        assert dates == sorted(dates)


@pytest.mark.unit
class TestTokenTrackerReset:
    def test_reset_clears_all_data(self, tracker: TokenTracker) -> None:
        tracker.record("m", "r", 100, 50)
        tracker.reset()
        summary = tracker.get_daily_summary()
        assert summary["totals"]["total"] == 0


@pytest.mark.unit
class TestGetTracker:
    def test_get_tracker_returns_singleton(self) -> None:
        from src.observability.token_tracker import get_tracker
        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2
