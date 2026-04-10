"""Initialize Kùzu knowledge graph: 6 node tables + 7 relationship tables.

Schema aligned with ENTERPRISE_DEV_SPEC §4.7.4.

Usage:
    python scripts/init_kuzu.py                   # create schema
    python scripts/init_kuzu.py --verify           # verify only
    python scripts/init_kuzu.py --db-path path     # custom path
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Schema definitions (§4.7.4) ─────────────────────────────────────

NODE_TABLES = [
    "CREATE NODE TABLE IF NOT EXISTS Chip ("
    "chip_id INT64, part_number STRING, manufacturer STRING, "
    "category STRING, family STRING, status STRING, "
    "PRIMARY KEY (chip_id))",

    "CREATE NODE TABLE IF NOT EXISTS Parameter ("
    "param_id INT64, name STRING, category STRING, "
    "min_val DOUBLE, typ_val DOUBLE, max_val DOUBLE, "
    "unit STRING, condition STRING, "
    "PRIMARY KEY (param_id))",

    "CREATE NODE TABLE IF NOT EXISTS Errata ("
    "errata_id INT64, errata_code STRING, title STRING, "
    "severity STRING, status STRING, workaround STRING, "
    "affected_revisions STRING, "
    "PRIMARY KEY (errata_id))",

    "CREATE NODE TABLE IF NOT EXISTS Document ("
    "doc_id INT64, file_hash STRING, doc_type STRING, "
    "file_name STRING, "
    "PRIMARY KEY (doc_id))",

    "CREATE NODE TABLE IF NOT EXISTS DesignRule ("
    "rule_id INT64, rule_type STRING, rule_text STRING, "
    "severity STRING, "
    "PRIMARY KEY (rule_id))",

    "CREATE NODE TABLE IF NOT EXISTS Peripheral ("
    "name STRING, "
    "PRIMARY KEY (name))",
]

REL_TABLES = [
    "CREATE REL TABLE IF NOT EXISTS HAS_PARAM ("
    "FROM Chip TO Parameter, source_page INT64, source_table STRING)",

    "CREATE REL TABLE IF NOT EXISTS ALTERNATIVE ("
    "FROM Chip TO Chip, compat_type STRING, compat_score DOUBLE, "
    "is_domestic BOOL, key_differences STRING)",

    "CREATE REL TABLE IF NOT EXISTS HAS_ERRATA ("
    "FROM Chip TO Errata)",

    "CREATE REL TABLE IF NOT EXISTS ERRATA_AFFECTS ("
    "FROM Errata TO Peripheral)",

    "CREATE REL TABLE IF NOT EXISTS DOCUMENTED_IN ("
    "FROM Chip TO Document)",

    "CREATE REL TABLE IF NOT EXISTS HAS_RULE ("
    "FROM Chip TO DesignRule, source_page INT64)",

    "CREATE REL TABLE IF NOT EXISTS HAS_PERIPHERAL ("
    "FROM Chip TO Peripheral)",
]

EXPECTED_NODE_TABLES = {"Chip", "Parameter", "Errata", "Document", "DesignRule", "Peripheral"}
EXPECTED_REL_TABLES = {
    "HAS_PARAM", "ALTERNATIVE", "HAS_ERRATA", "ERRATA_AFFECTS",
    "DOCUMENTED_IN", "HAS_RULE", "HAS_PERIPHERAL",
}

# ── Init function ───────────────────────────────────────────────────


def init_knowledge_graph(db_path: str = "data/kuzu"):
    """Create the Kùzu database and all schema tables (idempotent).

    Args:
        db_path: Path to the Kùzu database directory.

    Returns:
        kuzu.Database instance.
    """
    import kuzu

    path = Path(db_path)
    # Ensure parent directory exists (kuzu creates the db directory itself)
    path.parent.mkdir(parents=True, exist_ok=True)

    db = kuzu.Database(str(path))
    conn = kuzu.Connection(db)

    # Create node tables
    for ddl in NODE_TABLES:
        conn.execute(ddl)
        table_name = ddl.split("IF NOT EXISTS")[1].split("(")[0].strip()
        print(f"  ✓ Node table: {table_name}")

    # Create relationship tables
    for ddl in REL_TABLES:
        conn.execute(ddl)
        table_name = ddl.split("IF NOT EXISTS")[1].split("(")[0].strip()
        print(f"  ✓ Rel table:  {table_name}")

    print(f"\nKùzu schema initialized at {db_path}")
    return db


# ── Verify function ─────────────────────────────────────────────────


def verify_schema(db_path: str = "data/kuzu") -> bool:
    """Verify that all expected node and relationship tables exist.

    Returns:
        True if all tables exist, False otherwise.
    """
    import kuzu

    path = Path(db_path)
    if not path.exists():
        print(f"ERROR: Database path does not exist: {db_path}", file=sys.stderr)
        return False

    db = kuzu.Database(str(path))
    conn = kuzu.Connection(db)

    # Get all table names
    result = conn.execute("CALL show_tables() RETURN *")
    existing_tables: set[str] = set()
    while result.has_next():
        row = result.get_next()
        # show_tables() returns [id, name, type, database, comment]
        existing_tables.add(row[1])

    ok = True

    # Check node tables
    missing_nodes = EXPECTED_NODE_TABLES - existing_tables
    if missing_nodes:
        print(f"ERROR: Missing node tables: {missing_nodes}", file=sys.stderr)
        ok = False

    # Check relationship tables
    missing_rels = EXPECTED_REL_TABLES - existing_tables
    if missing_rels:
        print(f"ERROR: Missing rel tables: {missing_rels}", file=sys.stderr)
        ok = False

    if ok:
        print(
            f"OK: All {len(EXPECTED_NODE_TABLES)} node tables "
            f"+ {len(EXPECTED_REL_TABLES)} rel tables exist."
        )

    return ok


# ── CLI ─────────────────────────────────────────────────────────────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Kùzu knowledge graph")
    parser.add_argument("--db-path", default="data/kuzu", help="Kùzu database path")
    parser.add_argument("--verify", action="store_true", help="Only verify, don't create")
    args = parser.parse_args()

    if args.verify:
        ok = verify_schema(args.db_path)
    else:
        init_knowledge_graph(args.db_path)
        ok = verify_schema(args.db_path)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
