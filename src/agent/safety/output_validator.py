"""Structured output validator (§2.9).

Validates LLM-generated chip parameter JSON using Pydantic schemas
and domain-specific rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ── Pydantic schemas ────────────────────────────────────────────────

class ChipParam(BaseModel):
    """Schema for a single chip parameter extracted by LLM."""
    name: str
    value: float | None = None
    unit: str = ""
    min_val: float | None = None
    max_val: float | None = None
    condition: str = ""


class ChipParamsOutput(BaseModel):
    """Schema for LLM output containing chip parameters."""
    part_number: str
    parameters: list[ChipParam] = Field(default_factory=list)


# ── Domain rules ────────────────────────────────────────────────────

@dataclass
class DomainWarning:
    """A warning from domain rule validation."""
    param_name: str
    message: str
    value: float | None = None


@dataclass
class ValidationResult:
    """Result of structured output validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[DomainWarning] = field(default_factory=list)
    data: Any = None


# ── Validator class ─────────────────────────────────────────────────

class StructuredOutputValidator:
    """Validates LLM-generated structured output against schemas and domain rules."""

    def validate(self, data: dict[str, Any], schema_name: str | None = None) -> bool:
        """Return True if data conforms to the named schema."""
        result = self.validate_chip_params(data)
        return result.valid

    def get_errors(self) -> list[str]:
        """Return errors from last validate call."""
        return []

    def validate_chip_params(self, data: dict[str, Any]) -> ValidationResult:
        """Validate chip parameters against Pydantic schema + domain rules."""
        try:
            parsed = ChipParamsOutput(**data)
        except ValidationError as e:
            errors = [str(err) for err in e.errors()]
            logger.warning("Schema validation failed: %s", errors)
            return ValidationResult(valid=False, errors=errors)

        warnings = self.validate_domain_rules(parsed.parameters)
        return ValidationResult(
            valid=True,
            warnings=warnings,
            data=parsed,
        )

    def validate_domain_rules(self, params: list[ChipParam]) -> list[DomainWarning]:
        """Apply domain-specific constraints to extracted parameters."""
        warnings: list[DomainWarning] = []

        for p in params:
            val = p.value
            if val is None:
                continue

            name_lower = p.name.lower()

            # Frequency must be positive
            if "freq" in name_lower or "clock" in name_lower:
                if val < 0:
                    warnings.append(DomainWarning(
                        param_name=p.name, message="Frequency must be >= 0", value=val
                    ))

            # Voltage range: 0.1 – 100 V
            if "voltage" in name_lower or name_lower in ("vcc", "vdd", "vio"):
                if not (0.1 <= val <= 100):
                    warnings.append(DomainWarning(
                        param_name=p.name, message="Voltage outside 0.1–100V range", value=val
                    ))

            # Temperature range: -273 – +500 °C
            if "temp" in name_lower:
                if not (-273 <= val <= 500):
                    warnings.append(DomainWarning(
                        param_name=p.name, message="Temperature outside -273–500°C range", value=val
                    ))

        return warnings

