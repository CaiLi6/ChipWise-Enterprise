"""Unit tests for ReportEngine Word/PDF/Excel generation (§5D1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.core.report_engine import ReportEngine

_DATA = {
    "summary": "STM32F407 is an ARM Cortex-M4 MCU running at 168MHz.",
    "analysis": "Suitable for high-performance embedded applications.",
    "comparison_table": {
        "VCC": {"STM32F407": {"typ": "3.3", "unit": "V"}, "GD32F407": {"typ": "3.3", "unit": "V"}},
        "Frequency": {"STM32F407": {"typ": "168", "unit": "MHz"}, "GD32F407": {"typ": "120", "unit": "MHz"}},
    },
}


@pytest.fixture
def engine(tmp_path: Path) -> ReportEngine:
    return ReportEngine(output_dir=str(tmp_path))


@pytest.mark.unit
class TestReportEngineExcel:
    def test_generate_excel_creates_file(self, engine: ReportEngine) -> None:
        path = engine.generate_excel(_DATA, title="STM32 Report")
        assert path
        assert Path(path).exists()
        assert path.endswith(".xlsx")

    def test_generate_excel_empty_data(self, engine: ReportEngine) -> None:
        path = engine.generate_excel({}, title="Empty")
        assert path
        assert Path(path).exists()


@pytest.mark.unit
class TestReportEngineWord:
    def test_generate_word_creates_file(self, engine: ReportEngine) -> None:
        try:
            import docx  # noqa: F401
        except ImportError:
            pytest.skip("python-docx not installed")

        path = engine.generate_word(_DATA, title="STM32 Report")
        assert path
        assert Path(path).exists()
        assert path.endswith(".docx")

    def test_generate_word_empty_data(self, engine: ReportEngine) -> None:
        try:
            import docx  # noqa: F401
        except ImportError:
            pytest.skip("python-docx not installed")

        path = engine.generate_word({}, title="Empty Report")
        assert path
        assert Path(path).exists()

    def test_generate_word_missing_dep_returns_empty(self, engine: ReportEngine, monkeypatch) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("No module named 'docx'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        path = engine.generate_word(_DATA, title="Test")
        assert path == ""


@pytest.mark.unit
class TestReportEnginePDF:
    def test_generate_pdf_missing_dep_returns_empty(self, engine: ReportEngine, monkeypatch) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "reportlab.lib.pagesizes":
                raise ImportError("No module named 'reportlab'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        path = engine.generate_pdf(_DATA, title="Test")
        assert path == ""


@pytest.mark.unit
class TestOutputDirectory:
    def test_output_dir_auto_created(self, tmp_path: Path) -> None:
        nested = str(tmp_path / "nested" / "dir")
        _engine = ReportEngine(output_dir=nested)
        assert Path(nested).exists()

    def test_excel_file_in_output_dir(self, tmp_path: Path) -> None:
        engine = ReportEngine(output_dir=str(tmp_path))
        path = engine.generate_excel(_DATA)
        assert str(tmp_path) in path
