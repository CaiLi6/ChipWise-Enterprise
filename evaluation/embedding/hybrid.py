"""BGE-M3 hybrid (dense+sparse) reference run — production-config baseline.

Kept OUT of the apples-to-apples dense ranking. Uses FlagEmbedding to get both
dense and sparse (lexical) signals, then fuses them with RRF (k=60) to mirror the
production ``RRFRanker`` over Milvus hybrid search. Sparse scoring is restricted
to each query's dense top-N candidate pool for tractability.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUT_PATH = Path("reports/embedding_eval/hybrid_reference.json")
RRF_K = 60


def _rrf_fuse(dense_rank: list[str], sparse_rank: list[str], k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = {}
    for r, cid in enumerate(dense_rank):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r + 1)
    for r, cid in enumerate(sparse_rank):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def run_hybrid_reference(
    corpus_path: str | Path = "data/eval/embedding_corpus.jsonl",
    qrels_path: str | Path = "data/eval/embedding_qrels.jsonl",
    dense_pool: int = 100,
    top_k: int = 20,
    output_path: str | Path = OUT_PATH,
) -> Path | None:
    """Encode with FlagEmbedding BGE-M3, fuse dense+sparse, score vs qrels."""
    try:
        from FlagEmbedding import BGEM3FlagModel
    except Exception as exc:  # noqa: BLE001
        logger.warning("FlagEmbedding unavailable; skipping hybrid reference: %s", exc)
        return None

    import numpy as np

    from evaluation.embedding import metrics
    from evaluation.embedding.corpus import load_corpus
    from evaluation.embedding.index import search
    from evaluation.embedding.runner import load_qrels

    corpus = load_corpus(corpus_path)
    chunk_ids = [c["chunk_id"] for c in corpus]
    passages = [c["content"] for c in corpus]
    qrels = load_qrels(qrels_path)
    qtexts = [q["query"] for q in qrels]

    logger.info("Loading BGE-M3 (FlagEmbedding) for hybrid reference ...")
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

    corpus_out = model.encode(passages, return_dense=True, return_sparse=True, batch_size=16)
    query_out = model.encode(qtexts, return_dense=True, return_sparse=True, batch_size=16)

    c_dense = np.asarray(corpus_out["dense_vecs"], dtype=np.float32)
    q_dense = np.asarray(query_out["dense_vecs"], dtype=np.float32)
    c_lex = corpus_out["lexical_weights"]
    q_lex = query_out["lexical_weights"]

    indices, _ = search(c_dense, q_dense, top_k=min(dense_pool, len(passages)))

    per_query: list[dict[str, float]] = []
    categories: list[str] = []
    for qi, q in enumerate(qrels):
        pool_idx = list(indices[qi])
        dense_rank = [chunk_ids[i] for i in pool_idx]
        sparse_scores = [
            (chunk_ids[i], float(model.compute_lexical_matching_score(q_lex[qi], c_lex[i])))
            for i in pool_idx
        ]
        sparse_rank = [cid for cid, _ in sorted(sparse_scores, key=lambda kv: kv[1], reverse=True)]
        fused = _rrf_fuse(dense_rank, sparse_rank)[:top_k]

        rel = {cid: float(g) for cid, g in q.get("relevant", {}).items()}
        per_query.append(metrics.per_query_metrics(fused, rel))
        categories.append(q.get("category", "general"))

    payload = {
        "model": "bge-m3-hybrid",
        "config": {"fusion": "RRF", "rrf_k": RRF_K, "dense_pool": dense_pool, "top_k": top_k},
        "metrics": {
            "aggregate": metrics.aggregate(per_query),
            "by_category_ndcg10": metrics.aggregate_by_category(per_query, categories, "ndcg@10"),
        },
        "n_queries": len(qrels),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Hybrid reference -> %s", output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="BGE-M3 hybrid reference run")
    parser.add_argument("--corpus", default="data/eval/embedding_corpus.jsonl")
    parser.add_argument("--qrels", default="data/eval/embedding_qrels.jsonl")
    parser.add_argument("--dense-pool", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--out", default=str(OUT_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_hybrid_reference(args.corpus, args.qrels, args.dense_pool, args.top_k, args.out)


if __name__ == "__main__":
    main()
