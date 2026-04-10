"""Seed data script — chip alternatives CSV import (§4B3)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def import_alternatives(csv_path: str, db_pool: Any) -> int:
    """Import chip alternatives from CSV into PostgreSQL.

    CSV format: original_part,alternative_part,compat_type,compat_score,is_domestic,key_differences
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    count = 0
    async with db_pool.acquire() as conn:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    await conn.execute(
                        """
                        INSERT INTO chip_alternatives
                            (source_chip_id, target_chip_id, compat_type, compat_score, is_domestic, key_differences)
                        SELECT
                            src.chip_id, tgt.chip_id, $3, $4::float, $5::bool, $6
                        FROM chips src, chips tgt
                        WHERE src.part_number = $1 AND tgt.part_number = $2
                        ON CONFLICT (source_chip_id, target_chip_id) DO UPDATE SET
                            compat_score = EXCLUDED.compat_score,
                            key_differences = EXCLUDED.key_differences
                        """,
                        row["original_part"],
                        row["alternative_part"],
                        row.get("compat_type", "pin_compatible"),
                        float(row.get("compat_score", 0.5)),
                        row.get("is_domestic", "false").lower() == "true",
                        row.get("key_differences", ""),
                    )
                    count += 1
                except Exception:
                    logger.warning("Failed to import row: %s", row)

    return count


if __name__ == "__main__":
    import asyncio
    import sys

    csv_file = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/chip_alternatives_sample.csv"
    print(f"Import from {csv_file} — requires running PG")
