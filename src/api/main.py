"""FastAPI application factory."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ChipWise Enterprise",
        description="Chip data intelligence retrieval and analysis platform",
        version="0.1.0",
    )
    return app


app = create_app()
