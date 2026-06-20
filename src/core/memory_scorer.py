"""Memory importance scoring for short-term conversation turns.

The scorer is deterministic by default so memory writes do not depend on an
LLM. It extracts lightweight metadata used by compression and retrieval.
"""

from __future__ import annotations

import re
from typing import Any

_PART_NUMBER = re.compile(r"\b([A-Z][A-Z0-9\-]{3,19}\d[A-Z0-9\-]*)\b")
_NUMERIC_FACT = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:MHz|GHz|kHz|V|mV|A|mA|uA|W|mW|GB/s|Gbps|Mbps|ns|ms|°C|C)\b",
    re.IGNORECASE,
)
_PREFERENCE = re.compile(r"记住|偏好|以后|总是|不要|默认|prefer|always|never", re.IGNORECASE)
_QUESTION = re.compile(r"\?|？|多少|如何|怎么|what|how|which|compare|对比", re.IGNORECASE)

_TOPIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "parameter_query": re.compile(r"参数|主频|电压|功耗|IO|DSP|PCIe|clock|frequency", re.IGNORECASE),
    "comparison": re.compile(r"对比|比较|compare|versus| vs ", re.IGNORECASE),
    "design_rule": re.compile(r"规则|布线|layout|design rule|时序|thermal|散热", re.IGNORECASE),
    "errata": re.compile(r"errata|勘误|known issue|bug", re.IGNORECASE),
    "bom": re.compile(r"\bBOM\b|物料|替代料|alternative|compatible|兼容", re.IGNORECASE),
    "test_case": re.compile(r"测试|test case|验证|用例", re.IGNORECASE),
}


class MemoryImportanceScorer:
    """Assign importance/topic/entity metadata to conversation turns."""

    def score_turn(self, role: str, content: str) -> dict[str, Any]:
        clean = re.sub(r"\s+", " ", content).strip()
        chips = sorted({m.group(1).upper() for m in _PART_NUMBER.finditer(clean.upper())})
        numeric_facts = [m.group(0) for m in _NUMERIC_FACT.finditer(clean)]
        topics = [
            topic
            for topic, pattern in _TOPIC_PATTERNS.items()
            if pattern.search(clean)
        ]

        score = 0.25
        if role == "user":
            score += 0.10
        if chips:
            score += 0.20
        if numeric_facts:
            score += 0.20
        if topics:
            score += min(0.20, 0.06 * len(topics))
        if _PREFERENCE.search(clean):
            score += 0.25
            topics.append("preference")
        if _QUESTION.search(clean):
            score += 0.08
        if len(clean) > 600:
            score -= 0.05

        facts = self._extract_fact_snippets(clean, chips, numeric_facts)
        return {
            "importance": round(max(0.0, min(score, 1.0)), 3),
            "topics": sorted(set(topics)),
            "entities": {"chips": chips} if chips else {},
            "facts": facts,
        }

    @staticmethod
    def _extract_fact_snippets(
        content: str,
        chips: list[str],
        numeric_facts: list[str],
    ) -> list[str]:
        if not content:
            return []
        sentences = re.split(r"(?<=[。.!?？])\s+|\n+", content)
        snippets: list[str] = []
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if any(chip in s.upper() for chip in chips) or any(fact in s for fact in numeric_facts):
                snippets.append(s[:240])
            if len(snippets) >= 5:
                break
        if not snippets and (chips or numeric_facts):
            snippets.append(content[:240])
        return snippets
