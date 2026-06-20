"""Procedural memory: reusable tool-selection hints learned from episodes."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProcedureHint:
    id: str
    intent: str
    trigger_patterns: list[str] = field(default_factory=list)
    recommended_tools: list[str] = field(default_factory=list)
    stop_rules: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0


_DEFAULT_PROCEDURES = [
    ProcedureHint(
        id="single-param-sql-first",
        intent="single_numeric_parameter",
        trigger_patterns=["主频", "DSP", "IO", "电压", "功耗", "PCIe", "clock", "frequency"],
        recommended_tools=["sql_query", "rag_search"],
        stop_rules=["If sql_query returns the requested parameter, answer immediately with citations if available."],
    ),
    ProcedureHint(
        id="relationship-graph-first",
        intent="relationship_or_alternative",
        trigger_patterns=["替代", "兼容", "alternative", "compatible", "相似"],
        recommended_tools=["graph_query", "rag_search"],
        stop_rules=["Use graph_query first for alternatives; fall back to rag_search if graph misses."],
    ),
    ProcedureHint(
        id="design-rule-rag-first",
        intent="design_rule_or_errata",
        trigger_patterns=["规则", "布线", "时序", "errata", "勘误", "layout"],
        recommended_tools=["rag_search", "graph_query"],
        stop_rules=["Use rag_search for source-backed design details; do not invent numeric limits."],
    ),
]


class ProceduralMemoryStore:
    """Store and retrieve conservative procedural hints."""

    def __init__(self, db_pool: Any = None) -> None:
        self._pool = db_pool

    async def get_hints(self, query: str, limit: int = 3) -> list[ProcedureHint]:
        hints = self._default_hints(query)
        hints.extend(await self._db_hints(query, limit=limit))
        dedup: dict[str, ProcedureHint] = {}
        for hint in hints:
            dedup.setdefault(hint.id, hint)
        return list(dedup.values())[:limit]

    async def record_outcome(self, query: str, tools_used: list[str], success: bool) -> None:
        if self._pool is None or not tools_used:
            return
        intent = self._infer_intent(query)
        procedure_id = f"learned-{intent}-{'-'.join(tools_used[:2])}"[:64]
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memory_procedures
                        (id, intent, trigger_patterns, recommended_tools, stop_rules,
                         success_count, failure_count, status, last_used_at, updated_at)
                    VALUES
                        ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb,
                         $6, $7, 'active', now(), now())
                    ON CONFLICT (id) DO UPDATE SET
                        success_count = memory_procedures.success_count + EXCLUDED.success_count,
                        failure_count = memory_procedures.failure_count + EXCLUDED.failure_count,
                        last_used_at = now(),
                        updated_at = now()
                    """,
                    procedure_id,
                    intent,
                    json.dumps(self._keywords(query), ensure_ascii=False),
                    json.dumps(tools_used, ensure_ascii=False),
                    json.dumps(["Learned from successful grounded episodes."], ensure_ascii=False),
                    1 if success else 0,
                    0 if success else 1,
                )
        except Exception:
            logger.warning("Failed to update procedural memory", exc_info=True)

    @staticmethod
    def format_hints(hints: list[ProcedureHint]) -> str:
        if not hints:
            return ""
        lines = ["Procedural memory hints (advisory, still obey grounding):"]
        for hint in hints:
            tools = " -> ".join(hint.recommended_tools) if hint.recommended_tools else "(no tools)"
            lines.append(f"- {hint.intent}: prefer {tools}; stop rules: {'; '.join(hint.stop_rules[:2])}")
        return "\n".join(lines)

    def _default_hints(self, query: str) -> list[ProcedureHint]:
        q = query.lower()
        out: list[ProcedureHint] = []
        for hint in _DEFAULT_PROCEDURES:
            if any(p.lower() in q for p in hint.trigger_patterns):
                out.append(hint)
        return out

    async def _db_hints(self, query: str, limit: int) -> list[ProcedureHint]:
        if self._pool is None:
            return []
        keywords = self._keywords(query)
        if not keywords:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, intent, trigger_patterns, recommended_tools, stop_rules,
                           success_count, failure_count
                    FROM memory_procedures
                    WHERE status = 'active'
                    ORDER BY success_count DESC, updated_at DESC
                    LIMIT $1
                    """,
                    max(limit * 3, 10),
                )
            hints: list[ProcedureHint] = []
            for row in rows:
                trigger_patterns = list(row["trigger_patterns"] or [])
                if not any(str(p).lower() in query.lower() for p in trigger_patterns):
                    continue
                hints.append(ProcedureHint(
                    id=row["id"],
                    intent=row["intent"],
                    trigger_patterns=trigger_patterns,
                    recommended_tools=list(row["recommended_tools"] or []),
                    stop_rules=list(row["stop_rules"] or []),
                    success_count=int(row["success_count"] or 0),
                    failure_count=int(row["failure_count"] or 0),
                ))
            return hints[:limit]
        except Exception:
            logger.warning("Failed to retrieve procedural memory", exc_info=True)
            return []

    @staticmethod
    def _infer_intent(query: str) -> str:
        q = query.lower()
        if any(word in q for word in ("替代", "兼容", "alternative", "compatible")):
            return "relationship_or_alternative"
        if any(word in q for word in ("规则", "布线", "errata", "勘误", "layout")):
            return "design_rule_or_errata"
        return "single_numeric_parameter"

    @staticmethod
    def _keywords(query: str) -> list[str]:
        return sorted(set(re.findall(r"[A-Za-z0-9_\-]{3,}|[\u4e00-\u9fff]{2,}", query)))[:12]
