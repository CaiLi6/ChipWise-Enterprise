"""Migrate existing Milvus collections to add BM25 full-text search support.

Milvus does not allow adding Functions to existing collections, so this script:
1. Renames the old collection to {name}_pre_bm25
2. Creates a new collection with the BM25-enabled schema
3. Copies data from the old collection to the new one
4. Drops the old collection after verification

Usage:
    python scripts/migrate_bm25.py [--host localhost] [--port 19530] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from pymilvus import (
    Collection,
    connections,
    utility,
)

COLLECTIONS = ["datasheet_chunks", "knowledge_notes"]
BATCH_SIZE = 1000


def _collection_has_bm25(name: str) -> bool:
    """Check if a collection already has the bm25_vector field."""
    if not utility.has_collection(name):
        return False
    col = Collection(name)
    return any(f.name == "bm25_vector" for f in col.schema.fields)


def _get_output_fields(col: Collection) -> list[str]:
    """Get all non-vector field names for data copy (vectors are auto-handled)."""
    skip = {"bm25_vector"}
    return [f.name for f in col.schema.fields if f.name not in skip]


def migrate_collection(name: str, dry_run: bool = False) -> bool:
    """Migrate a single collection to BM25-enabled schema."""
    if not utility.has_collection(name):
        print(f"  Collection '{name}' does not exist — skipping.")
        return True

    if _collection_has_bm25(name):
        print(f"  Collection '{name}' already has bm25_vector — skipping.")
        return True

    old_name = f"{name}_pre_bm25"
    old_col = Collection(name)
    num_entities = old_col.num_entities
    print(f"  Collection '{name}': {num_entities} entities to migrate.")

    if dry_run:
        print(f"  [DRY RUN] Would rename '{name}' → '{old_name}', recreate, copy data.")
        return True

    # Step 1: Rename old collection
    if utility.has_collection(old_name):
        print(f"  WARNING: '{old_name}' already exists — previous migration may have failed.")
        print(f"  Please manually inspect and drop '{old_name}' before retrying.")
        return False

    utility.rename_collection(name, old_name)
    print(f"  Renamed '{name}' → '{old_name}'.")

    # Step 2: Create new collection with BM25 schema (via init_milvus)
    from init_milvus import DATASHEET_CHUNKS_FIELDS, KNOWLEDGE_NOTES_FIELDS, create_indexes
    from pymilvus import CollectionSchema, Function, FunctionType

    fields_map = {
        "datasheet_chunks": DATASHEET_CHUNKS_FIELDS,
        "knowledge_notes": KNOWLEDGE_NOTES_FIELDS,
    }
    fields = fields_map[name]
    bm25_fn = Function(
        name="text_bm25",
        function_type=FunctionType.BM25,
        input_field_names=["content"],
        output_field_names=["bm25_vector"],
    )
    schema = CollectionSchema(fields=fields, functions=[bm25_fn], description=f"ChipWise {name}")
    new_col = Collection(name=name, schema=schema)
    create_indexes(new_col)
    print(f"  Created new '{name}' with BM25 schema and indexes.")

    # Step 3: Copy data in batches
    old_col = Collection(old_name)
    old_col.load()
    output_fields = _get_output_fields(old_col)

    copied = 0
    # Use iterator-style pagination via query with offset
    while copied < num_entities:
        batch = old_col.query(
            expr="",
            output_fields=output_fields,
            limit=BATCH_SIZE,
            offset=copied,
        )
        if not batch:
            break
        new_col.insert(batch)
        copied += len(batch)
        print(f"  Copied {copied}/{num_entities} entities...")

    new_col.flush()
    new_col.load()

    # Step 4: Verify
    new_count = new_col.num_entities
    if new_count < num_entities:
        print(f"  WARNING: New collection has {new_count} entities, expected {num_entities}.")
        print(f"  Old collection '{old_name}' preserved for manual inspection.")
        return False

    # Step 5: Drop old collection
    utility.drop_collection(old_name)
    print(f"  Dropped '{old_name}'. Migration complete for '{name}'.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Milvus collections for BM25 support")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=19530)
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    args = parser.parse_args()

    connections.connect("default", host=args.host, port=args.port)
    print(f"Connected to Milvus at {args.host}:{args.port}")

    if args.dry_run:
        print("[DRY RUN MODE]")

    all_ok = True
    for name in COLLECTIONS:
        print(f"\nMigrating '{name}'...")
        ok = migrate_collection(name, dry_run=args.dry_run)
        if not ok:
            all_ok = False

    connections.disconnect("default")

    if all_ok:
        print("\nAll migrations completed successfully.")
    else:
        print("\nSome migrations failed — see warnings above.", file=sys.stderr)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
