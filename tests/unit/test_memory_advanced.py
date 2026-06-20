"""Unit tests for episodic/procedural/governed memory helpers."""

from __future__ import annotations

import pytest
from src.core.episodic_memory import EpisodicMemoryStore, MemoryEpisode
from src.core.memory_consolidator import MemoryConsolidator
from src.core.memory_governance import explicit_memory_from_query
from src.core.procedural_memory import ProceduralMemoryStore, ProcedureHint


@pytest.mark.unit
class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_no_db_record_degrades_to_none(self) -> None:
        episode = MemoryEpisode(
            user_key="u-1",
            session_id="s1",
            trace_id="t1",
            query_text="XCKU5PFFVD900 主频",
        )
        assert await EpisodicMemoryStore(None).record_episode(episode) is None

    @pytest.mark.asyncio
    async def test_no_db_list_returns_empty(self) -> None:
        assert await EpisodicMemoryStore(None).list_episodes(user_key="u-1") == []


@pytest.mark.unit
class TestProceduralMemory:
    @pytest.mark.asyncio
    async def test_default_hint_for_single_parameter_query(self) -> None:
        hints = await ProceduralMemoryStore(None).get_hints("XCKU5PFFVD900 PCIe 主频是多少")
        assert hints
        assert hints[0].intent == "single_numeric_parameter"
        assert "sql_query" in hints[0].recommended_tools

    @pytest.mark.asyncio
    async def test_default_hint_for_alternative_query(self) -> None:
        hints = await ProceduralMemoryStore(None).get_hints("有没有兼容替代料")
        assert any(h.intent == "relationship_or_alternative" for h in hints)

    def test_format_hints(self) -> None:
        hints = [
            ProcedureHint(
                id="single-param-sql-first",
                intent="single_numeric_parameter",
                recommended_tools=["sql_query", "rag_search"],
                stop_rules=["stop after clear SQL hit"],
            )
        ]
        text = ProceduralMemoryStore.format_hints(hints)
        assert "Procedural memory hints" in text


@pytest.mark.unit
class TestGovernedMemory:
    def test_explicit_memory_from_query(self) -> None:
        memory = explicit_memory_from_query(
            "以后默认优先用 sql_query 查单参数",
            owner_key="u-1",
            trace_id="t1",
        )
        assert memory is not None
        assert memory.status == "confirmed"
        assert memory.scope == "user"
        assert memory.kind == "preference"

    def test_non_memory_query_returns_none(self) -> None:
        assert explicit_memory_from_query("XCKU5PFFVD900 主频是多少", owner_key="u-1", trace_id="t1") is None


@pytest.mark.unit
class TestMemoryConsolidator:
    def test_proposes_candidate_for_high_quality_episode(self) -> None:
        episode = MemoryEpisode(
            user_key="u-1",
            session_id="s1",
            trace_id="t1",
            query_text="XCKU5PFFVD900 PCIe 主频是多少",
            tools_used=["sql_query", "rag_search"],
            citations=[{"chunk_id": "c1"}],
            grounding={"coverage": 0.95, "abstained": False},
            outcome="success",
        )
        memory = MemoryConsolidator().propose_from_episode(episode)
        assert memory is not None
        assert memory.status == "candidate"
        assert memory.kind == "procedure_hint"

    def test_rejects_abstained_episode(self) -> None:
        episode = MemoryEpisode(
            user_key="u-1",
            session_id="s1",
            trace_id="t1",
            query_text="bad",
            citations=[{"chunk_id": "c1"}],
            grounding={"coverage": 0.95, "abstained": True},
            outcome="success",
        )
        assert MemoryConsolidator().propose_from_episode(episode) is None
