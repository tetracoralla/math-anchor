from __future__ import annotations

import re
from typing import Any

from ..dimension_expression import (
    DIMENSION_EXPONENT_PATTERN,
    DIMENSION_SYMBOL_PATTERN,
    DIMENSION_VECTOR_NAME_PATTERN,
)
from ..errors import CalculatorError
from ..models import OperationSpec
from ..operations import (
    algebra,
    calculus,
    combinatorics,
    data,
    dimension,
    expression,
    finance,
    floating,
    inference,
    linear_algebra,
    matrix,
    measurement,
    number_theory,
    numerical,
    optimization,
    probability,
    programmer,
    quantity,
    rounding,
    units,
    verification,
)


MAX_SEARCH_QUERY_LENGTH = 256
MAX_CATEGORY_LENGTH = 64
MAX_OPERATION_ID_LENGTH = 128
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


_PRECISION = {
    "type": "integer",
    "minimum": 2,
    "maximum": 200,
    "default": 16,
    "description": "Decimal digits used for approximate output.",
}
_EXPRESSION = {
    "type": "string",
    "maxLength": 4096,
    "description": "Safe expression; use explicit * and ^ or ** for powers.",
}
_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 50,
        "items": {"oneOf": [{"type": "number"}, {"type": "string"}]},
    },
}
_EXACT_CELL = {
    "oneOf": [
        {"type": "integer"},
        {
            "type": "string",
            "maxLength": 256,
            "description": "Exact integer or rational expression text such as 1/10.",
        },
    ]
}
_EXACT_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 50,
        "items": _EXACT_CELL,
    },
}
_EXACT_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": _EXACT_CELL,
}
_MAX_STANDARD_INTEGER = 9_007_199_254_740_991
_EXACT_INTEGER = {
    "oneOf": [
        {
            "type": "integer",
            "minimum": -_MAX_STANDARD_INTEGER,
            "maximum": _MAX_STANDARD_INTEGER,
        },
        {
            "type": "string",
            "pattern": r"^[+-]?\d+$",
            "maxLength": 17,
        },
    ]
}
_POSITIVE_MODULUS = {
    "oneOf": [
        {
            "type": "integer",
            "minimum": 2,
            "maximum": _MAX_STANDARD_INTEGER,
        },
        {
            "type": "string",
            "pattern": r"^(?:[+]?[2-9]|[+]?[1-9]\d+)$",
            "maxLength": 17,
        },
    ]
}
_PROGRAMMER_LITERAL = {
    "type": "string",
    "pattern": r"^[+-]?(?:0[bB][01]+|0[oO][0-7]+|0[xX][0-9A-Fa-f]+|[0-9]+)$",
    "maxLength": 260,
    "description": "Exact integer text; non-decimal values require a 0b, 0o, or 0x prefix.",
}
_PROGRAMMER_BIT_WIDTH = {
    "type": "integer",
    "enum": [8, 16, 32, 64, 128, 256],
    "default": 64,
}
_PROGRAMMER_SIGNEDNESS = {
    "type": "string",
    "enum": ["unsigned", "twos_complement"],
    "default": "unsigned",
}
_PROGRAMMER_INPUT_MODE = {
    "type": "string",
    "enum": ["value", "bits"],
    "default": "value",
    "description": "Interpret the literal as a mathematical value or as a nonnegative raw bit pattern.",
}
_PROGRAMMER_COUNT = {
    "type": "integer",
    "minimum": 0,
    "maximum": 256,
    "default": 1,
}
_PROGRAMMER_OFFSET = {"type": "integer", "minimum": 0, "maximum": 255}
_PROGRAMMER_FIELD_WIDTH = {"type": "integer", "minimum": 1, "maximum": 256}
_IEEE_FORMAT = {"type": "string", "enum": ["binary32", "binary64"], "default": "binary64"}
_IEEE_INPUT_MODE = {"type": "string", "enum": ["decimal", "bits"], "default": "decimal"}
_IEEE_VALUE = {
    "type": "string",
    "minLength": 1,
    "maxLength": 256,
    "description": "Decimal text or a nonnegative 0b/0o/0x/integer bit pattern according to inputMode.",
}
_LARGE_INTEGER_TEXT = {
    "type": "string",
    "pattern": r"^[+-]?[0-9]+$",
    "maxLength": 1000,
    "description": "Exact ASCII integer text.",
}
_VARIABLES = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "maxItems": 16,
}
_DECIMAL_TEXT = {
    "type": "string",
    "pattern": r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$",
    "maxLength": 256,
    "description": "Decimal text for exact decimal provenance, such as 0.1 or 1e-6.",
}
_DECIMAL_VALUE_SCHEMA = {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]}
_DECIMAL_TEXT_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100_000,
    "items": _DECIMAL_TEXT,
}
_APPROXIMATE_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 100,
        "items": _DECIMAL_TEXT,
    },
}
_APPROXIMATE_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100,
    "items": _DECIMAL_TEXT,
}
_NUMERIC_LINALG_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 32,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 32,
        "items": _DECIMAL_TEXT,
    },
}
_NUMERIC_LINALG_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 32,
    "items": _DECIMAL_TEXT,
}
_CANDIDATE = {
    "type": "object",
    "propertyNames": {"pattern": r"^[A-Za-z_][A-Za-z0-9_]*$"},
    "additionalProperties": {"oneOf": [{"type": "number"}, {"type": "string", "maxLength": 4096}]},
    "minProperties": 1,
    "maxProperties": 8,
}
_DIMENSION_EXPONENT = {
    "oneOf": [
        {
            "type": "integer",
            "minimum": -1_000_000,
            "maximum": 1_000_000,
        },
        {
            "type": "string",
            "pattern": DIMENSION_EXPONENT_PATTERN,
        },
    ]
}
_DIMENSION_SYMBOL_PROPERTY_NAME = {
    "pattern": DIMENSION_SYMBOL_PATTERN,
    "maxLength": 64,
}
_DIMENSION_SYMBOL_NAME = {
    "type": "string",
    **_DIMENSION_SYMBOL_PROPERTY_NAME,
}
_DIMENSION_VECTOR = {
    "type": "object",
    "propertyNames": {
        "pattern": DIMENSION_VECTOR_NAME_PATTERN,
        "minLength": 1,
        "maxLength": 64,
    },
    "additionalProperties": _DIMENSION_EXPONENT,
    "maxProperties": 16,
}
_DIMENSION_DECLARATION = {
    "oneOf": [
        {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
        },
        _DIMENSION_VECTOR,
    ]
}
_DIMENSION_SYMBOLS = {
    "type": "object",
    "propertyNames": _DIMENSION_SYMBOL_PROPERTY_NAME,
    "additionalProperties": _DIMENSION_DECLARATION,
    "maxProperties": 64,
}
_DIMENSION_PI_VARIABLES = {
    "type": "object",
    "propertyNames": {
        "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$",
        "maxLength": 64,
    },
    "additionalProperties": {
        "type": "string",
        "minLength": 1,
        "maxLength": 128,
    },
    "minProperties": 1,
    "maxProperties": 16,
}
_DIMENSION_EXPRESSION_TEXT = {
    "type": "string",
    "minLength": 1,
    "maxLength": 2048,
}
_DIMENSION_EQUATION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "left": _DIMENSION_EXPRESSION_TEXT,
        "right": _DIMENSION_EXPRESSION_TEXT,
    },
    "required": ["left", "right"],
}


def _object(
    properties: dict[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


def _continuous_distribution_object(
    distribution: str,
    parameters: dict[str, Any],
    required_parameters: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "distribution": {"const": distribution},
            "function": {"type": "string", "enum": ["pdf", "cdf", "quantile"]},
            "x": _DECIMAL_TEXT,
            "probability": _DECIMAL_TEXT,
            **parameters,
            "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
        },
        "required": ["distribution", "function", *required_parameters],
        "oneOf": [
            {
                "properties": {
                    "function": {"enum": ["pdf", "cdf"]},
                    "probability": False,
                },
                "required": ["x"],
            },
            {
                "properties": {
                    "function": {"const": "quantile"},
                    "x": False,
                },
                "required": ["probability"],
            },
        ],
    }
