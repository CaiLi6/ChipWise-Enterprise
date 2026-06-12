"""Test-set review helpers: summary stats, sampling, and verified marking.

Professional-grade ground truth requires human review. These helpers surface the
qrels for inspection (keyword grounding, relevance distribution) and let a
reviewer stamp ``verified`` once the spot-check / disagreement resolution is done.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from collections import Counter
from pathlib import Path

from evaluation.embedding.corpus import load_corpus
from evaluation.embedding.runner import load_qrels

logger = logging.getLogger(__name__)

QRELS = Path("data/eval/embedding_qrels.jsonl")


def summarize(qrels_path: str | Path = QRELS) -> dict:
    rows = load_qrels(qrels_path)
    n = len(rows)
    rel_counts = [len(r.get("relevant", {})) for r in rows]
    cats = Counter(r.get("category", "general") for r in rows)
    langs = Counter(r.get("lang", "?") for r in rows)
    grades = Counter(g for r in rows for g in r.get("relevant", {}).values())
    summary = {
        "n_queries": n,
        "verified": sum(1 for r in rows if r.get("verified")),
        "avg_relevant_per_query": round(sum(rel_counts) / n, 2) if n else 0,
        "max_relevant": max(rel_counts) if rel_counts else 0,
        "by_category": dict(cats),
        "by_lang": dict(langs),
        "grade_distribution": {str(k): v for k, v in sorted(grades.items())},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def sample(qrels_path: str | Path = QRELS, n: int = 10, seed: int = 0) -> None:
    """Print *n* sampled queries with their graded relevant chunk snippets."""
    rows = load_qrels(qrels_path)
    corpus = {c["chunk_id"]: c for c in load_corpus()}
    rng = random.Random(seed)
    for r in rng.sample(rows, min(n, len(rows))):
        print(f"\n=== {r['qid']} [{r['lang']}/{r['category']}] ===")
        print(f"Q: {r['query']}")
        print(f"keywords: {r.get('expected_keywords')}")
        print(f"answer: {r.get('expected_answer')}")
        for cid, g in sorted(r.get("relevant", {}).items(), key=lambda kv: -kv[1]):
            snippet = corpus.get(cid, {}).get("content", "")[:180].replace("\n", " ")
            print(f"  gain={g} {cid}: {snippet}")


def mark_verified(qrels_path: str | Path = QRELS, value: bool = True) -> None:
    rows = load_qrels(qrels_path)
    for r in rows:
        r["verified"] = value
    with open(qrels_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info("Marked verified=%s for %d queries", value, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Review embedding qrels")
    parser.add_argument("--qrels", default=str(QRELS))
    parser.add_argument("--sample", type=int, default=0, help="Print N sampled queries")
    parser.add_argument("--mark-verified", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summarize(args.qrels)
    if args.sample:
        sample(args.qrels, args.sample)
    if args.mark_verified:
        mark_verified(args.qrels, True)


if __name__ == "__main__":
    main()
