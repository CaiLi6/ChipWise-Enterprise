"""Layer 3 RAGAS adapter — maps ChipWise evaluation data to RAGAS schema.

Uses the local LM Studio endpoint as the RAGAS judge model.
Only activated with ``--ragas`` flag (expensive).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def evaluate_ragas(
    queries: list[dict[str, Any]],
) -> list[dict[str, float]]:
    """Run RAGAS metrics on a batch of query results.

    Each item in *queries* must have keys:
        - question: str
        - contexts: list[str]
        - answer: str
        - ground_truth: str  (expected_answer_snippet)

    Returns:
        List of dicts with RAGAS metric scores per query.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            answer_correctness,
            answer_relevancy,
            context_precision,
            faithfulness,
        )
    except ImportError:
        logger.error(
            "RAGAS dependencies not installed. Run: pip install ragas datasets"
        )
        return [{}] * len(queries)

    dataset = _build_dataset(queries)
    if dataset is None:
        return [{}] * len(queries)

    try:
        llm = _get_ragas_llm()
        embeddings = _get_ragas_embeddings()

        metrics = [context_precision, faithfulness, answer_relevancy, answer_correctness]

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
        )

        df = result.to_pandas()
        return df.to_dict(orient="records")

    except Exception as e:
        logger.error("RAGAS evaluation failed: %s", e)
        return [{}] * len(queries)


def _build_dataset(queries: list[dict[str, Any]]) -> Any:
    """Convert query results to RAGAS Dataset."""
    try:
        from datasets import Dataset

        data = {
            "question": [],
            "contexts": [],
            "answer": [],
            "ground_truth": [],
        }
        for q in queries:
            data["question"].append(q.get("question", ""))
            data["contexts"].append(q.get("contexts", []))
            data["answer"].append(q.get("answer", ""))
            data["ground_truth"].append(q.get("ground_truth", ""))

        return Dataset.from_dict(data)
    except Exception as e:
        logger.error("Failed to build RAGAS dataset: %s", e)
        return None


def _get_ragas_llm() -> Any:
    """Create a RAGAS-compatible LLM wrapper pointing at LM Studio."""
    try:
        from langchain_openai import ChatOpenAI

        from src.core.settings import load_settings

        settings = load_settings()
        cfg = settings.llm.primary

        llm = ChatOpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=cfg.model,
            temperature=0.0,
        )
        return llm
    except Exception as e:
        logger.warning("Failed to create RAGAS LLM: %s", e)
        return None


def _get_ragas_embeddings() -> Any:
    """Create a RAGAS-compatible embedding wrapper pointing at BGE-M3."""
    try:
        from langchain_openai import OpenAIEmbeddings

        from src.core.settings import load_settings

        settings = load_settings()
        cfg = settings.embedding

        return OpenAIEmbeddings(
            base_url=cfg.base_url,
            api_key="not-needed",
            model=cfg.model,
        )
    except Exception as e:
        logger.warning("Failed to create RAGAS embeddings: %s", e)
        return None
