"""Draft a bilingual test set from the frozen corpus using the primary LLM.

For each sampled chunk the LLM drafts question/answer pairs grounded in that
chunk. We keep only pairs whose ``expected_keywords`` appear verbatim in the
source chunk (anti-hallucination), tag a query category, and seed the source
chunk as graded-relevant (gain=2). Pooling (see :mod:`pooling`) later adds any
additional relevant chunks before human review.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from evaluation.embedding._config import llm_generate
from evaluation.embedding.corpus import load_corpus

logger = logging.getLogger(__name__)

DRAFT_PATH = Path("data/eval/embedding_testset_draft.jsonl")

CATEGORIES = [
    "numeric", "table_lookup", "comparison", "feature_availability",
    "package_pinout", "errata_limit", "general",
]

_PROMPT = """\
You are a senior semiconductor hardware engineer writing retrieval test questions
for a chip-datasheet search engine. Below is ONE text chunk from a real datasheet.

Generate exactly {n} question/answer pairs that an engineer could answer ONLY from
this chunk. Make them realistic and specific (parameters, limits, pin/package,
features, min/typ/max values, interface widths, frequencies, voltages, etc.).

Language requirement: produce {n_zh} question(s) in **Chinese** and {n_en} in
**English** (the source text is English; Chinese questions test cross-lingual retrieval).

For EACH pair return an object with:
- "query": the question (in the required language)
- "lang": "zh" or "en"
- "category": one of {categories}
- "expected_keywords": 2-5 SHORT tokens (numbers/units/identifiers) that appear
  VERBATIM in the source text below (do NOT invent terms)
- "expected_answer": a 1-2 sentence ground-truth answer

Return ONLY a raw JSON array. No markdown fences, no commentary.

Source text:
\"\"\"
{chunk}
\"\"\"
"""


def _digit_density(text: str) -> float:
    if not text:
        return 0.0
    return sum(c.isdigit() for c in text) / len(text)


def _select_chunks(corpus: list[dict], n_chunks: int, seed: int) -> list[dict]:
    """Pick spec-dense, doc-diverse chunks (seeded, deterministic)."""
    rng = random.Random(seed)
    # Rank by digit density (spec-like), keep doc diversity by round-robin.
    by_doc: dict[str, list[dict]] = {}
    for ch in corpus:
        if ch["char_len"] < 120:
            continue
        by_doc.setdefault(ch["doc_id"], []).append(ch)
    for docid in by_doc:
        by_doc[docid].sort(key=lambda c: _digit_density(c["content"]), reverse=True)

    docs = list(by_doc.keys())
    rng.shuffle(docs)
    selected: list[dict] = []
    rank = 0
    while len(selected) < n_chunks and docs:
        progressed = False
        for docid in docs:
            bucket = by_doc[docid]
            if rank < len(bucket):
                selected.append(bucket[rank])
                progressed = True
                if len(selected) >= n_chunks:
                    break
        if not progressed:
            break
        rank += 1
    return selected


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def build_testset(
    target_n: int = 90,
    per_chunk: int = 2,
    seed: int = 1234,
    corpus_path: str | Path | None = None,
    output_path: str | Path = DRAFT_PATH,
) -> Path:
    """Generate the draft test set JSONL grounded in the frozen corpus."""
    corpus = load_corpus(corpus_path) if corpus_path else load_corpus()
    by_id = {c["chunk_id"]: c for c in corpus}
    n_chunks = (target_n // per_chunk) + 8  # over-sample for validation drops
    chunks = _select_chunks(corpus, n_chunks, seed)
    logger.info("Drafting from %d chunks (target %d questions)", len(chunks), target_n)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_zh = (per_chunk + 1) // 2
    n_en = per_chunk - n_zh
    qid = 1
    written = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for ch in chunks:
            if written >= target_n:
                break
            prompt = _PROMPT.format(
                n=per_chunk, n_zh=n_zh, n_en=n_en,
                categories=CATEGORIES, chunk=ch["content"][:2800],
            )
            try:
                raw = llm_generate(prompt, role="primary", max_tokens=1024)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM draft failed for %s: %s", ch["chunk_id"], exc)
                continue

            for pair in _parse_json_array(raw):
                rec = _validate_pair(pair, ch, by_id, qid)
                if rec is None:
                    continue
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                qid += 1
                written += 1
                if written >= target_n:
                    break
    logger.info("Wrote %d draft questions -> %s", written, output_path)
    return output_path


def _validate_pair(pair: dict, chunk: dict, by_id: dict, qid: int) -> dict[str, Any] | None:
    query = (pair.get("query") or "").strip()
    if len(query) < 5:
        return None
    keywords = [str(k).strip() for k in pair.get("expected_keywords", []) if str(k).strip()]
    src = chunk["content"].lower()
    valid_kw = [k for k in keywords if k.lower() in src]
    # Require majority of keywords to be verbatim-grounded in the source chunk.
    if not valid_kw or len(valid_kw) < max(1, len(keywords) * 0.5):
        return None
    category = pair.get("category") if pair.get("category") in CATEGORIES else "general"
    lang_val = pair.get("lang")
    if lang_val not in ("zh", "en"):
        lang_val = "zh" if re.search(r"[\u4e00-\u9fff]", query) else "en"
    return {
        "qid": f"q{qid:03d}",
        "query": query,
        "lang": lang_val,
        "category": category,
        "expected_keywords": valid_kw,
        "expected_answer": (pair.get("expected_answer") or "").strip(),
        "source_chunk_id": chunk["chunk_id"],
        "source_doc_id": chunk["doc_id"],
        "relevant": {chunk["chunk_id"]: 2},
        "verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft bilingual embedding test set")
    parser.add_argument("--n", type=int, default=90, help="Target number of questions")
    parser.add_argument("--per-chunk", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--out", default=str(DRAFT_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    build_testset(args.n, args.per_chunk, args.seed, args.corpus, args.out)


if __name__ == "__main__":
    main()
