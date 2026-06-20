"""Eval/grounding-driven candidate memory consolidation."""

from __future__ import annotations

from typing import Any

from src.core.episodic_memory import MemoryEpisode
from src.core.memory_governance import GovernedMemory


class MemoryConsolidator:
    """Propose governed candidate memories from high-quality episodes."""

    def __init__(
        self,
        *,
        min_grounding_coverage: float = 0.85,
        min_citations: int = 1,
    ) -> None:
        self._min_grounding_coverage = min_grounding_coverage
        self._min_citations = min_citations

    def propose_from_episode(self, episode: MemoryEpisode) -> GovernedMemory | None:
        if not self._eligible(episode):
            return None
        tools = " -> ".join(episode.tools_used) if episode.tools_used else "no tools"
        content = (
            "成功查询经验："
            f"问题「{episode.query_text[:160]}」使用工具链 {tools}，"
            f"grounding={episode.grounding.get('coverage', 'unknown')}，"
            f"引用数={len(episode.citations)}。"
        )
        return GovernedMemory(
            scope="project",
            owner_key=None,
            kind="procedure_hint",
            content=content,
            tags=["auto_candidate", "episode"],
            source="episode",
            source_id=episode.id,
            status="candidate",
            metadata={
                "tools_used": episode.tools_used,
                "grounding": episode.grounding,
                "outcome": episode.outcome,
            },
        )

    def _eligible(self, episode: MemoryEpisode) -> bool:
        if episode.outcome != "success":
            return False
        if len(episode.citations) < self._min_citations:
            return False
        grounding: dict[str, Any] = episode.grounding or {}
        if grounding.get("abstained"):
            return False
        coverage = grounding.get("coverage")
        if coverage is None:
            return bool(episode.tools_used)
        try:
            return float(coverage) >= self._min_grounding_coverage
        except (TypeError, ValueError):
            return False
