"""Per-model subprocess worker: encode corpus+queries, retrieve, measure.

Run as a module so each model gets a clean process (fair memory isolation)::

    python -m evaluation.embedding.worker --model bge-m3 \
        --corpus data/eval/embedding_corpus.jsonl \
        --queries data/eval/_queries.json --top-k 50

Writes ``<cache-dir>/<model>.json`` with ranked retrievals + perf + memory.
Ranked lists depend only on (corpus, queries), NOT on relevance labels, so the
same cache is reused by both :mod:`pooling` and :mod:`runner`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("embedding.worker")

CACHE_DIR = Path("reports/embedding_eval/cache")


def _load_queries(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_worker(
    model_key: str,
    corpus_path: str,
    queries_path: str,
    top_k: int = 50,
    threads: int = 4,
    cache_dir: str | Path = CACHE_DIR,
) -> Path:
    """Encode + retrieve + measure for one model; return path to result JSON."""
    from evaluation.embedding import perf
    from evaluation.embedding.corpus import load_corpus
    from evaluation.embedding.index import ranked_chunk_ids, search
    from evaluation.embedding.models import REGISTRY, EmbeddingRunner

    spec = REGISTRY[model_key]
    corpus = load_corpus(corpus_path)
    chunk_ids = [c["chunk_id"] for c in corpus]
    passages = [c["content"] for c in corpus]
    queries = _load_queries(queries_path)
    qids = [q["qid"] for q in queries]
    qtexts = [q["query"] for q in queries]

    import psutil

    proc = psutil.Process(os.getpid())
    baseline_rss = proc.memory_info().rss / (1024 * 1024)

    runner = EmbeddingRunner(spec, threads=threads)
    with perf.MemorySampler() as load_mem:
        runner.load()
    post_load_rss = proc.memory_info().rss / (1024 * 1024)

    # Encode corpus (timed) with peak-memory sampling.
    import time

    with perf.MemorySampler() as enc_mem:
        t0 = time.perf_counter()
        corpus_vecs, corpus_stats = runner.encode_passages(passages, batch_size=32)
        corpus_encode_sec = time.perf_counter() - t0
    query_vecs, query_stats = runner.encode_queries(qtexts, batch_size=16)

    indices, scores = search(corpus_vecs, query_vecs, top_k=top_k)
    ranked_ids = ranked_chunk_ids(indices, chunk_ids)
    ranked = {
        qid: [[cid, float(s)] for cid, s in zip(ids, sc, strict=False)]
        for qid, ids, sc in zip(qids, ranked_ids, scores, strict=False)
    }

    # Speed: query latency at batch=1 (production single-query path). Throughput
    # is derived for free from batch-1 latency and the timed corpus encode
    # (batch=32), avoiding an expensive separate sweep on slow CPU models.
    sample_q = qtexts[: min(15, len(qtexts))]
    p50, p95, mean = perf.measure_query_latency(
        lambda qs: runner.encode_queries(qs, batch_size=1)[0], sample_q, warmup=3, reps=1
    )
    corpus_tps = len(passages) / corpus_encode_sec if corpus_encode_sec else 0.0
    throughput = {
        1: (1000.0 / mean) if mean else 0.0,
        32: corpus_tps,
    }
    speed = perf.SpeedReport(
        query_latency_p50_ms=p50,
        query_latency_p95_ms=p95,
        query_latency_mean_ms=mean,
        throughput=throughput,
        corpus_encode_sec=corpus_encode_sec,
        corpus_texts_per_sec=corpus_tps,
    )

    memory = perf.MemoryReport(
        baseline_rss_mb=round(baseline_rss, 1),
        post_load_rss_mb=round(post_load_rss, 1),
        load_delta_mb=round(post_load_rss - baseline_rss, 1),
        peak_encode_rss_mb=enc_mem.peak_mb,
        pss_mb=perf._pss_mb(),
        ru_maxrss_mb=perf.ru_maxrss_mb(),
        gpu_peak_mb=perf.gpu_peak_mb(),
        disk_weight_mb=perf.disk_weight_mb(spec.hf_id),
    )

    result: dict[str, Any] = {
        "model": model_key,
        "meta": {
            "hf_id": spec.hf_id,
            "dim": spec.dim,
            "max_len": spec.max_len,
            "device": runner.device,
            "dtype": runner.dtype,
            "revision": runner.revision,
            "threads": threads,
            "normalize": spec.normalize,
            "query_prefix": spec.query_prefix,
            "passage_prefix": spec.passage_prefix,
            "query_encode_kwargs": spec.query_encode_kwargs,
            "passage_encode_kwargs": spec.passage_encode_kwargs,
            "notes": spec.notes,
        },
        "fairness": {
            "n_corpus": len(passages),
            "n_queries": len(qtexts),
            "corpus_truncation_rate": round(corpus_stats.truncation_rate, 4),
            "query_truncation_rate": round(query_stats.truncation_rate, 4),
            "corpus_nan_or_zero": corpus_stats.nan_or_zero,
            "query_nan_or_zero": query_stats.nan_or_zero,
            "load_peak_rss_mb": load_mem.peak_mb,
        },
        "speed": speed.as_dict(),
        "memory": memory.as_dict(),
        "ranked": ranked,
        "top_k": top_k,
    }

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{model_key}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Worker %s done -> %s", model_key, out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding benchmark per-model worker")
    parser.add_argument("--model", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--cache-dir", default=str(CACHE_DIR))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_worker(args.model, args.corpus, args.queries, args.top_k, args.threads, args.cache_dir)


if __name__ == "__main__":
    main()
