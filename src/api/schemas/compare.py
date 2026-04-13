"""Pydantic schemas for chip compare API (§4A2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """Request body for POST /api/v1/compare."""

    chip_names: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2-5 chip part numbers to compare",
    )
    dimensions: list[str] | None = Field(
        default=None,
        description="Optional parameter category filter (electrical, timing, thermal)",
    )


class CompareResponse(BaseModel):
    """Response body for POST /api/v1/compare."""

    comparison_table: dict[str, Any] = Field(default_factory=dict)
    analysis: str = ""
    chips: list[str] = Field(default_factory=list)
    citations: list[Any] = Field(default_factory=list)
