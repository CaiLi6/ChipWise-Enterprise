"""GraphRAG evaluation: graph coverage + relation/path retrieval quality."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.retrieval.graph_search import GraphSearch

_PART_NUMBER = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z][A-Z0-9\-]{4,39}$")
_NON_CHIP_TOKENS = (
    "DC",
    "LPDDR",
    "DDR",
    "VDD",
    "GND",
    "USB",
    "HDMI",
    "PCIE",
    "GPIO",
    "DEMO",
    "REPORT",
    "NOTES",
)


def _looks_like_chip_part(value: str) -> bool:
    token = re.sub(r"\s+", "", value.upper())
    if not _PART_NUMBER.match(token):
        return False
    if any(token.startswith(prefix) for prefix in _NON_CHIP_TOKENS):
        return False
    return not token.endswith("-")


@dataclass
class GraphRAGCase:
    """One deterministic graph retrieval test case."""

    case_id: str
    case_type: str
    question: str
    query_args: dict[str, Any]
    expected: dict[str, Any]


@dataclass
class GraphRAGCaseResult:
    case_id: str
    case_type: str
    passed: bool
    recall: float
    latency_ms: float
    expected: dict[str, Any]
    actual: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


@dataclass
class GraphRAGEvaluationResult:
    generated_at: float
    source_counts: dict[str, int]
    graph_counts: dict[str, int]
    coverage: dict[str, float]
    metrics: dict[str, float]
    cases: list[GraphRAGCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "source_counts": self.source_counts,
            "graph_counts": self.graph_counts,
            "coverage": self.coverage,
            "metrics": self.metrics,
            "cases": [asdict(c) for c in self.cases],
        }


class GraphRAGEvaluator:
    """Evaluate Kùzu graph retrieval against PG-derived golden cases."""

    def __init__(self, graph_search: GraphSearch, graph_store: Any | None = None) -> None:
        self._graph = graph_search
        self._store = graph_store

    async def evaluate_cases(self, cases: list[GraphRAGCase]) -> list[GraphRAGCaseResult]:
        out: list[GraphRAGCaseResult] = []
        for case in cases:
            out.append(await self._evaluate_one(case))
        return out

    async def _evaluate_one(self, case: GraphRAGCase) -> GraphRAGCaseResult:
        started = time.perf_counter()
        try:
            if case.case_type == "alternative":
                actual = await self._graph.find_alternatives(case.query_args["part_number"], include_domestic=True)
                expected = {str(x).upper() for x in case.expected.get("part_numbers", [])}
                found = {str(x.get("part_number", "")).upper() for x in actual}
                recall = len(expected & found) / max(1, len(expected))
                passed = expected.issubset(found)
            elif case.case_type == "param_range":
                actual = await self._graph.param_range_search(
                    case.query_args["param_name"],
                    float(case.query_args["min_val"]),
                    float(case.query_args["max_val"]),
                )
                expected_part = str(case.expected.get("part_number", "")).upper()
                found = {str(x.get("part_number", "")).upper() for x in actual}
                recall = 1.0 if expected_part in found else 0.0
                passed = recall == 1.0
            elif case.case_type == "subgraph":
                actual = await self._graph.get_chip_subgraph(
                    case.query_args["part_number"],
                    max_depth=int(case.query_args.get("max_depth", 1)),
                )
                min_results = int(case.expected.get("min_results", 1))
                recall = min(1.0, len(actual) / max(1, min_results))
                passed = len(actual) >= min_results
            else:
                return self._result(case, False, 0.0, started, [], f"Unsupported case_type={case.case_type}")
            return self._result(case, passed, recall, started, actual)
        except Exception as exc:
            return self._result(case, False, 0.0, started, [], str(exc))

    @staticmethod
    def _result(
        case: GraphRAGCase,
        passed: bool,
        recall: float,
        started: float,
        actual: list[dict[str, Any]],
        error: str = "",
    ) -> GraphRAGCaseResult:
        return GraphRAGCaseResult(
            case_id=case.case_id,
            case_type=case.case_type,
            passed=passed,
            recall=round(recall, 4),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            expected=case.expected,
            actual=actual[:20],
            error=error,
        )


async def build_cases_from_pg(pool: Any, limit_per_type: int = 20) -> list[GraphRAGCase]:
    """Build deterministic golden graph cases from PostgreSQL source-of-truth rows."""
    cases: list[GraphRAGCase] = []
    async with pool.acquire() as conn:
        alt_rows = await conn.fetch(
            """
            SELECT c.part_number AS source_part, alt.part_number AS alt_part
            FROM chip_alternatives ca
            JOIN chips c ON c.id = ca.original_id
            JOIN chips alt ON alt.id = ca.alt_id
            WHERE c.status IN ('active', 'referenced')
            ORDER BY ca.id
            LIMIT $1
            """,
            limit_per_type * 10,
        )
        for idx, row in enumerate(alt_rows):
            if not _looks_like_chip_part(row["source_part"]) or not _looks_like_chip_part(row["alt_part"]):
                continue
            cases.append(GraphRAGCase(
                case_id=f"alt-{idx}-{row['source_part']}",
                case_type="alternative",
                question=f"{row['source_part']} 的替代/兼容芯片有哪些？",
                query_args={"part_number": row["source_part"]},
                expected={"part_numbers": [row["alt_part"]]},
            ))
            if len([c for c in cases if c.case_type == "alternative"]) >= limit_per_type:
                break

        param_rows = await conn.fetch(
            """
            SELECT c.part_number, p.parameter_name, p.typ_value, p.unit
            FROM chip_parameters p
            JOIN chips c ON c.id = p.chip_id
            WHERE p.typ_value IS NOT NULL
            ORDER BY p.id
            LIMIT $1
            """,
            limit_per_type,
        )
        for idx, row in enumerate(param_rows):
            val = float(row["typ_value"])
            cases.append(GraphRAGCase(
                case_id=f"param-{idx}-{row['part_number']}-{row['parameter_name']}",
                case_type="param_range",
                question=f"哪些芯片的 {row['parameter_name']} 约为 {val:g}{row['unit'] or ''}？",
                query_args={"param_name": row["parameter_name"], "min_val": val, "max_val": val},
                expected={"part_number": row["part_number"], "value": val, "unit": row["unit"] or ""},
            ))

        subgraph_rows = await conn.fetch(
            """
            SELECT c.part_number,
                   (SELECT COUNT(*) FROM chip_parameters p WHERE p.chip_id = c.id)
                 + (SELECT COUNT(*) FROM documents d WHERE d.chip_id = c.id)
                 + (SELECT COUNT(*) FROM chip_alternatives a WHERE a.original_id = c.id) AS expected_edges
            FROM chips c
            WHERE EXISTS (SELECT 1 FROM chip_parameters p WHERE p.chip_id = c.id)
            ORDER BY expected_edges DESC
            LIMIT $1
            """,
            limit_per_type,
        )
        for idx, row in enumerate(subgraph_rows):
            min_results = max(1, min(int(row["expected_edges"] or 1), 10))
            cases.append(GraphRAGCase(
                case_id=f"subgraph-{idx}-{row['part_number']}",
                case_type="subgraph",
                question=f"返回 {row['part_number']} 的一跳知识子图。",
                query_args={"part_number": row["part_number"], "max_depth": 1},
                expected={"min_results": min_results},
            ))
    return cases


async def source_counts(pool: Any) -> dict[str, int]:
    async with pool.acquire() as conn:
        rows = await conn.fetchrow(
            """
            SELECT
              (SELECT COUNT(*) FROM chips) AS chips,
              (SELECT COUNT(*) FROM chip_parameters) AS parameters,
              (SELECT COUNT(*) FROM documents WHERE chip_id IS NOT NULL) AS documents,
              (SELECT COUNT(*) FROM chip_alternatives) AS alternatives,
              (SELECT COUNT(*) FROM design_rules) AS design_rules,
              (SELECT COUNT(*) FROM errata) AS errata
            """
        )
    return {k: int(v or 0) for k, v in dict(rows).items()}


def graph_counts(graph_store: Any) -> dict[str, int]:
    queries = {
        "chips": "MATCH (n:Chip) RETURN count(n) AS n",
        "parameters": "MATCH (n:Parameter) RETURN count(n) AS n",
        "documents": "MATCH (n:Document) RETURN count(n) AS n",
        "design_rules": "MATCH (n:DesignRule) RETURN count(n) AS n",
        "errata": "MATCH (n:Errata) RETURN count(n) AS n",
        "has_param": "MATCH (:Chip)-[r:HAS_PARAM]->(:Parameter) RETURN count(r) AS n",
        "alternatives": "MATCH (:Chip)-[r:ALTERNATIVE]->(:Chip) RETURN count(r) AS n",
        "documented_in": "MATCH (:Chip)-[r:DOCUMENTED_IN]->(:Document) RETURN count(r) AS n",
        "has_rule": "MATCH (:Chip)-[r:HAS_RULE]->(:DesignRule) RETURN count(r) AS n",
        "has_errata": "MATCH (:Chip)-[r:HAS_ERRATA]->(:Errata) RETURN count(r) AS n",
    }
    out: dict[str, int] = {}
    for name, query in queries.items():
        rows = graph_store.execute_cypher(query)
        out[name] = int(rows[0].get("n") or 0) if rows else 0
    return out


def coverage_metrics(source: dict[str, int], graph: dict[str, int]) -> dict[str, float]:
    pairs = {
        "chip_node_coverage": ("chips", "chips"),
        "parameter_node_coverage": ("parameters", "parameters"),
        "document_node_coverage": ("documents", "documents"),
        "design_rule_node_coverage": ("design_rules", "design_rules"),
        "errata_node_coverage": ("errata", "errata"),
        "has_param_edge_coverage": ("parameters", "has_param"),
        "alternative_edge_coverage": ("alternatives", "alternatives"),
        "documented_in_edge_coverage": ("documents", "documented_in"),
        "has_rule_edge_coverage": ("design_rules", "has_rule"),
        "has_errata_edge_coverage": ("errata", "has_errata"),
    }
    out: dict[str, float] = {}
    for metric, (src_key, graph_key) in pairs.items():
        denom = source.get(src_key, 0)
        if denom == 0:
            out[metric] = 1.0 if graph.get(graph_key, 0) == 0 else 0.0
        else:
            out[metric] = round(min(1.0, graph.get(graph_key, 0) / denom), 4)
    non_empty = [v for k, v in out.items() if not (k.startswith("errata") or k == "has_errata_edge_coverage")]
    out["mean_non_empty_coverage"] = round(sum(non_empty) / max(1, len(non_empty)), 4)
    return out


def aggregate_case_metrics(results: list[GraphRAGCaseResult]) -> dict[str, float]:
    by_type: dict[str, list[GraphRAGCaseResult]] = {}
    for result in results:
        by_type.setdefault(result.case_type, []).append(result)
    metrics: dict[str, float] = {
        "case_count": float(len(results)),
        "pass_rate": round(sum(1 for r in results if r.passed) / max(1, len(results)), 4),
        "mean_recall": round(sum(r.recall for r in results) / max(1, len(results)), 4),
        "avg_latency_ms": round(sum(r.latency_ms for r in results) / max(1, len(results)), 2),
    }
    for case_type, items in by_type.items():
        metrics[f"{case_type}_pass_rate"] = round(sum(1 for r in items if r.passed) / max(1, len(items)), 4)
        metrics[f"{case_type}_recall"] = round(sum(r.recall for r in items) / max(1, len(items)), 4)
    return metrics


async def run_graphrag_evaluation(pool: Any, graph_store: Any, limit_per_type: int = 20) -> GraphRAGEvaluationResult:
    cases = await build_cases_from_pg(pool, limit_per_type=limit_per_type)
    evaluator = GraphRAGEvaluator(GraphSearch(graph_store), graph_store=graph_store)
    results = await evaluator.evaluate_cases(cases)
    src_counts = await source_counts(pool)
    g_counts = await asyncio.to_thread(graph_counts, graph_store)
    return GraphRAGEvaluationResult(
        generated_at=time.time(),
        source_counts=src_counts,
        graph_counts=g_counts,
        coverage=coverage_metrics(src_counts, g_counts),
        metrics=aggregate_case_metrics(results),
        cases=results,
    )


def write_report(result: GraphRAGEvaluationResult, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
