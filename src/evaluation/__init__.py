"""RAG evaluation module — metrics, runners, aggregation, storage."""

from src.evaluation.storage import (
    EvaluationRecord,
    append_batch,
    append_evaluation,
    load_batches,
    load_evaluations,
)

__all__ = [
    "EvaluationRecord",
    "append_evaluation",
    "load_evaluations",
    "load_batches",
    "append_batch",
]
