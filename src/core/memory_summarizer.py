"""Structured short-term memory summarization."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class MemorySummarizer:
    """Summarize old conversation turns into a bounded structured memory."""

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    async def summarize(
        self,
        *,
        existing_summary: str,
        turns: list[dict[str, Any]],
        max_chars: int,
    ) -> str:
        if self._llm is not None:
            try:
                prompt = self._build_prompt(existing_summary, turns, max_chars)
                resp = await self._llm.generate(prompt, temperature=0.0, max_tokens=600)
                text = resp.text if hasattr(resp, "text") else str(resp)
                if text.strip():
                    return text.strip()[-max_chars:]
            except Exception:
                logger.warning("LLM memory summarization failed; using deterministic fallback", exc_info=True)
        return self.fallback_summary(existing_summary, turns, max_chars)

    @staticmethod
    def fallback_summary(
        existing_summary: str,
        turns: list[dict[str, Any]],
        max_chars: int,
    ) -> str:
        sections: dict[str, list[str]] = {
            "当前目标": [],
            "已确认事实": [],
            "用户偏好": [],
            "关键实体": [],
            "工具证据": [],
            "未完成问题": [],
            "下一步": [],
        }
        if existing_summary.strip():
            sections["已确认事实"].append(existing_summary.strip())

        chips: set[str] = set()
        for turn in turns:
            content = re.sub(r"\s+", " ", str(turn.get("content", ""))).strip()
            metadata = turn.get("metadata") if isinstance(turn.get("metadata"), dict) else {}
            for chip in ((metadata.get("entities") or {}).get("chips") or []):
                chips.add(str(chip))
            for fact in metadata.get("facts") or []:
                if str(fact).strip():
                    sections["已确认事实"].append(str(fact).strip())
            topics = set(metadata.get("topics") or [])
            role = str(turn.get("role", "user"))
            if "preference" in topics:
                sections["用户偏好"].append(content[:240])
            if role == "assistant" and (metadata.get("facts") or topics):
                sections["工具证据"].extend(str(fact) for fact in (metadata.get("facts") or [])[:3])
            if role == "user" and content:
                if any(mark in content for mark in ("?", "？", "多少", "如何", "怎么")):
                    sections["未完成问题"].append(content[:240])
                else:
                    sections["当前目标"].append(content[:240])

        sections["关键实体"].extend(sorted(chips))
        lines: list[str] = []
        for title, values in sections.items():
            unique = []
            for value in values:
                if value and value not in unique:
                    unique.append(value)
            if unique:
                lines.append(f"## {title}")
                lines.extend(f"- {value}" for value in unique[:8])
        return "\n".join(lines).strip()[-max_chars:]

    @staticmethod
    def _build_prompt(existing_summary: str, turns: list[dict[str, Any]], max_chars: int) -> str:
        payload = "\n".join(
            f"{turn.get('role', 'user')}: {turn.get('content', '')}"
            for turn in turns
        )
        return (
            "请把以下芯片问答会话压缩成短期记忆摘要。只保留已确认事实、用户偏好、"
            "当前目标、关键实体、工具证据、未完成问题、下一步。不要编造数字；"
            "数字/参数必须来自输入中的工具结果或已确认事实，不确定的内容不要写入。"
            f"总长度不超过 {max_chars} 个字符。\n\n"
            f"已有摘要:\n{existing_summary or '(无)'}\n\n"
            f"待压缩 turns:\n{payload}\n\n"
            "输出 Markdown，包含固定小标题：当前目标、已确认事实、用户偏好、关键实体、工具证据、未完成问题、下一步。"
        )
