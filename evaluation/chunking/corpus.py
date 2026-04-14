"""Corpus sampler — snapshot documents from production PG for evaluation."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def sample_from_production(
    n: int = 30,
    output_dir: str | Path = "data/eval_corpus",
) -> Path:
    """Sample *n* documents from the production PostgreSQL ``documents`` table.

    Copies the original files to ``output_dir/<timestamp>/`` and writes an
    ``eval_corpus_manifest.json`` mapping doc_id → sha256 → local path.

    Returns:
        The snapshot directory path.
    """
    output_dir = Path(output_dir)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    snapshot_dir = output_dir / ts
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    rows = _query_documents(n)
    manifest: list[dict[str, Any]] = []
    copied = 0

    for row in rows:
        doc_id, file_path, sha256 = row["doc_id"], row["file_path"], row["sha256"]
        src = Path(file_path)
        if not src.exists():
            logger.warning("File not accessible, skipping: %s", file_path)
            continue
        dest = snapshot_dir / src.name
        # Handle name collision
        if dest.exists():
            dest = snapshot_dir / f"{doc_id}_{src.name}"
        shutil.copy2(src, dest)
        manifest.append({
            "doc_id": doc_id,
            "sha256": sha256,
            "original_path": str(src),
            "snapshot_path": str(dest),
        })
        copied += 1

    manifest_path = snapshot_dir / "eval_corpus_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info("Sampled %d/%d documents → %s", copied, n, snapshot_dir)
    return snapshot_dir


def _query_documents(n: int) -> list[dict[str, str]]:
    """Query PG documents table for random sample."""
    try:
        from sqlalchemy import text as sa_text

        from src.core.settings import load_settings

        settings = load_settings()
        db = settings.database
        url = f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"

        from sqlalchemy import create_engine

        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(
                sa_text("SELECT doc_id, file_path, file_hash AS sha256 FROM documents ORDER BY RANDOM() LIMIT :n"),
                {"n": n},
            )
            return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error("Cannot query production PG: %s", e)
        return []


def _build_manifest_from_dir(corpus_dir: Path) -> list[dict[str, str]]:
    """Build a manifest from all PDF files already present in *corpus_dir*."""
    import hashlib

    manifest: list[dict[str, str]] = []
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        sha256 = hashlib.sha256(pdf.read_bytes()).hexdigest()
        manifest.append({
            "doc_id": sha256[:16],
            "sha256": sha256,
            "original_path": str(pdf),
            "snapshot_path": str(pdf),
        })
    return manifest


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Sample eval corpus from production PG")
    parser.add_argument("--sample", type=int, default=30, help="Number of documents to sample")
    parser.add_argument("--out", type=str, default="data/eval_corpus", help="Output directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    snapshot = sample_from_production(n=args.sample, output_dir=args.out)
    print(f"Corpus snapshot: {snapshot}")


if __name__ == "__main__":
    main()
