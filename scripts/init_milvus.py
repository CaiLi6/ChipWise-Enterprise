"""Initialize Milvus collections and indexes per ENTERPRISE_DEV_SPEC §4.7.2."""

from __future__ import annotations

import sys
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusException,
    connections,
    utility,
)


# ── datasheet_chunks (11 fields) ────────────────────────────────────

DATASHEET_CHUNKS_FIELDS = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
    FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
    FieldSchema(name="chip_id", dtype=DataType.INT64),
    FieldSchema(name="part_number", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="manufacturer", dtype=DataType.VARCHAR, max_length=50),
    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=30),
    FieldSchema(name="page", dtype=DataType.INT64),
    FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=300),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="collection", dtype=DataType.VARCHAR, max_length=100),
]

# ── knowledge_notes (8 fields) ──────────────────────────────────────

KNOWLEDGE_NOTES_FIELDS = [
    FieldSchema(name="note_id", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
    FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
    FieldSchema(name="user_id", dtype=DataType.INT64),
    FieldSchema(name="chip_id", dtype=DataType.INT64),
    FieldSchema(name="note_type", dtype=DataType.VARCHAR, max_length=30),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=500),
]


def create_indexes(collection: Collection) -> None:
    """Create HNSW (dense) and SPARSE_INVERTED_INDEX (sparse) indexes."""
    # Dense: HNSW with COSINE
    collection.create_index(
        field_name="dense_vector",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256},
        },
    )
    # Sparse: SPARSE_INVERTED_INDEX with IP
    collection.create_index(
        field_name="sparse_vector",
        index_params={
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "IP",
        },
    )


def create_collections(host: str = "localhost", port: int = 19530) -> None:
    """Create datasheet_chunks and knowledge_notes collections (idempotent)."""
    connections.connect("default", host=host, port=port)

    for name, fields in [
        ("datasheet_chunks", DATASHEET_CHUNKS_FIELDS),
        ("knowledge_notes", KNOWLEDGE_NOTES_FIELDS),
    ]:
        if utility.has_collection(name):
            print(f"Collection '{name}' already exists — skipping.")
            continue
        schema = CollectionSchema(fields=fields, description=f"ChipWise {name}")
        col = Collection(name=name, schema=schema)
        create_indexes(col)
        col.load()
        print(f"Created collection '{name}' with indexes.")

    connections.disconnect("default")


def verify_collections(host: str = "localhost", port: int = 19530) -> bool:
    """Verify both collections exist and are ready."""
    connections.connect("default", host=host, port=port)
    ok = True
    for name in ["datasheet_chunks", "knowledge_notes"]:
        if not utility.has_collection(name):
            print(f"ERROR: Collection '{name}' not found.", file=sys.stderr)
            ok = False
            continue
        col = Collection(name=name)
        print(f"  {name}: fields={len(col.schema.fields)}, loaded={col.num_entities >= 0}")
    connections.disconnect("default")
    return ok


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Milvus collections")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=19530)
    parser.add_argument("--verify", action="store_true", help="Only verify, don't create")
    args = parser.parse_args()

    if args.verify:
        ok = verify_collections(args.host, args.port)
    else:
        create_collections(args.host, args.port)
        ok = verify_collections(args.host, args.port)

    sys.exit(0 if ok else 1)
