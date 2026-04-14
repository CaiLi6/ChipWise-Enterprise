"""Unit tests for StructuredOutputValidator."""

from __future__ import annotations

import pytest
from src.agent.safety.output_validator import (
    ChipParam,
    StructuredOutputValidator,
)


@pytest.mark.unit
class TestStructuredOutputValidator:
    def test_valid_chip_params(self) -> None:
        v = StructuredOutputValidator()
        data = {
            "part_number": "STM32F407",
            "parameters": [
                {"name": "Clock Speed", "value": 168.0, "unit": "MHz"},
                {"name": "Vcc", "value": 3.3, "unit": "V"},
            ],
        }
        result = v.validate_chip_params(data)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_part_number(self) -> None:
        v = StructuredOutputValidator()
        data = {"parameters": [{"name": "Clock", "value": 168}]}
        result = v.validate_chip_params(data)
        assert result.valid is False
        assert len(result.errors) > 0

    def test_empty_parameters(self) -> None:
        v = StructuredOutputValidator()
        data = {"part_number": "STM32F407", "parameters": []}
        result = v.validate_chip_params(data)
        assert result.valid is True

    def test_domain_rule_negative_frequency(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Clock Frequency", value=-1.0, unit="MHz")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 1
        assert "Frequency" in warnings[0].message

    def test_domain_rule_valid_frequency(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Clock Frequency", value=168.0, unit="MHz")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 0

    def test_domain_rule_voltage_out_of_range(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Vcc Voltage", value=200.0, unit="V")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 1
        assert "Voltage" in warnings[0].message

    def test_domain_rule_voltage_valid(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Vcc Voltage", value=3.3, unit="V")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 0

    def test_domain_rule_temperature_out_of_range(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Max Temperature", value=600.0, unit="°C")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 1
        assert "Temperature" in warnings[0].message

    def test_domain_rule_temperature_valid(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Max Temperature", value=125.0, unit="°C")]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 0

    def test_validate_shortcut(self) -> None:
        v = StructuredOutputValidator()
        assert v.validate({"part_number": "X", "parameters": []}) is True
        assert v.validate({"parameters": []}) is False

    def test_no_value_skips_domain_check(self) -> None:
        v = StructuredOutputValidator()
        params = [ChipParam(name="Clock Frequency", value=None)]
        warnings = v.validate_domain_rules(params)
        assert len(warnings) == 0
