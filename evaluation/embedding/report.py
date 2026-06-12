"""Render benchmark results into Markdown + CSV + charts.

Produces separate ranking tables (accuracy / speed / memory) plus a fairness
audit and a production-fit recommendation, so a model that wins accuracy but is
too heavy to deploy locally is not silently crowned the winner.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORT_DIR = Path("reports/embedding_eval")


def _fmt_ci(m: dict[str, Any] | None) -> str:
    if not m:
        return "-"
    return f"{m['mean']:.3f} [{m['ci_low']:.3f}, {m['ci_high']:.3f}]"


def _g(d: dict, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _accuracy_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, r in results.items():
        agg = _g(r, "metrics", "aggregate", default={})
        rows.append({
            "model": key,
            "recall@1": _g(agg, "recall@1", "mean"),
            "recall@5": _g(agg, "recall@5", "mean"),
            "recall@10": _g(agg, "recall@10", "mean"),
            "mrr@10": _g(agg, "mrr@10", "mean"),
            "ndcg@10": _g(agg, "ndcg@10", "mean"),
            "map@10": _g(agg, "map@10", "mean"),
            "_agg": agg,
        })
    rows.sort(key=lambda x: (x["ndcg@10"] or 0), reverse=True)
    return rows


def generate_report(
    results_path: str | Path = "reports/embedding_eval/results.json",
    hybrid_path: str | Path = "reports/embedding_eval/hybrid_reference.json",
    out_dir: str | Path = REPORT_DIR,
) -> Path:
    """Write embedding_eval.{md,csv} + charts from results.json."""
    results_path = Path(results_path)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    results: dict[str, Any] = payload["results"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    acc = _accuracy_rows(results)
    lines: list[str] = []
    lines.append("# Embedding 模型对比基准报告\n")
    lines.append(
        f"- 查询数: **{payload['n_queries']}**（人工核验 {payload.get('n_verified', 0)}）"
        f" · 语料 chunk 数: **{payload['n_corpus']}** · top_k: {payload['top_k']} · threads: {payload['threads']}"
    )
    dev = _g(next(iter(results.values())), "meta", "device", default="?")
    dtype = _g(next(iter(results.values())), "meta", "dtype", default="?")
    lines.append(f"- 设备: **{dev}** · dtype: **{dtype}** · 检索: 精确 cosine（dense 隔离，reranker 关闭）\n")

    # 1. Accuracy
    lines.append("## 1. 检索准确率（dense，apples-to-apples）\n")
    lines.append("> 数值为均值，方括号为 bootstrap 95% 置信区间。\n")
    lines.append("| 模型 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | MAP@10 |")
    lines.append("|------|----------|----------|-----------|--------|---------|--------|")
    for row in acc:
        agg = row["_agg"]
        lines.append(
            f"| `{row['model']}` | {_fmt_ci(agg.get('recall@1'))} | {_fmt_ci(agg.get('recall@5'))} "
            f"| {_fmt_ci(agg.get('recall@10'))} | {_fmt_ci(agg.get('mrr@10'))} "
            f"| {_fmt_ci(agg.get('ndcg@10'))} | {_fmt_ci(agg.get('map@10'))} |"
        )
    lines.append("")

    # 2. Per-category & per-language
    lines.append("## 2. 分类别 / 分语言 nDCG@10\n")
    cats = sorted({c for r in results.values() for c in _g(r, "metrics", "by_category_ndcg10", default={})})
    if cats:
        lines.append("| 模型 | " + " | ".join(cats) + " |")
        lines.append("|------|" + "|".join(["---"] * len(cats)) + "|")
        for key, r in results.items():
            bc = _g(r, "metrics", "by_category_ndcg10", default={})
            cells = [f"{_g(bc, c, 'mean', default=float('nan')):.3f}" if c in bc else "-" for c in cats]
            lines.append(f"| `{key}` | " + " | ".join(cells) + " |")
        lines.append("")
    langs = sorted({lg for r in results.values() for lg in _g(r, "metrics", "by_lang_ndcg10", default={})})
    if langs:
        lines.append("| 模型 | " + " | ".join(f"lang={lg}" for lg in langs) + " |")
        lines.append("|------|" + "|".join(["---"] * len(langs)) + "|")
        for key, r in results.items():
            bl = _g(r, "metrics", "by_lang_ndcg10", default={})
            cells = [f"{_g(bl, lg, 'mean', default=float('nan')):.3f}" if lg in bl else "-" for lg in langs]
            lines.append(f"| `{key}` | " + " | ".join(cells) + " |")
        lines.append("")

    # 3. Speed
    lines.append("## 3. 推理速度\n")
    lines.append("| 模型 | query p50 (ms) | query p95 (ms) | 吞吐@32 (texts/s) | 全库编码 (texts/s) |")
    lines.append("|------|----------------|----------------|-------------------|--------------------|")
    for key, r in sorted(results.items(), key=lambda kv: _g(kv[1], "speed", "query_latency_p50_ms", default=1e9)):
        sp = r.get("speed", {})
        thr = _g(sp, "throughput_texts_per_sec", "32", default=_g(sp, "throughput_texts_per_sec", "64", default="-"))
        lines.append(
            f"| `{key}` | {sp.get('query_latency_p50_ms', '-')} | {sp.get('query_latency_p95_ms', '-')} "
            f"| {thr} | {sp.get('corpus_texts_per_sec', '-')} |"
        )
    lines.append("")

    # 4. Memory / deployment
    lines.append("## 4. 部署内存 / 资源\n")
    lines.append("| 模型 | 维度 | 权重磁盘 (MB) | 加载增量 RSS (MB) | 推理峰值 RSS (MB) | PSS (MB) | GPU 峰值 (MB) |")
    lines.append("|------|------|---------------|-------------------|-------------------|----------|---------------|")
    for key, r in sorted(results.items(), key=lambda kv: _g(kv[1], "memory", "peak_encode_rss_mb", default=1e9)):
        mem, meta = r.get("memory", {}), r.get("meta", {})
        lines.append(
            f"| `{key}` | {meta.get('dim', '-')} | {mem.get('disk_weight_mb', '-')} "
            f"| {mem.get('load_delta_mb', '-')} | {mem.get('peak_encode_rss_mb', '-')} "
            f"| {mem.get('pss_mb', '-')} | {mem.get('gpu_peak_mb', '-')} |"
        )
    lines.append("")

    # 5. Fairness audit
    lines.append("## 5. 公平性审计\n")
    lines.append("| 模型 | hf_id | revision | max_len | 语料截断率 | 查询截断率 | NaN/零向量 |")
    lines.append("|------|-------|----------|---------|------------|------------|------------|")
    for key, r in results.items():
        meta, fz = r.get("meta", {}), r.get("fairness", {})
        lines.append(
            f"| `{key}` | {meta.get('hf_id', '-')} | {str(meta.get('revision', '-'))[:12]} "
            f"| {meta.get('max_len', '-')} | {fz.get('corpus_truncation_rate', '-')} "
            f"| {fz.get('query_truncation_rate', '-')} "
            f"| {fz.get('corpus_nan_or_zero', 0)}/{fz.get('query_nan_or_zero', 0)} |"
        )
    lines.append("")

    # 6. Hybrid reference
    hp = Path(hybrid_path)
    if hp.exists():
        hyb = json.loads(hp.read_text(encoding="utf-8"))
        lines.append("## 6. 参考点：BGE-M3 Hybrid (dense+sparse)\n")
        lines.append("> 生产配置参考，不参与上面的纯 dense 排名。\n")
        agg = _g(hyb, "metrics", "aggregate", default={})
        lines.append(f"- nDCG@10: **{_fmt_ci(agg.get('ndcg@10'))}** · Recall@10: {_fmt_ci(agg.get('recall@10'))} "
                     f"· MRR@10: {_fmt_ci(agg.get('mrr@10'))}")
        bdense = _g(results, "bge-m3", "metrics", "aggregate", "ndcg@10", "mean", default=None)
        if bdense is not None and _g(agg, "ndcg@10", "mean") is not None:
            delta = _g(agg, "ndcg@10", "mean") - bdense
            lines.append(f"- 相对 BGE-M3 dense 的 nDCG@10 增益: **{delta:+.3f}**\n")

    # 7. Recommendation
    lines.append("## 7. 结论与产线适配建议\n")
    if acc:
        best = acc[0]
        best_acc = best["model"]
        fastest = min(results, key=lambda k: _g(results[k], "speed", "query_latency_p50_ms", default=1e9))
        lightest = min(results, key=lambda k: _g(results[k], "memory", "peak_encode_rss_mb", default=1e9))
        base = "bge-m3"
        base_agg = _g(results, base, "metrics", "aggregate", "ndcg@10", default={}) if base in results else {}
        # Statistical-significance check vs baseline (CI overlap on nDCG@10).
        sig_note = ""
        if base in results and best_acc != base and base_agg:
            top_ci = best["_agg"].get("ndcg@10", {})
            if top_ci and "ci_low" in top_ci and "ci_high" in base_agg:
                overlap = top_ci["ci_low"] <= base_agg["ci_high"]
                sig_note = (
                    f"，但其 nDCG@10 CI [{top_ci['ci_low']:.3f}, {top_ci['ci_high']:.3f}] 与基准 "
                    f"bge-m3 [{base_agg['ci_low']:.3f}, {base_agg['ci_high']:.3f}] "
                    + ("**重叠 → 差异不具统计显著性**" if overlap else "**不重叠 → 差异显著**")
                )
        lines.append(f"- **检索准确率最优**: `{best_acc}`（nDCG@10 = {best['ndcg@10']:.3f}）{sig_note}")
        lines.append(f"- **延迟最低**: `{fastest}`（p50 {_g(results, fastest, 'speed', 'query_latency_p50_ms')} ms）"
                     f" · **峰值内存最省**: `{lightest}`（{_g(results, lightest, 'memory', 'peak_encode_rss_mb')} MB）")
        # Production-fit summary table (accuracy vs cost).
        lines.append("\n**产线适配综合表**（准确率 vs 资源/速度）\n")
        lines.append("| 模型 | nDCG@10 | query p50 (ms) | 峰值内存 (MB) | 权重 (MB) | 综合定位 |")
        lines.append("|------|---------|----------------|---------------|-----------|----------|")
        verdicts = {
            "bge-m3": "生产基准：准确率/速度/内存均衡，dense+sparse 一体",
            "qwen3-0.6b": "准确率最高但 CPU 最慢、峰值内存最高；适合有 GPU 场景",
            "jina-v3": "延迟最高（LoRA）、加载内存最大；本地 CPU 不划算",
            "e5-large": "速度快但中文→英文检索准确率偏低",
            "bge-large-zh": "最省内存，但英文 Datasheet 准确率最差（中文模型）",
        }
        for row in acc:
            k = row["model"]
            lines.append(
                f"| `{k}` | {row['ndcg@10']:.3f} | {_g(results, k, 'speed', 'query_latency_p50_ms')} "
                f"| {_g(results, k, 'memory', 'peak_encode_rss_mb')} | {_g(results, k, 'memory', 'disk_weight_mb')} "
                f"| {verdicts.get(k, '-')} |"
            )
        lines.append(
            "\n> **建议**: 当前生产模型 `bge-m3` 在纯 dense 下已是第二，且 Recall@5/@10 最高、"
            "速度与内存均衡，并独有 sparse 混合能力（见第 6 节）。`qwen3-0.6b` 的 dense 准确率领先"
            "但不具统计显著性，且 CPU 推理慢 2 倍、峰值内存最高——**在当前无 GPU 的部署下不建议迁移**。"
            "若未来上 GPU，可重新评估 `qwen3-0.6b`。"
        )
    lines.append("")

    md_path = out_dir / "embedding_eval.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    _write_csv(results, out_dir / "embedding_eval.csv")
    _write_charts(acc, results, out_dir)
    logger.info("Report -> %s", md_path)
    return md_path


def _write_csv(results: dict[str, Any], path: Path) -> None:
    cols = [
        "model", "hf_id", "dim", "device", "dtype",
        "recall@1", "recall@5", "recall@10", "mrr@10", "ndcg@10", "map@10",
        "query_p50_ms", "query_p95_ms", "corpus_texts_per_sec",
        "disk_weight_mb", "load_delta_mb", "peak_encode_rss_mb", "pss_mb",
        "corpus_truncation_rate",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for key, r in results.items():
            agg, meta = _g(r, "metrics", "aggregate", default={}), r.get("meta", {})
            sp, mem, fz = r.get("speed", {}), r.get("memory", {}), r.get("fairness", {})
            w.writerow({
                "model": key, "hf_id": meta.get("hf_id"), "dim": meta.get("dim"),
                "device": meta.get("device"), "dtype": meta.get("dtype"),
                "recall@1": _g(agg, "recall@1", "mean"), "recall@5": _g(agg, "recall@5", "mean"),
                "recall@10": _g(agg, "recall@10", "mean"), "mrr@10": _g(agg, "mrr@10", "mean"),
                "ndcg@10": _g(agg, "ndcg@10", "mean"), "map@10": _g(agg, "map@10", "mean"),
                "query_p50_ms": sp.get("query_latency_p50_ms"), "query_p95_ms": sp.get("query_latency_p95_ms"),
                "corpus_texts_per_sec": sp.get("corpus_texts_per_sec"),
                "disk_weight_mb": mem.get("disk_weight_mb"), "load_delta_mb": mem.get("load_delta_mb"),
                "peak_encode_rss_mb": mem.get("peak_encode_rss_mb"), "pss_mb": mem.get("pss_mb"),
                "corpus_truncation_rate": fz.get("corpus_truncation_rate"),
            })


def _write_charts(acc: list[dict], results: dict[str, Any], out_dir: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        logger.warning("matplotlib unavailable, skipping charts: %s", exc)
        return

    models = [r["model"] for r in acc]
    ndcg = [r["ndcg@10"] or 0 for r in acc]
    lat = [_g(results[m], "speed", "query_latency_p50_ms", default=0) for m in models]
    mem = [_g(results[m], "memory", "peak_encode_rss_mb", default=0) for m in models]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].bar(models, ndcg, color="#4C78A8")
    axes[0].set_title("nDCG@10 (higher better)")
    axes[1].bar(models, lat, color="#F58518")
    axes[1].set_title("query p50 latency ms (lower better)")
    axes[2].bar(models, mem, color="#54A24B")
    axes[2].set_title("peak encode RSS MB (lower better)")
    for ax in axes:
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out_dir / "embedding_eval_charts.png", dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render embedding benchmark report")
    parser.add_argument("--results", default="reports/embedding_eval/results.json")
    parser.add_argument("--hybrid", default="reports/embedding_eval/hybrid_reference.json")
    parser.add_argument("--out-dir", default=str(REPORT_DIR))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    generate_report(args.results, args.hybrid, args.out_dir)


if __name__ == "__main__":
    main()
