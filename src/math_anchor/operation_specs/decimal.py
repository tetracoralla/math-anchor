from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _object,
    rounding,
)


SPECS = (
    OperationSpec(
        id="decimal.quantize",
        category="decimal",
        summary="Round exact decimal text to places, significant digits, or an explicit increment.",
        description="Apply one named decimal rounding convention without binary floating-point coercion, preserving negative zero and reporting whether and in which direction the numeric value changed.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "decimal_places"},
                        "value": _DECIMAL_TEXT,
                        "decimalPlaces": {"type": "integer", "minimum": -100, "maximum": 100, "default": 2},
                        "roundingMode": {
                            "type": "string",
                            "enum": ["half_even", "half_up", "half_down", "toward_zero", "away_from_zero", "ceiling", "floor"],
                            "default": "half_even",
                        },
                    },
                    ("action", "value", "decimalPlaces"),
                ),
                _object(
                    {
                        "action": {"const": "significant_digits"},
                        "value": _DECIMAL_TEXT,
                        "significantDigits": {"type": "integer", "minimum": 1, "maximum": 100, "default": 6},
                        "roundingMode": {
                            "type": "string",
                            "enum": ["half_even", "half_up", "half_down", "toward_zero", "away_from_zero", "ceiling", "floor"],
                            "default": "half_even",
                        },
                    },
                    ("action", "value", "significantDigits"),
                ),
                _object(
                    {
                        "action": {"const": "increment"},
                        "value": _DECIMAL_TEXT,
                        "increment": _DECIMAL_TEXT,
                        "roundingMode": {
                            "type": "string",
                            "enum": ["half_even", "half_up", "half_down", "toward_zero", "away_from_zero", "ceiling", "floor"],
                            "default": "half_even",
                        },
                    },
                    ("action", "value", "increment"),
                ),
            ]
        },
        examples=(
            {"action": "decimal_places", "value": "2.345", "decimalPlaces": 2, "roundingMode": "half_even"},
            {"action": "significant_digits", "value": "12345.678", "significantDigits": 4, "roundingMode": "half_up"},
            {"action": "increment", "value": "1.23", "increment": "0.05", "roundingMode": "half_up"},
        ),
        handler=rounding.quantize,
        backends=("python",),
        keywords=("round", "decimal places", "significant digits", "cash rounding", "quantize", "舍入", "四舍五入", "有效数字", "小数位", "定点数"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
