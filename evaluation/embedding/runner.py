"""Benchmark orchestration: spawn per-model workers, compute metrics, aggregate.

Each model runs in its own subprocess (clean memory isolation). Worker ranked
lists are cached and keyed by a hash of (corpus, queries); the cache is shared by
:mod:`pooling` and the final metric run so models are never encoded twice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from evaluation.embedding import metrics
from evaluation.embedding.models import DEFAULT_ORDER

logger = logging.getLogger(__name__)

CACHE_DIR = Path("reports/embedding_eval/cache")
QUERIES_PATH = Path("data/eval/_queries.json")
RESULTS_PATH = Path("reports/embedding_eval/results.json")


# ── qrels / queries io ──────────────────────────────────────────────────────
def load_qrels(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def export_queries(qrels_path: str | Path, out: str | Path = QUERIES_PATH) -> Path:
    """Write the qid/query list workers consume (queries are label-independent)."""
    rows = load_qrels(qrels_path)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"qid": r["qid"], "query": r["query"]} for r in rows]
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out


def _io_hash(corpus_path: str | Path, queries_path: str | Path) -> str:
    h = hashlib.sha256()
    for p in (corpus_path, queries_path):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


# ── worker spawning ─────────────────────────────────────────────────────────
def ensure_cached(
    model_key: str,
    corpus_path: str | Path,
    queries_path: str | Path,
    top_k: int = 50,
    threads: int = 4,
    cache_dir: str | Path = CACHE_DIR,
    force: bool = False,
) -> dict[str, Any]:
    """Return cached worker result for *model_key*, spawning a subprocess if stale."""
    cache_dir = Path(cache_dir)
    cache_file = cache_dir / f"{model_key}.json"
    want_hash = _io_hash(corpus_path, queries_path)

    if cache_file.exists() and not force:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("_io_hash") == want_hash:
                logger.info("Cache hit: %s", model_key)
                return cached
        except Exception:  # noqa: BLE001
            pass

    logger.info("Running worker subprocess: %s", model_key)
    cmd = [
        sys.executable, "-m", "evaluation.embedding.worker",
        "--model", model_key,
        "--corpus", str(corpus_path),
        "--queries", str(queries_path),
        "--top-k", str(top_k),
        "--threads", str(threads),
        "--cache-dir", str(cache_dir),
    ]
    subprocess.run(cmd, check=True)
    result = json.loads(cache_file.read_text(encoding="utf-8"))
    result["_io_hash"] = want_hash
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ── metric computation ──────────────────────────────────────────────────────
def compute_metrics(result: dict[str, Any], qrels: list[dict]) -> dict[str, Any]:
    ranked = result["ranked"]
    per_query: list[dict[str, float]] = []
    categories: list[str] = []
    for q in qrels:
        qid = q["qid"]
        rel = {cid: float(g) for cid, g in q.get("relevant", {}).items()}
        ranked_ids = [cid for cid, _ in ranked.get(qid, [])]
        per_query.append(metrics.per_query_metrics(ranked_ids, rel))
        categories.append(q.get("category", "general"))

    return {
        "aggregate": metrics.aggregate(per_query),
        "by_category_ndcg10": metrics.aggregate_by_category(per_query, categories, "ndcg@10"),
        "by_lang_ndcg10": metrics.aggregate_by_category(
            per_query, [q.get("lang", "?") for q in qrels], "ndcg@10"
        ),
    }


def run_benchmark(
    models: list[str],
    qrels_path: str | Path,
    corpus_path: str | Path,
    top_k: int = 50,
    threads: int = 4,
    force: bool = False,
    output_path: str | Path = RESULTS_PATH,
) -> dict[str, Any]:
    """Run all *models*, compute accuracy + carry perf/memory, write results.json."""
    queries_path = export_queries(qrels_path)
    qrels = load_qrels(qrels_path)
    verified = sum(1 for q in qrels if q.get("verified"))
    logger.info("Loaded %d qrels (%d human-verified)", len(qrels), verified)

    all_results: dict[str, Any] = {}
    for key in models:
        worker_res = ensure_cached(key, corpus_path, queries_path, top_k, threads, force=force)
        scored = compute_metrics(worker_res, qrels)
        all_results[key] = {
            "meta": worker_res["meta"],
            "fairness": worker_res["fairness"],
            "speed": worker_res["speed"],
            "memory": worker_res["memory"],
            "metrics": scored,
        }

    payload = {
        "models": models,
        "n_queries": len(qrels),
        "n_verified": verified,
        "n_corpus": all_results[models[0]]["fairness"]["n_corpus"] if models else 0,
        "top_k": top_k,
        "threads": threads,
        "results": all_results,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Benchmark results -> %s", output_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run embedding benchmark")
    parser.add_argument("--models", default="all", help="Comma-separated keys or 'all'")
    parser.add_argument("--qrels", default="data/eval/embedding_qrels.jsonl")
    parser.add_argument("--corpus", default="data/eval/embedding_corpus.jsonl")
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--out", default=str(RESULTS_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    models = DEFAULT_ORDER if args.models == "all" else [m.strip() for m in args.models.split(",")]
    run_benchmark(models, args.qrels, args.corpus, args.top_k, args.threads, args.force, args.out)


if __name__ == "__main__":
    main()
