"""Prompt-budgeted retrieval from short-term conversation memory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.core.conversation_manager import ConversationContext

_TOKEN = re.compile(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}")


@dataclass
class MemoryRetrievalConfig:
    prompt_budget_chars: int = 6000
    recent_turns_always: int = 4
    min_relevance_score: float = 0.12


class MemoryRetriever:
    """Select memory messages under a character budget."""

    def __init__(self, config: MemoryRetrievalConfig | None = None) -> None:
        self._config = config or MemoryRetrievalConfig()

    def select_messages(
        self,
        context: ConversationContext,
        query: str,
    ) -> list[dict[str, str]]:
        budget = max(0, self._config.prompt_budget_chars)
        messages: list[dict[str, str]] = []
        used = 0

        summary = context.summary.strip()
        if summary and budget:
            content = "Conversation summary (compressed memory):\n" + summary
            content = content[:budget]
            messages.append({"role": "system", "content": content})
            used += len(content)

        remaining = max(0, budget - used)
        if remaining <= 0:
            return messages

        pinned = self._format_pinned(context.pinned, remaining)
        if pinned:
            messages.append({"role": "system", "content": pinned})
            remaining -= len(pinned)
            if remaining <= 0:
                return messages

        selected = self._select_turns(context.turns, query)
        for turn in selected:
            content = str(turn.get("content", "")).strip()
            role = str(turn.get("role", "user"))
            if not content or role not in {"user", "assistant", "system"}:
                continue
            if len(content) > remaining:
                content = content[:remaining]
            if not content:
                break
            messages.append({"role": role, "content": content})
            remaining -= len(content)
            if remaining <= 0:
                break
        return messages

    def _select_turns(self, turns: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        if not turns:
            return []
        query_terms = self._terms(query)
        always_start = max(0, len(turns) - self._config.recent_turns_always)
        scored: list[tuple[int, float, dict[str, Any]]] = []
        for idx, turn in enumerate(turns):
            score = self._score_turn(turn, query_terms)
            if idx >= always_start:
                score = max(score, self._config.min_relevance_score + 0.1)
            if score >= self._config.min_relevance_score:
                scored.append((idx, score, turn))
        scored.sort(key=lambda item: item[0])
        return [turn for _idx, _score, turn in scored]

    def _score_turn(self, turn: dict[str, Any], query_terms: set[str]) -> float:
        metadata = turn.get("metadata") if isinstance(turn.get("metadata"), dict) else {}
        importance = float(metadata.get("importance") or 0.0)
        content_terms = self._terms(str(turn.get("content", "")))
        overlap = len(query_terms & content_terms) / max(1, len(query_terms))
        entity_bonus = 0.0
        chips = ((metadata.get("entities") or {}).get("chips") or [])
        if chips and any(str(chip).lower() in query_terms for chip in chips):
            entity_bonus = 0.3
        return min(1.0, importance * 0.55 + overlap * 0.35 + entity_bonus)

    @staticmethod
    def _format_pinned(pinned: list[dict[str, Any]], budget: int) -> str:
        if not pinned or budget <= 0:
            return ""
        lines = ["Pinned conversation memory (must preserve):"]
        for item in pinned:
            content = str(item.get("content", "")).strip()
            if content:
                lines.append(f"- {content[:300]}")
        text = "\n".join(lines)
        return text[:budget] if len(lines) > 1 else ""

    @staticmethod
    def _terms(text: str) -> set[str]:
        return {m.group(0).lower() for m in _TOKEN.finditer(text)}
