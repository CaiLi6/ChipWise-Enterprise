"""Smoke tests for Gradio app (§6A1)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
class TestGradioAppSmoke:
    def test_module_importable(self) -> None:
        """The gradio_app module must be importable without errors."""
        import frontend.gradio_app as app_mod  # noqa: F401
        assert hasattr(app_mod, "create_gradio_app")

    def test_create_gradio_app_without_gradio(self, monkeypatch) -> None:
        """create_gradio_app returns None when gradio is not installed."""
        import frontend.gradio_app as app_mod
        monkeypatch.setattr(app_mod, "_HAS_GRADIO", False)
        result = app_mod.create_gradio_app()
        assert result is None

    def test_create_gradio_app_with_gradio(self) -> None:
        """When gradio is available, create_gradio_app returns a Blocks instance."""
        try:
            import gradio as gr
        except ImportError:
            pytest.skip("gradio not installed")

        import frontend.gradio_app as app_mod
        app = app_mod.create_gradio_app(api_base="http://localhost:8080")
        assert app is not None
        assert isinstance(app, gr.Blocks)

    def test_main_function_exists(self) -> None:
        import frontend.gradio_app as app_mod
        assert callable(app_mod.main)
