"""Unified CLI for the embedding benchmark.

Pipeline::

    python -m evaluation.embedding.cli build-corpus  --limit 60
    python -m evaluation.embedding.cli build-testset --n 90
    python -m evaluation.embedding.cli pool
    python -m evaluation.embedding.cli review --sample 12   # then --mark-verified
    python -m evaluation.embedding.cli run     --models all
    python -m evaluation.embedding.cli hybrid
    python -m evaluation.embedding.cli report
"""

from __future__ import annotations

import argparse
import logging

from evaluation.embedding.models import DEFAULT_ORDER


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(prog="evaluation.embedding.cli", description="Embedding benchmark")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build-corpus", help="Build frozen chunk corpus from real PDFs")
    p.add_argument("--docs", default="data/documents")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--max-pages", type=int, default=40)
    p.add_argument("--seed", type=int, default=1234)

    p = sub.add_parser("build-testset", help="Draft bilingual test set via LLM")
    p.add_argument("--n", type=int, default=90)
    p.add_argument("--per-chunk", type=int, default=2)
    p.add_argument("--seed", type=int, default=1234)

    p = sub.add_parser("pool", help="Pool candidates + LLM-grade into qrels")
    p.add_argument("--pool-models", default="bge-m3,e5-large")
    p.add_argument("--pool-n", type=int, default=10)
    p.add_argument("--max-new", type=int, default=12)
    p.add_argument("--threads", type=int, default=4)

    p = sub.add_parser("review", help="Summarize / sample / verify qrels")
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--mark-verified", action="store_true")

    p = sub.add_parser("run", help="Run dense benchmark across models")
    p.add_argument("--models", default="all")
    p.add_argument("--qrels", default="data/eval/embedding_qrels.jsonl")
    p.add_argument("--corpus", default="data/eval/embedding_corpus.jsonl")
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("hybrid", help="BGE-M3 hybrid (dense+sparse) reference run")
    p.add_argument("--dense-pool", type=int, default=100)
    p.add_argument("--top-k", type=int, default=20)

    p = sub.add_parser("report", help="Render Markdown + CSV + charts")

    sub.add_parser("all", help="(corpus->testset->pool->run->hybrid->report); review is manual")

    args = parser.parse_args()
    _setup_logging()

    if args.cmd == "build-corpus":
        from evaluation.embedding.corpus import build_corpus

        build_corpus(args.docs, args.limit, args.max_pages, args.seed)
    elif args.cmd == "build-testset":
        from evaluation.embedding.testset import build_testset

        build_testset(args.n, args.per_chunk, args.seed)
    elif args.cmd == "pool":
        from evaluation.embedding.pooling import build_qrels

        pool_models = [m.strip() for m in args.pool_models.split(",") if m.strip()]
        build_qrels(pool_models=pool_models, pool_n=args.pool_n,
                    max_new_candidates=args.max_new, threads=args.threads)
    elif args.cmd == "review":
        from evaluation.embedding.review import mark_verified, sample, summarize

        summarize()
        if args.sample:
            sample(n=args.sample)
        if args.mark_verified:
            mark_verified(value=True)
    elif args.cmd == "run":
        from evaluation.embedding.runner import run_benchmark

        models = DEFAULT_ORDER if args.models == "all" else [m.strip() for m in args.models.split(",")]
        run_benchmark(models, args.qrels, args.corpus, args.top_k, args.threads, args.force)
    elif args.cmd == "hybrid":
        from evaluation.embedding.hybrid import run_hybrid_reference

        run_hybrid_reference(dense_pool=args.dense_pool, top_k=args.top_k)
    elif args.cmd == "report":
        from evaluation.embedding.report import generate_report

        generate_report()
    elif args.cmd == "all":
        from evaluation.embedding.corpus import build_corpus
        from evaluation.embedding.hybrid import run_hybrid_reference
        from evaluation.embedding.pooling import build_qrels
        from evaluation.embedding.report import generate_report
        from evaluation.embedding.runner import run_benchmark
        from evaluation.embedding.testset import build_testset

        build_corpus()
        build_testset()
        build_qrels()
        run_benchmark(DEFAULT_ORDER, "data/eval/embedding_qrels.jsonl", "data/eval/embedding_corpus.jsonl")
        run_hybrid_reference()
        generate_report()


if __name__ == "__main__":
    main()
