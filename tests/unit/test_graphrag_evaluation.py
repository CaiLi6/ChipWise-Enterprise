"""Unit tests for deterministic GraphRAG evaluation metrics."""

from __future__ import annotations

import pytest
from src.evaluation.graphrag import (
    GraphRAGCase,
    GraphRAGEvaluator,
    aggregate_case_metrics,
    coverage_metrics,
)


class _FakeGraphSearch:
    async def find_alternatives(self, part_number: str, include_domestic: bool = False):  # noqa: ARG002
        return [{"part_number": "XCKU5PFFVD900"}] if part_number == "PH2A106FLG900" else []

    async def param_range_search(self, param_name: str, min_val: float, max_val: float):  # noqa: ARG002
        return [{"part_number": "PH2A106FLG900", "param": param_name, "value": min_val}]

    async def get_chip_subgraph(self, part_number: str, max_depth: int = 1):  # noqa: ARG002
        return [{"src": {"part_number": part_number}, "dest": {"name": "DSP"}}]


@pytest.mark.unit
class TestGraphRAGEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_cases(self) -> None:
        cases = [
            GraphRAGCase(
                case_id="alt",
                case_type="alternative",
                question="替代芯片",
                query_args={"part_number": "PH2A106FLG900"},
                expected={"part_numbers": ["XCKU5PFFVD900"]},
            ),
            GraphRAGCase(
                case_id="param",
                case_type="param_range",
                question="DSP 数量",
                query_args={"param_name": "DSP", "min_val": 1800, "max_val": 1800},
                expected={"part_number": "PH2A106FLG900"},
            ),
            GraphRAGCase(
                case_id="subgraph",
                case_type="subgraph",
                question="子图",
                query_args={"part_number": "PH2A106FLG900", "max_depth": 1},
                expected={"min_results": 1},
            ),
        ]
        results = await GraphRAGEvaluator(_FakeGraphSearch()).evaluate_cases(cases)  # type: ignore[arg-type]
        assert all(r.passed for r in results)
        metrics = aggregate_case_metrics(results)
        assert metrics["pass_rate"] == 1.0
        assert metrics["mean_recall"] == 1.0

    def test_coverage_metrics(self) -> None:
        source = {
            "chips": 10,
            "parameters": 20,
            "documents": 5,
            "alternatives": 2,
            "design_rules": 0,
            "errata": 0,
        }
        graph = {
            "chips": 10,
            "parameters": 18,
            "documents": 5,
            "alternatives": 1,
            "design_rules": 0,
            "errata": 0,
            "has_param": 18,
            "documented_in": 5,
            "has_rule": 0,
            "has_errata": 0,
        }
        metrics = coverage_metrics(source, graph)
        assert metrics["chip_node_coverage"] == 1.0
        assert metrics["parameter_node_coverage"] == 0.9
        assert metrics["alternative_edge_coverage"] == 0.5
