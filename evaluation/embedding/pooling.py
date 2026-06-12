"""Pool retrieval candidates and assign graded relevance to reduce false negatives.

Single-source labels (only the chunk a question was generated from) make ranking
metrics noisy: datasheets repeat specs across sections/variants, so a model that
retrieves a *different* valid chunk would be wrongly penalized. We therefore pool
top-k candidates from several dense models + a lexical BM25, then have the LLM
grade each pooled candidate (0/1/2). Output: ``data/eval/embedding_qrels.jsonl``.
Human review (verified flag) is still required for professional-grade ground truth.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

from evaluation.embedding._config import llm_generate
from evaluation.embedding.corpus import load_corpus
from evaluation.embedding.runner import ensure_cached, export_queries, load_qrels

logger = logging.getLogger(__name__)

QRELS_OUT = Path("data/eval/embedding_qrels.jsonl")
DEFAULT_POOL_MODELS = ["bge-m3", "e5-large"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*|[\u4e00-\u9fff]")


def _tok(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class _BM25:
    """Minimal Okapi BM25 for lexical candidate generation (pooling only)."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = docs
        self.N = len(docs)
        self.dl = [len(d) for d in docs]
        self.avgdl = sum(self.dl) / self.N if self.N else 0.0
        self.tf = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for d in docs:
            for term in set(d):
                df[term] += 1
        self.idf = {
            t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }

    def top_n(self, query: list[str], n: int) -> list[int]:
        scores: dict[int, float] = {}
        for i in range(self.N):
            tf = self.tf[i]
            denom_norm = self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl) if self.avgdl else self.k1
            s = 0.0
            for term in query:
                if term in tf:
                    idf = self.idf.get(term, 0.0)
                    s += idf * (tf[term] * (self.k1 + 1)) / (tf[term] + denom_norm)
            if s > 0:
                scores[i] = s
        return [i for i, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]]


_JUDGE_PROMPT = """\
You are grading whether each passage helps answer a hardware engineer's question
about a chip datasheet. Grade STRICTLY:
  2 = fully answers the question (contains the specific value/fact asked)
  1 = related/partially relevant (same topic, but not the full answer)
  0 = irrelevant

Question: {query}

Passages:
{passages}

Return ONLY a JSON array of integers (one grade per passage, in order). Example: [2,0,1,0]
"""


def _judge(query: str, passages: list[str], batch: int = 6, trunc: int = 380) -> list[int]:
    """Grade passages 0/1/2, batching to stay under the judge's context window.

    Dense datasheet text tokenizes heavily; >~4k chars per request overflows the
    loaded gemma context (400). We grade in small batches and concatenate.
    """
    grades: list[int] = []
    for start in range(0, len(passages), batch):
        chunk = passages[start : start + batch]
        numbered = "\n".join(f"[{i}] {p[:trunc]}" for i, p in enumerate(chunk))
        prompt = _JUDGE_PROMPT.format(query=query, passages=numbered)
        try:
            raw = llm_generate(prompt, role="primary", max_tokens=96).strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Judge LLM failed (batch %d): %s", start, exc)
            grades += [0] * len(chunk)
            continue
        lo, hi = raw.find("["), raw.rfind("]")
        if lo != -1 and hi != -1:
            raw = raw[lo : hi + 1]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = []
        out = [int(g) if isinstance(g, (int, float)) and int(g) in (0, 1, 2) else 0 for g in parsed]
        if len(out) < len(chunk):
            out += [0] * (len(chunk) - len(out))
        grades += out[: len(chunk)]
    return grades


def build_qrels(
    draft_path: str | Path = "data/eval/embedding_testset_draft.jsonl",
    corpus_path: str | Path = "data/eval/embedding_corpus.jsonl",
    pool_models: list[str] | None = None,
    pool_n: int = 10,
    max_new_candidates: int = 12,
    threads: int = 4,
    output_path: str | Path = QRELS_OUT,
) -> Path:
    """Pool candidates per query, LLM-grade them, merge into graded qrels."""
    pool_models = pool_models or DEFAULT_POOL_MODELS
    draft = load_qrels(draft_path)
    corpus = load_corpus(corpus_path)
    by_id = {c["chunk_id"]: c for c in corpus}
    chunk_ids = [c["chunk_id"] for c in corpus]

    queries_path = export_queries(draft_path)
    model_rank: dict[str, dict[str, list[str]]] = {}
    for key in pool_models:
        res = ensure_cached(key, corpus_path, queries_path, top_k=max(pool_n, 20), threads=threads)
        model_rank[key] = {qid: [cid for cid, _ in lst] for qid, lst in res["ranked"].items()}

    bm25 = _BM25([_tok(by_id[cid]["content"]) for cid in chunk_ids])

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n_added = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for q in draft:
            qid, query = q["qid"], q["query"]
            seed = set(q.get("relevant", {}).keys())
            pool: list[str] = []
            for key in pool_models:
                pool += model_rank[key].get(qid, [])[:pool_n]
            pool += [chunk_ids[i] for i in bm25.top_n(_tok(query), pool_n)]
            # Dedup, drop seed, cap.
            seen: set[str] = set(seed)
            candidates: list[str] = []
            for cid in pool:
                if cid not in seen and cid in by_id:
                    seen.add(cid)
                    candidates.append(cid)
                if len(candidates) >= max_new_candidates:
                    break

            relevant = {cid: int(g) for cid, g in q.get("relevant", {}).items()}
            if candidates:
                grades = _judge(query, [by_id[c]["content"] for c in candidates])
                for cid, g in zip(candidates, grades, strict=False):
                    if g > 0:
                        relevant[cid] = max(relevant.get(cid, 0), g)
                        n_added += 1

            merged = dict(q)
            merged["relevant"] = relevant
            merged["pooled_models"] = pool_models
            merged["verified"] = False
            out.write(json.dumps(merged, ensure_ascii=False) + "\n")

    logger.info("Pooled qrels written (%d added relevant labels) -> %s", n_added, output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pool + grade qrels")
    parser.add_argument("--draft", default="data/eval/embedding_testset_draft.jsonl")
    parser.add_argument("--corpus", default="data/eval/embedding_corpus.jsonl")
    parser.add_argument("--pool-models", default=",".join(DEFAULT_POOL_MODELS))
    parser.add_argument("--pool-n", type=int, default=10)
    parser.add_argument("--max-new", type=int, default=12)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--out", default=str(QRELS_OUT))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pool_models = [m.strip() for m in args.pool_models.split(",") if m.strip()]
    build_qrels(args.draft, args.corpus, pool_models, args.pool_n, args.max_new, args.threads, args.out)


if __name__ == "__main__":
    main()
