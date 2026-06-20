"""ConversationManager — Redis-backed multi-turn session memory (§2D1).

The current payload is versioned so older list-only sessions can be migrated
without losing existing browser sessions:

```
{
  "version": 2,
  "summary": "... compressed older turns ...",
  "turns": [{"role": "user", "content": "...", "created_at": 1710000000.0}],
  "entities": {"chips": ["STM32F407"]},
  "updated_at": 1710000000.0
}
```
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.memory_scorer import MemoryImportanceScorer

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 minutes
MAX_TURNS = 10
SUMMARY_MAX_CHARS = 2000
PAYLOAD_VERSION = 2

_PART_NUMBER = re.compile(r"\b([A-Z][A-Z0-9\-]{3,19}\d[A-Z0-9\-]*)\b")


@dataclass
class ConversationContext:
    """Loaded short-term memory for one user/session."""

    summary: str = ""
    turns: list[dict[str, Any]] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)

    def to_messages(self) -> list[dict[str, str]]:
        """Return prompt-ready messages: compressed summary, then recent turns."""
        messages: list[dict[str, str]] = []
        if self.summary.strip():
            messages.append({
                "role": "system",
                "content": "Conversation summary (compressed memory):\n" + self.summary.strip(),
            })
        messages.extend(
            {"role": turn["role"], "content": turn["content"]}
            for turn in self.turns
            if turn.get("role") in {"user", "assistant", "system"} and turn.get("content")
        )
        return messages


class ConversationManager:
    """Manages per-user conversation history in Redis.

    Key format: ``session:{user_id}:{session_id}``.
    Auto-compresses old turns into a bounded summary and refreshes TTL on writes.
    """

    def __init__(
        self,
        redis: Any,
        *,
        session_ttl: int = SESSION_TTL,
        max_turns: int = MAX_TURNS,
        compression_threshold: int | None = None,
        summary_max_chars: int = SUMMARY_MAX_CHARS,
        summarizer: Any | None = None,
        scorer: MemoryImportanceScorer | None = None,
    ) -> None:
        self._redis = redis
        self._session_ttl = session_ttl
        self._max_turns = max_turns
        self._compression_threshold = compression_threshold or max_turns
        self._summary_max_chars = summary_max_chars
        self._summarizer = summarizer
        self._scorer = scorer or MemoryImportanceScorer()

    def _key(self, user_id: int | str, session_id: str) -> str:
        return f"session:{user_id}:{session_id}"

    async def get_history(self, user_id: int | str, session_id: str) -> list[dict[str, str]]:
        """Return conversation history (up to MAX_TURNS most recent)."""
        context = await self.load_context(user_id, session_id)
        return [
            {"role": turn["role"], "content": turn["content"]}
            for turn in context.turns[-self._max_turns:]
        ]

    async def load_context(self, user_id: int | str, session_id: str) -> ConversationContext:
        """Load compressed summary + recent turns for prompt construction."""
        payload = await self._load_payload(user_id, session_id)
        return ConversationContext(
            summary=str(payload.get("summary") or ""),
            turns=self._prompt_turns(payload.get("turns", [])),
            entities=self._normalize_entities(payload.get("entities")),
        )

    async def append_turn(
        self, user_id: int | str, session_id: str, role: str, content: str
    ) -> None:
        """Append a turn, compress old turns if needed, and refresh TTL."""
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unsupported conversation role: {role}")
        payload = await self._load_payload(user_id, session_id)
        turns = self._stored_turns(payload.get("turns", []))
        turns.append(self._build_turn(role, content))
        payload["turns"] = turns
        payload["updated_at"] = time.time()
        payload["entities"] = self._merge_entities(
            self._normalize_entities(payload.get("entities")),
            self._extract_entities(content),
        )
        payload = await self._compress_payload(payload)
        await self._save_payload(user_id, session_id, payload)

    async def append_exchange(
        self,
        user_id: int | str,
        session_id: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        """Append a user/assistant exchange with a single Redis write."""
        payload = await self._load_payload(user_id, session_id)
        turns = self._stored_turns(payload.get("turns", []))
        turns.extend([
            self._build_turn("user", user_content),
            self._build_turn("assistant", assistant_content),
        ])
        entities = self._normalize_entities(payload.get("entities"))
        entities = self._merge_entities(entities, self._extract_entities(user_content))
        entities = self._merge_entities(entities, self._extract_entities(assistant_content))
        payload["turns"] = turns
        payload["entities"] = entities
        payload["updated_at"] = time.time()
        payload = await self._compress_payload(payload)
        await self._save_payload(user_id, session_id, payload)

    async def clear_session(self, user_id: int | str, session_id: str) -> None:
        """Delete a session."""
        await self._redis.delete(self._key(user_id, session_id))

    async def _load_payload(self, user_id: int | str, session_id: str) -> dict[str, Any]:
        raw = await self._redis.get(self._key(user_id, session_id))
        if raw is None:
            return self._empty_payload()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt session data for %s:%s", user_id, session_id)
            return self._empty_payload()

        if isinstance(data, list):
            payload = self._empty_payload()
            payload["turns"] = self._stored_turns(data)
            payload["entities"] = self._extract_entities_from_turns(payload["turns"])
            payload = await self._compress_payload(payload)
            await self._save_payload(user_id, session_id, payload)
            return payload

        if not isinstance(data, dict):
            logger.warning("Unexpected session payload for %s:%s", user_id, session_id)
            return self._empty_payload()

        payload = self._empty_payload()
        payload.update(data)
        payload["version"] = PAYLOAD_VERSION
        payload["summary"] = str(payload.get("summary") or "")[-self._summary_max_chars:]
        payload["turns"] = self._stored_turns(payload.get("turns", []))
        payload["entities"] = self._normalize_entities(payload.get("entities"))
        return payload

    async def _save_payload(
        self, user_id: int | str, session_id: str, payload: dict[str, Any]
    ) -> None:
        payload["version"] = PAYLOAD_VERSION
        payload["updated_at"] = time.time()
        await self._redis.set(
            self._key(user_id, session_id),
            json.dumps(payload, ensure_ascii=False),
            ex=self._session_ttl,
        )

    async def _compress_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        turns = self._stored_turns(payload.get("turns", []))
        if len(turns) <= self._compression_threshold:
            payload["turns"] = turns
            return payload

        keep = max(1, self._max_turns)
        old_turns = turns[:-keep]
        recent_turns = turns[-keep:]
        payload["summary"] = await self._summarize_turns(
            str(payload.get("summary") or ""),
            old_turns,
        )
        payload["turns"] = recent_turns
        return payload

    async def _summarize_turns(
        self, existing_summary: str, old_turns: list[dict[str, Any]]
    ) -> str:
        if self._summarizer is not None:
            try:
                summary = await self._summarizer.summarize(
                    existing_summary=existing_summary,
                    turns=old_turns,
                    max_chars=self._summary_max_chars,
                )
                if summary:
                    return str(summary)[-self._summary_max_chars:]
            except Exception:
                logger.warning("Conversation summarizer failed; using fallback", exc_info=True)
        return self._fallback_summary(existing_summary, old_turns)

    def _fallback_summary(self, existing_summary: str, turns: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        if existing_summary.strip():
            lines.append(existing_summary.strip())
        if turns:
            lines.append("Earlier conversation facts:")
        for turn in turns:
            role = str(turn.get("role", "user"))
            content = re.sub(r"\s+", " ", str(turn.get("content", ""))).strip()
            metadata = turn.get("metadata") if isinstance(turn.get("metadata"), dict) else {}
            if content:
                facts = metadata.get("facts") if isinstance(metadata.get("facts"), list) else []
                if facts:
                    lines.extend(f"- {fact}" for fact in facts[:3])
                else:
                    lines.append(f"- {role}: {content[:300]}")
        summary = "\n".join(lines).strip()
        return summary[-self._summary_max_chars:]

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {
            "version": PAYLOAD_VERSION,
            "summary": "",
            "turns": [],
            "entities": {},
            "updated_at": time.time(),
        }

    @staticmethod
    def _stored_turns(raw_turns: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_turns, list):
            return []
        turns: list[dict[str, Any]] = []
        for turn in raw_turns:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role", "")).strip()
            content = str(turn.get("content", "")).strip()
            if role not in {"user", "assistant", "system"} or not content:
                continue
            metadata = turn.get("metadata") if isinstance(turn.get("metadata"), dict) else {}
            if not metadata:
                metadata = MemoryImportanceScorer().score_turn(role, content)
            turns.append({
                "role": role,
                "content": content,
                "created_at": float(turn.get("created_at") or time.time()),
                "metadata": metadata,
            })
        return turns

    @staticmethod
    def _prompt_turns(raw_turns: Any) -> list[dict[str, str]]:
        return [
            {"role": turn["role"], "content": turn["content"]}
            for turn in ConversationManager._stored_turns(raw_turns)
        ]

    def _build_turn(self, role: str, content: str) -> dict[str, Any]:
        return {
            "role": role,
            "content": content,
            "created_at": time.time(),
            "metadata": self._scorer.score_turn(role, content),
        }

    @staticmethod
    def _extract_entities(content: str) -> dict[str, list[str]]:
        return MemoryImportanceScorer().score_turn("user", content).get("entities", {})

    @classmethod
    def _extract_entities_from_turns(cls, turns: list[dict[str, Any]]) -> dict[str, list[str]]:
        entities: dict[str, list[str]] = {}
        for turn in turns:
            entities = cls._merge_entities(entities, cls._extract_entities(str(turn.get("content", ""))))
        return entities

    @staticmethod
    def _normalize_entities(raw: Any) -> dict[str, list[str]]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, list[str]] = {}
        for key, value in raw.items():
            if isinstance(value, list):
                vals = sorted({str(v) for v in value if str(v).strip()})
                if vals:
                    out[str(key)] = vals
        return out

    @staticmethod
    def _merge_entities(
        base: dict[str, list[str]], extra: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        merged = {k: list(v) for k, v in base.items()}
        for key, values in extra.items():
            merged[key] = sorted({*merged.get(key, []), *values})
        return merged
