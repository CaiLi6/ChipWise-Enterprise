"""Unit tests for ReportExportTool (§5D2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from src.agent.tools.report_export import ReportExportTool
from src.core.report_engine import ReportEngine


@pytest.fixture
def engine_mock(tmp_path: Path) -> MagicMock:
    mock = MagicMock(spec=ReportEngine)
    mock.generate_word.return_value = str(tmp_path / "report.docx")
    mock.generate_pdf.return_value = str(tmp_path / "report.pdf")
    mock.generate_excel.return_value = str(tmp_path / "report.xlsx")
    return mock


@pytest.fixture
def tool(engine_mock: MagicMock) -> ReportExportTool:
    return ReportExportTool(report_engine=engine_mock)


@pytest.mark.unit
class TestReportExportTool:
    def test_name(self, tool: ReportExportTool) -> None:
        assert tool.name == "report_export"

    def test_schema_requires_format_and_data(self, tool: ReportExportTool) -> None:
        schema = tool.parameters_schema
        assert "format" in schema["required"]
        assert "data" in schema["required"]

    def test_schema_format_enum(self, tool: ReportExportTool) -> None:
        schema = tool.parameters_schema
        allowed = schema["properties"]["format"]["enum"]
        assert set(allowed) == {"word", "pdf", "excel"}

    @pytest.mark.asyncio
    async def test_excel_export(self, tool: ReportExportTool, tmp_path: Path) -> None:
        result = await tool.execute(format="excel", data={"summary": "test"})
        assert "export_path" in result
        assert result["format"] == "excel"

    @pytest.mark.asyncio
    async def test_word_export(self, tool: ReportExportTool) -> None:
        result = await tool.execute(format="word", data={"summary": "test"})
        assert result["format"] == "word"

    @pytest.mark.asyncio
    async def test_pdf_export(self, tool: ReportExportTool) -> None:
        result = await tool.execute(format="pdf", data={"summary": "test"})
        assert result["format"] == "pdf"

    @pytest.mark.asyncio
    async def test_invalid_format_returns_error(self, tool: ReportExportTool) -> None:
        result = await tool.execute(format="pptx", data={})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_data_does_not_raise(self, tool: ReportExportTool) -> None:
        result = await tool.execute(format="excel", data={})
        assert "export_path" in result

    @pytest.mark.asyncio
    async def test_engine_failure_returns_error(self, engine_mock: MagicMock) -> None:
        engine_mock.generate_excel.side_effect = RuntimeError("Disk full")
        tool = ReportExportTool(report_engine=engine_mock)
        result = await tool.execute(format="excel", data={})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_engine_returns_empty_string_is_error(self, engine_mock: MagicMock) -> None:
        engine_mock.generate_word.return_value = ""  # missing dependency
        tool = ReportExportTool(report_engine=engine_mock)
        result = await tool.execute(format="word", data={})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_custom_title_passed_to_engine(self, tool: ReportExportTool, engine_mock: MagicMock) -> None:
        await tool.execute(format="excel", data={}, title="My Custom Report")
        engine_mock.generate_excel.assert_called_once_with(
            {}, "My Custom Report"
        )

    @pytest.mark.asyncio
    async def test_default_title_used(self, tool: ReportExportTool, engine_mock: MagicMock) -> None:
        await tool.execute(format="excel", data={})
        call_args = engine_mock.generate_excel.call_args[0]
        assert "ChipWise" in call_args[1]
