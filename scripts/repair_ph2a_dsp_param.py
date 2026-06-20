"""Repair PH2A106FLG900 DSP quantity extracted as NULL.

Source: PH2A106FLG900 & XCKU5PFFVD900 compatibility guide, table 2-7
``DSP功能对比`` states PH2A DSP 数量 = 1,800个.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        database=os.environ.get("PG_DATABASE", "chipwise"),
        user=os.environ.get("PG_USER", "chipwise"),
        password=os.environ.get("PG_PASSWORD", ""),
    )
    try:
        chip = await conn.fetchrow(
            "SELECT id FROM chips WHERE upper(part_number)=upper($1)",
            "PH2A106FLG900",
        )
        if chip is None:
            raise RuntimeError("PH2A106FLG900 not found in chips")
        row = await conn.fetchrow(
            """
            UPDATE chip_parameters
               SET typ_value = 1800,
                   unit = '个',
                   condition = COALESCE(
                       condition,
                       'From compatibility guide table 2-7 DSP功能对比'
                   )
             WHERE chip_id = $1
               AND parameter_name = 'DSP'
            RETURNING parameter_name, typ_value, unit, source_page, source_table
            """,
            int(chip["id"]),
        )
        if row is None:
            raise RuntimeError("DSP parameter row not found for PH2A106FLG900")
        print(dict(row))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
