"""Smoke test: verify all top-level packages can be imported."""

import pytest


@pytest.mark.unit
class TestSmokeImports:
    """Ensure every top-level src package is importable."""

    def test_import_api(self) -> None:
        import src.api

    def test_import_core(self) -> None:
        import src.core

    def test_import_agent(self) -> None:
        import src.agent

    def test_import_pipelines(self) -> None:
        import src.pipelines

    def test_import_ingestion(self) -> None:
        import src.ingestion

    def test_import_retrieval(self) -> None:
        import src.retrieval

    def test_import_libs(self) -> None:
        import src.libs

    def test_import_services(self) -> None:
        import src.services

    def test_import_observability(self) -> None:
        import src.observability

    def test_import_cache(self) -> None:
        import src.cache
