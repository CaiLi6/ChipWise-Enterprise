"""Build a frozen, shared chunk corpus from real datasheet PDFs.

The corpus is produced ONCE with the project's ``datasheet`` chunker and reused
identically by every model, so the only variable in the benchmark is the
embedding model. Output: ``data/eval/embedding_corpus.jsonl`` (+ manifest).
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CORPUS_PATH = Path("data/eval/embedding_corpus.jsonl")
MANIFEST_PATH = Path("data/eval/embedding_corpus_manifest.json")


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return s[:48] or "doc"


def _extract_text(pdf_path: Path, max_pages: int) -> str:
    """Extract text from a PDF, page by page (pdfplumber)."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages[:max_pages]:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
    return "\n\n".join(parts)


def build_corpus(
    docs_dir: str | Path = "data/documents",
    limit: int = 60,
    max_pages: int = 40,
    seed: int = 1234,
    output_path: str | Path = CORPUS_PATH,
) -> Path:
    """Extract + chunk a seeded sample of PDFs into a frozen corpus JSONL.

    Args:
        docs_dir: Root directory to search recursively for ``*.pdf``.
        limit: Number of documents to sample (seeded, deterministic).
        max_pages: Cap pages per PDF to bound extraction cost.
        seed: RNG seed for the document sample.
        output_path: Output JSONL path.

    Returns:
        Path to the corpus JSONL.
    """
    from src.ingestion.chunking.factory import create_chunker

    docs_dir = Path(docs_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(docs_dir.rglob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found under {docs_dir}")
    rng = random.Random(seed)
    if limit and limit < len(pdfs):
        pdfs = rng.sample(pdfs, limit)
    pdfs.sort()
    logger.info("Sampled %d PDFs from %s", len(pdfs), docs_dir)

    chunker = create_chunker("datasheet")
    manifest: list[dict] = []
    n_chunks = 0

    with open(output_path, "w", encoding="utf-8") as out:
        for pdf in pdfs:
            doc_id = _slug(pdf.stem)
            try:
                text = _extract_text(pdf, max_pages)
            except Exception as exc:  # noqa: BLE001 — skip unreadable PDFs
                logger.warning("Failed to extract %s: %s", pdf.name, exc)
                continue
            if len(text.strip()) < 200:
                logger.warning("Too little text, skipping: %s", pdf.name)
                continue

            chunks = chunker.split(text, doc_id=doc_id)
            kept = 0
            for ch in chunks:
                content = (ch.content or "").strip()
                if len(content) < 40:
                    continue
                rec = {
                    "chunk_id": ch.chunk_id or f"{doc_id}_{ch.chunk_index}",
                    "doc_id": doc_id,
                    "chunk_index": ch.chunk_index,
                    "page_number": ch.page_number,
                    "section": ch.section,
                    "content": content,
                    "char_len": len(content),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept += 1
                n_chunks += 1
            manifest.append({"doc_id": doc_id, "file": str(pdf), "chunks": kept})
            logger.info("  %s -> %d chunks", pdf.name, kept)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Corpus: %d chunks from %d docs -> %s", n_chunks, len(manifest), output_path)
    return output_path


def load_corpus(path: str | Path = CORPUS_PATH) -> list[dict]:
    """Load the frozen corpus JSONL into a list of chunk dicts."""
    path = Path(path)
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen embedding-eval corpus")
    parser.add_argument("--docs", default="data/documents")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default=str(CORPUS_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    build_corpus(args.docs, args.limit, args.max_pages, args.seed, args.out)


if __name__ == "__main__":
    main()
