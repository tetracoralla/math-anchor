from __future__ import annotations

from .shared import (
    ERROR_RESULT_SCHEMA,
    _TEXT_OR_NULL,
    _ok_schema,
)


RESULT_VARIANTS = (
        ERROR_RESULT_SCHEMA,
        _ok_schema(
            "scalar",
            {
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "unit": _TEXT_OR_NULL,
            },
            ["exact", "approx", "precision", "unit"],
        ),
        _ok_schema(
            "transformation",
            {
                "action": {"enum": ["simplify", "expand", "factor", "cancel", "apart", "collect"]},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "exact", "approx", "precision"],
        ),
        _ok_schema(
            "decimal_quantization",
            {
                "action": {"enum": ["decimal_places", "significant_digits", "increment"]},
                "input": {"type": "string"},
                "result": {"type": "string"},
                "quantum": {"type": "string"},
                "roundingMode": {
                    "enum": ["half_even", "half_up", "half_down", "toward_zero", "away_from_zero", "ceiling", "floor"]
                },
                "changed": {"type": "boolean"},
                "direction": {"enum": ["up", "down", "unchanged"]},
                "negativeZero": {"type": "boolean"},
                "decimalPlaces": {"oneOf": [{"type": "integer"}, {"type": "null"}]},
                "significantDigits": {"oneOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
                "increment": _TEXT_OR_NULL,
            },
            [
                "action",
                "input",
                "result",
                "quantum",
                "roundingMode",
                "changed",
                "direction",
                "negativeZero",
                "decimalPlaces",
                "significantDigits",
                "increment",
            ],
        ),
        _ok_schema(
            "function_table",
            {
                "count": {"type": "integer", "minimum": 1},
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "string"},
                            "exact": _TEXT_OR_NULL,
                            "approx": _TEXT_OR_NULL,
                            "undefined": {"type": "boolean"},
                        },
                        "required": ["x", "exact", "approx", "undefined"],
                    },
                },
            },
            ["count", "points"],
        ),
)
