"""Unit tests for TokenBudget."""

from __future__ import annotations

import pytest

from src.agent.safety.token_budget import TokenBudget


@pytest.mark.unit
class TestTokenBudget:
    def test_initial_state(self) -> None:
        tb = TokenBudget(8192)
        assert tb.remaining == 8192
        assert tb.used == 0
        assert tb.exhausted is False

    def test_consume(self) -> None:
        tb = TokenBudget(100)
        tb.consume(30)
        assert tb.used == 30
        assert tb.remaining == 70

    def test_exhausted(self) -> None:
        tb = TokenBudget(100)
        tb.consume(100)
        assert tb.exhausted is True
        assert tb.remaining == 0

    def test_over_budget(self) -> None:
        tb = TokenBudget(100)
        tb.consume(150)
        assert tb.exhausted is True
        assert tb.remaining == 0

    def test_reset(self) -> None:
        tb = TokenBudget(100)
        tb.consume(50)
        tb.reset()
        assert tb.used == 0
        assert tb.remaining == 100

    def test_multiple_consumes(self) -> None:
        tb = TokenBudget(1000)
        tb.consume(100)
        tb.consume(200)
        tb.consume(300)
        assert tb.used == 600
        assert tb.remaining == 400
