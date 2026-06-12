"""Embedding model benchmark suite (ChipWise Enterprise).

Compares text-embedding models on **retrieval accuracy**, **inference speed**, and
**deployment memory** for the Chinese-query / English-datasheet RAG scenario.

Primary axis is a dense-retrieval, apples-to-apples comparison (fixed chunk corpus,
reranker off, exact cosine search). The production BGE-M3 hybrid (dense+sparse)
configuration is reported separately as a reference point.

Run via the CLI::

    python -m evaluation.embedding.cli build-corpus --docs data/documents --limit 60
    python -m evaluation.embedding.cli build-testset --n 90
    python -m evaluation.embedding.cli pool
    python -m evaluation.embedding.cli run --models all
    python -m evaluation.embedding.cli report
"""
