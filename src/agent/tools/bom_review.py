"""BOMReviewTool — BOM audit with EOL detection + alternatives (§4C1-4C3)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.agent.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class BOMItem:
    """A single BOM line item."""

    def __init__(
        self,
        row_number: int,
        part_number: str,
        description: str = "",
        quantity: int = 0,
        designator: str = "",
    ) -> None:
        self.row_number = row_number
        self.part_number = part_number
        self.description = description
        self.quantity = quantity
        self.designator = designator
        self.chip_id: int | None = None
        self.match_status: str = "unmatched"
        self.eol_flag: bool = False
        self.nrnd_flag: bool = False
        self.parameter_conflicts: list[dict[str, str]] = []
        self.alternative: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "part_number": self.part_number,
            "description": self.description,
            "quantity": self.quantity,
            "designator": self.designator,
            "chip_id": self.chip_id,
            "match_status": self.match_status,
            "eol_flag": self.eol_flag,
            "nrnd_flag": self.nrnd_flag,
            "parameter_conflicts": self.parameter_conflicts,
            "alternative": self.alternative,
        }


class BOMReviewTool(BaseTool):
    """Review BOM files: match chips, detect EOL, check conflicts, suggest alternatives."""

    def __init__(self, db_pool: Any = None, graph_search: Any = None) -> None:
        self._pool = db_pool
        self._graph = graph_search

    @property
    def name(self) -> str:
        return "bom_review"

    @property
    def description(self) -> str:
        return (
            "Review a BOM (Bill of Materials) file: match parts to chip database, "
            "detect EOL/NRND, check parameter conflicts, suggest alternatives."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to BOM Excel file"},
                "bom_data": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Inline BOM data (alternative to file_path)",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        file_path = kwargs.get("file_path")
        bom_data = kwargs.get("bom_data")

        # Parse BOM
        if file_path:
            items = self._parse_bom_excel(file_path)
        elif bom_data:
            items = [
                BOMItem(
                    row_number=i + 1,
                    part_number=d.get("part_number", ""),
                    description=d.get("description", ""),
                    quantity=d.get("quantity", 0),
                    designator=d.get("designator", ""),
                )
                for i, d in enumerate(bom_data)
            ]
        else:
            return {"error": "Provide file_path or bom_data"}

        if not items:
            return {"error": "No items found in BOM"}

        # Process each item
        for item in items:
            await self._match_chip(item)
            if item.chip_id:
                self._check_eol(item)
                await self._check_conflicts(item)
                if item.eol_flag or item.nrnd_flag:
                    item.alternative = await self._find_alternative(item.chip_id)

        # Summary
        matched = sum(1 for i in items if i.match_status == "matched")
        eol_warnings = sum(1 for i in items if i.eol_flag or i.nrnd_flag)
        conflicts = sum(1 for i in items if i.parameter_conflicts)

        return {
            "bom_review": {
                "total_items": len(items),
                "matched": matched,
                "unmatched": len(items) - matched,
                "eol_warnings": eol_warnings,
                "conflicts": conflicts,
            },
            "items": [i.to_dict() for i in items],
        }

    @staticmethod
    def _parse_bom_excel(file_path: str) -> list[BOMItem]:
        """Parse BOM from Excel file using openpyxl."""
        items: list[BOMItem] = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            if ws is None:
                return items

            # Find header row
            headers: dict[str, int] = {}
            for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                if row_idx == 1:
                    for col_idx, val in enumerate(row):
                        if val:
                            headers[str(val).strip().lower()] = col_idx
                    continue

                if not any(row):
                    continue  # Skip empty rows

                pn_col = headers.get("part_number", headers.get("part number", headers.get("型号", 0)))
                desc_col = headers.get("description", headers.get("描述", 0))
                qty_col = headers.get("quantity", headers.get("qty", headers.get("数量", 0)))
                des_col = headers.get("designator", headers.get("位号", 0))

                part_number = str(row[pn_col - 1]).strip() if pn_col and pn_col <= len(row) else ""
                if not part_number or part_number == "None":
                    continue

                items.append(BOMItem(
                    row_number=row_idx,
                    part_number=part_number,
                    description=str(row[desc_col - 1]).strip() if desc_col and desc_col <= len(row) else "",
                    quantity=int(row[qty_col - 1] or 0) if qty_col and qty_col <= len(row) else 0,
                    designator=str(row[des_col - 1]).strip() if des_col and des_col <= len(row) else "",
                ))
            wb.close()
        except ImportError:
            logger.error("openpyxl not installed")
        except Exception:
            logger.exception("Failed to parse BOM: %s", file_path)
        return items

    async def _match_chip(self, item: BOMItem) -> None:
        """Match a BOM part number against the chip database."""
        if not self._pool or not item.part_number:
            return

        try:
            async with self._pool.acquire() as conn:
                # Exact match
                row = await conn.fetchrow(
                    "SELECT chip_id, status FROM chips WHERE part_number = $1",
                    item.part_number,
                )
                if row:
                    item.chip_id = row["chip_id"]
                    item.match_status = "matched"
                    item._status = row["status"]
                    return

                # Prefix/fuzzy match
                row = await conn.fetchrow(
                    "SELECT chip_id, status FROM chips WHERE part_number ILIKE $1 LIMIT 1",
                    f"{item.part_number}%",
                )
                if row:
                    item.chip_id = row["chip_id"]
                    item.match_status = "ambiguous"
                    item._status = row["status"]
        except Exception:
            logger.debug("Chip match failed for %s", item.part_number)

    @staticmethod
    def _check_eol(item: BOMItem) -> None:
        """Check EOL/NRND status (§4C2)."""
        status = getattr(item, "_status", "").lower()
        if status in ("eol", "obsolete", "discontinued"):
            item.eol_flag = True
        elif status in ("nrnd", "not recommended"):
            item.nrnd_flag = True

    async def _check_conflicts(self, item: BOMItem) -> None:
        """Check BOM description vs actual chip parameters (§4C2)."""
        if not self._pool or not item.chip_id or not item.description:
            return

        # Extract claims from description (e.g., "3.3V", "100MHz", "LQFP48")
        voltage_match = re.search(r"(\d+\.?\d*)\s*V\b", item.description)
        freq_match = re.search(r"(\d+)\s*MHz\b", item.description, re.IGNORECASE)

        if not voltage_match and not freq_match:
            return

        try:
            async with self._pool.acquire() as conn:
                params = await conn.fetch(
                    "SELECT name, max_value, unit FROM chip_parameters WHERE chip_id = $1",
                    item.chip_id,
                )
                param_map = {r["name"].lower(): r for r in params}

                if voltage_match:
                    claimed_v = float(voltage_match.group(1))
                    for key in ("vcc", "vdd", "supply voltage"):
                        if key in param_map and param_map[key]["max_value"]:
                            actual_max = float(param_map[key]["max_value"])
                            if claimed_v > actual_max * 1.1:
                                item.parameter_conflicts.append({
                                    "param": key,
                                    "bom_says": f"{claimed_v}V",
                                    "actual": f"max {actual_max}V",
                                })
        except Exception:
            logger.debug("Conflict check failed for chip %s", item.chip_id)

    async def _find_alternative(self, chip_id: int) -> dict[str, Any] | None:
        """Find best alternative for an EOL chip (§4C3)."""
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT alt.part_number, alt.manufacturer, ca.compat_score, ca.key_differences "
                        "FROM chip_alternatives ca "
                        "JOIN chips alt ON ca.target_chip_id = alt.chip_id "
                        "WHERE ca.source_chip_id = $1 "
                        "ORDER BY ca.compat_score DESC LIMIT 1",
                        chip_id,
                    )
                    if row:
                        return dict(row)
            except Exception:
                logger.debug("PG alternative query failed", exc_info=True)

        if self._graph:
            try:
                alts = await self._graph.find_alternatives(str(chip_id))
                if alts:
                    return alts[0]
            except Exception:
                pass

        return None
