"""CLI runner for chunking strategy evaluation (§B5)."""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_evaluation(
    strategies: list[str],
    corpus_dir: str | Path,
    qrels_path: str | Path,
    k_values: list[int] | None = None,
    run_e2e: bool = False,
    run_ragas: bool = False,
    output_path: str | Path = "reports/chunking_eval.md",
) -> dict[str, dict[str, Any]]:
    """Run the full evaluation pipeline.

    Steps:
      1. For each strategy, ingest corpus into an isolated Milvus collection.
      2. For each qrel, retrieve and compute L1 metrics.
      3. (Optional) Run L2 end-to-end evaluation.
      4. (Optional) Run L3 RAGAS evaluation.
      5. Aggregate and generate report.
    """
    if k_values is None:
        k_values = [5, 10, 20]

    corpus_dir = Path(corpus_dir)
    qrels = _load_qrels(qrels_path)
    logger.info("Loaded %d qrels (human_verified only)", len(qrels))

    all_results: dict[str, dict[str, Any]] = {}

    for strategy in strategies:
        logger.info("═══ Evaluating strategy: %s ═══", strategy)

        # Step 1: Ingest
        collection_name, chunks = _ingest_strategy(strategy, corpus_dir)

        # Step 2: L1 retrieval metrics
        l1_scores = _run_l1(qrels, collection_name, k_values)
        merged = _aggregate_l1(l1_scores, k_values)

        # Step 3: L2 (optional)
        if run_e2e:
            e2e_scores = _run_l2(qrels)
            merged.update(_aggregate_l2(e2e_scores))

        # Step 4: L3 (optional)
        if run_ragas:
            ragas_scores = _run_l3(qrels, collection_name, k_values[-1])
            merged.update(_aggregate_l3(ragas_scores))

        merged["collection_name"] = collection_name
        all_results[strategy] = merged

    # Step 5: Report
    from evaluation.chunking.report import generate_report

    generate_report(all_results, output_path, k_values)
    logger.info("Evaluation complete. Report: %s", output_path)

    return all_results


# ── Helpers ─────────────────────────────────────────────────────────

def _load_qrels(path: str | Path) -> list[dict[str, Any]]:
    """Load qrels JSONL, keeping only human_verified entries."""
    path = Path(path)
    qrels: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("source") == "human_verified":
                qrels.append(entry)
    # If none verified, use all (for draft evaluation)
    if not qrels:
        logger.warning("No human_verified qrels found; using all entries")
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    qrels.append(json.loads(line))
    return qrels


def _ingest_strategy(
    strategy: str, corpus_dir: Path
) -> tuple[str, list[Any]]:
    from evaluation.chunking.ingest import ingest_for_eval

    return ingest_for_eval(strategy, corpus_dir)


def _run_l1(
    qrels: list[dict[str, Any]],
    collection_name: str,
    k_values: list[int],
) -> list[dict[str, Any]]:
    from evaluation.chunking.metrics import evaluate_retrieval
    from evaluation.chunking.retriever import retrieve

    scores: list[dict[str, Any]] = []
    for qrel in qrels:
        query = qrel.get("query", "")
        results = retrieve(query, collection_name, top_k=max(k_values))
        chunk_dicts = [
            {"content": r.content, "metadata": r.metadata}
            for r in results
        ]
        score = evaluate_retrieval(chunk_dicts, qrel, k_values)
        scores.append(score)
    return scores


def _aggregate_l1(
    scores: list[dict[str, Any]], k_values: list[int]
) -> dict[str, Any]:
    """Average L1 metrics across all queries."""
    if not scores:
        return {}
    agg: dict[str, Any] = {}
    metric_keys = [
        k for k in scores[0] if k != "cost" and isinstance(scores[0][k], (int, float))
    ]
    for key in metric_keys:
        vals = [s[key] for s in scores if key in s]
        agg[key] = round(statistics.mean(vals), 4) if vals else 0.0

    # Aggregate cost
    if "cost" in scores[0]:
        cost_keys = scores[0]["cost"].keys()
        agg_cost: dict[str, float] = {}
        for ck in cost_keys:
            vals = [s["cost"][ck] for s in scores if "cost" in s]
            agg_cost[ck] = round(statistics.mean(vals), 1) if vals else 0.0
        agg["cost"] = agg_cost

    return agg


def _run_l2(qrels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from evaluation.chunking.e2e import evaluate_e2e

    scores: list[dict[str, Any]] = []
    for qrel in qrels:
        score = evaluate_e2e(qrel.get("query", ""), qrel)
        scores.append(score)
    return scores


def _aggregate_l2(scores: list[dict[str, Any]]) -> dict[str, Any]:
    if not scores:
        return {}
    kw_hits = [s["answer_keyword_hit"] for s in scores]
    sim_vals = [s["answer_snippet_similarity"] for s in scores]
    latencies = [s["latency_ms"] for s in scores]

    agg: dict[str, Any] = {
        "answer_keyword_hit": round(statistics.mean(kw_hits), 4),
        "answer_snippet_similarity": round(statistics.mean(sim_vals), 4),
    }
    if latencies:
        latencies.sort()
        agg["latency_p50_ms"] = round(latencies[len(latencies) // 2], 1)
        p95_idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
        agg["latency_p95_ms"] = round(latencies[p95_idx], 1)
    return agg


def _run_l3(
    qrels: list[dict[str, Any]],
    collection_name: str,
    top_k: int,
) -> list[dict[str, float]]:
    from evaluation.chunking.ragas_adapter import evaluate_ragas
    from evaluation.chunking.retriever import retrieve

    batch: list[dict[str, Any]] = []
    for qrel in qrels:
        query = qrel.get("query", "")
        results = retrieve(query, collection_name, top_k=top_k)
        contexts = [r.content for r in results]
        # Run through orchestrator for answer
        from evaluation.chunking.e2e import _run_query

        answer, _ = _run_query(query)
        batch.append({
            "question": query,
            "contexts": contexts,
            "answer": answer,
            "ground_truth": qrel.get("expected_answer_snippet", ""),
        })

    return evaluate_ragas(batch)


def _aggregate_l3(scores: list[dict[str, float]]) -> dict[str, Any]:
    if not scores or not scores[0]:
        return {}
    agg: dict[str, Any] = {}
    for key in ["context_precision", "faithfulness", "answer_relevancy", "answer_correctness"]:
        vals = [s.get(key, 0.0) for s in scores if key in s]
        agg[key] = round(statistics.mean(vals), 4) if vals else 0.0
    return agg


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Chunking strategy evaluation runner")
    parser.add_argument(
        "--strategies", required=True,
        help="Comma-separated strategy names (e.g. datasheet,fine,coarse,parent_child)",
    )
    parser.add_argument("--corpus", required=True, help="Corpus snapshot directory")
    parser.add_argument("--qrels", required=True, help="Qrels JSONL path")
    parser.add_argument("--k", default="5,10,20", help="Comma-separated k values")
    parser.add_argument("--e2e", action="store_true", help="Enable Layer 2 end-to-end evaluation")
    parser.add_argument("--ragas", action="store_true", help="Enable Layer 3 RAGAS evaluation")
    parser.add_argument("--output", default="reports/chunking_eval.md", help="Output report path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    strategies = [s.strip() for s in args.strategies.split(",")]
    k_values = [int(k.strip()) for k in args.k.split(",")]

    run_evaluation(
        strategies=strategies,
        corpus_dir=args.corpus,
        qrels_path=args.qrels,
        k_values=k_values,
        run_e2e=args.e2e,
        run_ragas=args.ragas,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
