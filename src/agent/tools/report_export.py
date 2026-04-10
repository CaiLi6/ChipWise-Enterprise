"""ReportExportTool — Agent-callable report generation (§5D2)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools.base_tool import BaseTool
from src.core.report_engine import ReportEngine

logger = logging.getLogger(__name__)


class ReportExportTool(BaseTool):
    """Export analysis results as Word, PDF, or Excel reports."""

    def __init__(self, report_engine: ReportEngine | None = None) -> None:
        self._engine = report_engine or ReportEngine()

    @property
    def name(self) -> str:
        return "report_export"

    @property
    def description(self) -> str:
        return "Export analysis results as Word, PDF, or Excel report."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["word", "pdf", "excel"]},
                "data": {"type": "object"},
                "title": {"type": "string", "default": "ChipWise Report"},
            },
            "required": ["format", "data"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        fmt = kwargs.get("format", "")
        data = kwargs.get("data", {})
        title = kwargs.get("title", "ChipWise Report")

        generators = {
            "word": self._engine.generate_word,
            "pdf": self._engine.generate_pdf,
            "excel": self._engine.generate_excel,
        }

        if fmt not in generators:
            return {"error": f"Unsupported format: {fmt}. Use word, pdf, or excel."}

        try:
            path = generators[fmt](data, title)
            if not path:
                return {"error": f"Failed to generate {fmt} report (missing dependencies)"}
            return {"export_path": path, "format": fmt}
        except Exception:
            logger.exception("Report generation failed")
            return {"error": f"Report generation failed for format {fmt}"}
