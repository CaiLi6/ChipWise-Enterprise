"""Qrels generator — LLM-based golden retrieval ground truth drafting."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_GENERATION_PROMPT = """\
You are a technical documentation expert. Given the following datasheet section,
generate {per_doc} question-answer pairs that a hardware engineer might ask.

For each pair, provide:
- "query": the natural-language question
- "chip": the chip model name mentioned (if any)
- "relevant_sections": list of section titles this answer comes from
- "expected_keywords": 3-5 key terms that MUST appear in the source text
- "expected_answer_snippet": a 1-2 sentence ground-truth answer

IMPORTANT: Every keyword in expected_keywords MUST appear verbatim in the
source text below. Do not hallucinate terms.

Source section title: {section_title}
Source text:
{section_text}

Respond with a JSON array of objects. No markdown, just raw JSON.
"""


def generate_qrels_draft(
    corpus_dir: str | Path,
    output_path: str | Path,
    per_doc: int = 2,
) -> Path:
    """Generate draft qrels from corpus PDFs using the primary LLM.

    Args:
        corpus_dir: Directory containing sampled PDF files.
        output_path: Output JSONL file path.
        per_doc: Number of QA pairs to generate per document.

    Returns:
        Path to the generated draft JSONL file.
    """
    corpus_dir = Path(corpus_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdfs = list(corpus_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning("No PDF files found in %s", corpus_dir)
        return output_path

    all_qrels: list[dict[str, Any]] = []
    qid_counter = 1

    for pdf_path in pdfs:
        logger.info("Processing: %s", pdf_path.name)
        sections = _extract_sections(pdf_path)

        for section_title, section_text in sections[:5]:  # max 5 sections per doc
            if len(section_text.strip()) < 100:
                continue

            pairs = _call_llm_for_pairs(section_title, section_text, per_doc)

            for pair in pairs:
                # Validate keywords exist in source text
                keywords = pair.get("expected_keywords", [])
                valid_kw = [kw for kw in keywords if kw.lower() in section_text.lower()]
                if len(valid_kw) < len(keywords) * 0.5:
                    logger.debug("Discarding pair — too many hallucinated keywords")
                    continue

                pair["expected_keywords"] = valid_kw
                pair["qid"] = f"q{qid_counter:03d}"
                pair["source"] = "llm_draft"
                pair.setdefault("relevant_doc_ids", [])
                all_qrels.append(pair)
                qid_counter += 1

    with open(output_path, "w", encoding="utf-8") as f:
        for qrel in all_qrels:
            f.write(json.dumps(qrel, ensure_ascii=False) + "\n")

    logger.info("Generated %d draft qrels → %s", len(all_qrels), output_path)
    return output_path


def _extract_sections(pdf_path: Path) -> list[tuple[str, str]]:
    """Extract text sections from a PDF."""
    try:
        import pdfplumber

        sections: list[tuple[str, str]] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    # Use first line as title approximation
                    lines = text.strip().split("\n")
                    title = lines[0][:80] if lines else ""
                    sections.append((title, text))
        return sections
    except Exception as e:
        logger.error("Failed to extract %s: %s", pdf_path, e)
        return []


def _call_llm_for_pairs(
    section_title: str, section_text: str, per_doc: int
) -> list[dict[str, Any]]:
    """Call the primary LLM to generate QA pairs."""
    try:
        from src.libs.llm.factory import create_llm

        llm = create_llm("primary")
        prompt = _GENERATION_PROMPT.format(
            per_doc=per_doc,
            section_title=section_title,
            section_text=section_text[:3000],  # Truncate to fit context
        )
        response = llm.generate(prompt)
        # Parse JSON from response
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        logger.warning("LLM qrels generation failed: %s", e)
        return []


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate draft qrels from corpus")
    parser.add_argument("--corpus", required=True, help="Corpus snapshot directory")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--per-doc", type=int, default=2, help="QA pairs per document")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    generate_qrels_draft(args.corpus, args.out, args.per_doc)


if __name__ == "__main__":
    main()
