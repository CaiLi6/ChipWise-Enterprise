"""Token budget controller for Agent iterations (§4.8.1)."""

from __future__ import annotations


class TokenBudget:
    """Track token consumption across Agent ReAct iterations.

    When the budget is exhausted the orchestrator must produce a
    final answer immediately instead of continuing the loop.
    """

    def __init__(self, max_tokens: int = 8192) -> None:
        self._max = max_tokens
        self._used = 0

    def consume(self, tokens: int) -> None:
        self._used += tokens

    @property
    def remaining(self) -> int:
        return max(0, self._max - self._used)

    @property
    def exhausted(self) -> bool:
        return self._used >= self._max

    @property
    def used(self) -> int:
        return self._used

    def reset(self) -> None:
        self._used = 0
