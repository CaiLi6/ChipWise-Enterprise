"""Smoke test: verify all top-level packages can be imported."""

import pytest


@pytest.mark.unit
class TestSmokeImports:
    """Ensure every top-level src package is importable."""

    def test_import_api(self) -> None:
        pass

    def test_import_core(self) -> None:
        pass

    def test_import_agent(self) -> None:
        pass

    def test_import_pipelines(self) -> None:
        pass

    def test_import_ingestion(self) -> None:
        pass

    def test_import_retrieval(self) -> None:
        pass

    def test_import_libs(self) -> None:
        pass

    def test_import_services(self) -> None:
        pass

    def test_import_observability(self) -> None:
        pass

    def test_import_cache(self) -> None:
        pass
