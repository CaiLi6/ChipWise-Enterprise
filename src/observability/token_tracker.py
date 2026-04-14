"""Token usage tracker with Prometheus metrics (§2.11, §6A3)."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# Try to import prometheus_client; degrade gracefully if not available
try:
    from prometheus_client import Counter  # type: ignore[import-not-found]
    _token_counter = Counter(
        "chipwise_llm_tokens_total",
        "Total LLM token usage",
        ["model", "role", "token_type"],
    )
    _HAS_PROMETHEUS = True
except Exception:
    _token_counter = None  # type: ignore[assignment]
    _HAS_PROMETHEUS = False


class TokenTracker:
    """Track LLM token usage per model, role, and request type.

    Writes to Prometheus Counter and maintains an in-memory daily summary.
    """

    def __init__(self) -> None:
        # {date_str: {(model, role, token_type): count}}
        self._daily: dict[str, dict[tuple[str, str, str], int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def record(
        self,
        model: str,
        role: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_type: str = "query",
    ) -> None:
        """Record token usage for one LLM call.

        Args:
            model: Model identifier (e.g. "qwen3-35b").
            role: Model role ("primary" or "router").
            prompt_tokens: Number of prompt tokens consumed.
            completion_tokens: Number of completion tokens generated.
            request_type: Request category ("query", "ingestion", etc.).
        """
        today = str(date.today())

        for token_type, count in [("prompt", prompt_tokens), ("completion", completion_tokens)]:
            self._daily[today][(model, role, token_type)] += count
            if _HAS_PROMETHEUS and _token_counter is not None:
                try:
                    _token_counter.labels(
                        model=model, role=role, token_type=token_type
                    ).inc(count)
                except Exception:
                    logger.debug("Prometheus counter update failed", exc_info=True)

    def get_daily_summary(self, target_date: str | None = None) -> dict[str, Any]:
        """Return token consumption summary for a given date.

        Args:
            target_date: ISO date string (YYYY-MM-DD). Defaults to today.

        Returns:
            dict with keys "date", "by_model", "totals".
        """
        day = target_date or str(date.today())
        raw = self._daily.get(day, {})

        by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"prompt": 0, "completion": 0})
        total_prompt = 0
        total_completion = 0

        for (model, role, token_type), count in raw.items():
            key = f"{model}:{role}"
            by_model[key][token_type] += count
            if token_type == "prompt":
                total_prompt += count
            else:
                total_completion += count

        return {
            "date": day,
            "by_model": dict(by_model),
            "totals": {
                "prompt": total_prompt,
                "completion": total_completion,
                "total": total_prompt + total_completion,
            },
        }

    def get_weekly_summary(self) -> list[dict[str, Any]]:
        """Return daily summaries for the last 7 days."""
        from datetime import timedelta

        today = date.today()
        return [
            self.get_daily_summary(str(today - timedelta(days=i)))
            for i in range(6, -1, -1)
        ]

    def reset(self) -> None:
        """Clear all tracked data (for testing)."""
        self._daily.clear()


# Module-level singleton for use across request handlers
_tracker = TokenTracker()


def get_tracker() -> TokenTracker:
    """Return the global TokenTracker singleton."""
    return _tracker
