"""Report generator — markdown + CSV comparison tables."""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_report(
    results: dict[str, dict[str, Any]],
    output_path: str | Path,
    k_values: list[int] | None = None,
) -> Path:
    """Generate a markdown comparison report from evaluation results.

    Args:
        results: ``{strategy_name: {metric: value, ...}}``.
        output_path: Path for the markdown report.
        k_values: The k values used in evaluation.

    Returns:
        Path to the generated report.
    """
    if k_values is None:
        k_values = [5, 10, 20]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md = _build_markdown(results, k_values)
    output_path.write_text(md, encoding="utf-8")

    # Also write CSV
    csv_path = output_path.with_suffix(".csv")
    _write_csv(results, csv_path)

    logger.info("Report written to %s (+ %s)", output_path, csv_path)
    return output_path


def _build_markdown(
    results: dict[str, dict[str, Any]], k_values: list[int]
) -> str:
    lines: list[str] = []
    lines.append("# Chunking Strategy Evaluation Report\n")

    strategies = sorted(results.keys())

    # ── Layer 1: Retrieval Metrics ──
    lines.append("## Layer 1 — Retrieval Metrics\n")

    for k in k_values:
        lines.append(f"### k = {k}\n")
        header = "| Strategy | Keyword Recall | Section Recall | MRR | nDCG |"
        sep = "| --- | ---: | ---: | ---: | ---: |"
        lines.append(header)
        lines.append(sep)

        for s in strategies:
            r = results[s]
            lines.append(
                f"| {s} "
                f"| {r.get(f'keyword_recall@{k}', 0):.3f} "
                f"| {r.get(f'section_recall@{k}', 0):.3f} "
                f"| {r.get(f'mrr@{k}', 0):.3f} "
                f"| {r.get(f'ndcg@{k}', 0):.3f} |"
            )
        lines.append("")

    # ── Cost Proxy ──
    lines.append("## Cost Proxy\n")
    header = "| Strategy | Chunks | Avg Chars/Chunk | Approx Tokens |"
    sep = "| --- | ---: | ---: | ---: |"
    lines.append(header)
    lines.append(sep)

    for s in strategies:
        cost = results[s].get("cost", {})
        lines.append(
            f"| {s} "
            f"| {cost.get('num_chunks', 0)} "
            f"| {cost.get('avg_chars_per_chunk', 0):.0f} "
            f"| {cost.get('approx_total_tokens', 0):.0f} |"
        )
    lines.append("")

    # ── Layer 2: End-to-End (if present) ──
    has_e2e = any("answer_keyword_hit" in results[s] for s in strategies)
    if has_e2e:
        lines.append("## Layer 2 — End-to-End\n")
        header = "| Strategy | Answer KW Hit | Snippet Sim | P50 Latency (ms) | P95 Latency (ms) |"
        sep = "| --- | ---: | ---: | ---: | ---: |"
        lines.append(header)
        lines.append(sep)

        for s in strategies:
            r = results[s]
            lines.append(
                f"| {s} "
                f"| {r.get('answer_keyword_hit', 0):.3f} "
                f"| {r.get('answer_snippet_similarity', 0):.3f} "
                f"| {r.get('latency_p50_ms', 0):.0f} "
                f"| {r.get('latency_p95_ms', 0):.0f} |"
            )
        lines.append("")

    # ── Layer 3: RAGAS (if present) ──
    has_ragas = any("context_precision" in results[s] for s in strategies)
    if has_ragas:
        lines.append("## Layer 3 — RAGAS\n")
        header = "| Strategy | Context Precision | Faithfulness | Answer Relevancy | Answer Correctness |"
        sep = "| --- | ---: | ---: | ---: | ---: |"
        lines.append(header)
        lines.append(sep)

        for s in strategies:
            r = results[s]
            lines.append(
                f"| {s} "
                f"| {r.get('context_precision', 0):.3f} "
                f"| {r.get('faithfulness', 0):.3f} "
                f"| {r.get('answer_relevancy', 0):.3f} "
                f"| {r.get('answer_correctness', 0):.3f} |"
            )
        lines.append("")

    return "\n".join(lines)


def _write_csv(results: dict[str, dict[str, Any]], csv_path: Path) -> None:
    """Write raw results as flat CSV."""
    all_keys: set[str] = set()
    for r in results.values():
        all_keys.update(_flatten(r).keys())
    all_keys_sorted = ["strategy"] + sorted(all_keys)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys_sorted)
        writer.writeheader()
        for strategy, r in sorted(results.items()):
            row = _flatten(r)
            row["strategy"] = strategy
            writer.writerow(row)


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts with dot-separated keys."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out
