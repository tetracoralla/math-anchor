from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ..errors import CalculatorError
from ..output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
)
from .assurance import BASE_ASSURANCE_PROPERTIES


_LIMIT_VALIDATORS = {
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
}
_MAX_VALIDATION_MESSAGE_BYTES = 512

_LIMIT_PROPERTIES = {
    "timeoutMs": {
        "type": "integer",
        "minimum": 100,
        "maximum": 30_000,
        "default": 10_000,
    },
    "memoryMb": {
        "type": "integer",
        "minimum": 256,
        "maximum": 4096,
        "default": 1024,
    },
    "resultMode": {
        "type": "string",
        "enum": ["auto", "exact", "approx", "both"],
        "default": "auto",
        "description": "Select exact, approximate, both, or an automatically compact result.",
    },
    "maxOutputBytes": {
        "type": "integer",
        "minimum": MIN_OUTPUT_BYTES,
        "maximum": MAX_OUTPUT_BYTES,
        "default": DEFAULT_MAX_OUTPUT_BYTES,
        "description": "Strict UTF-8 byte budget for structured output.",
    },
}

_TEXT_OR_NULL_REF = {"$ref": "#/$defs/textOrNull"}
_VALUE_REF = {"$ref": "#/$defs/value"}
_TEXT_MATRIX_REF = {"$ref": "#/$defs/textMatrix"}
_TEXT_VECTOR_REF = {"$ref": "#/$defs/textVector"}
_TEXT_MATRIX_OR_NULL_REF = {"$ref": "#/$defs/textMatrixOrNull"}
_VALUE_VECTOR_REF = {"$ref": "#/$defs/valueVector"}
_SHAPE_REF = {"$ref": "#/$defs/shape"}
_DIMENSION_VECTOR_REF = {"$ref": "#/$defs/dimensionVector"}
_PROGRAMMER_REPRESENTATION_REF = {"$ref": "#/$defs/programmerRepresentation"}
_PROGRAMMER_REPRESENTATION_OR_NULL_REF = {"$ref": "#/$defs/programmerRepresentationOrNull"}
_IEEE_PROJECTION_REF = {"$ref": "#/$defs/ieeeProjection"}
_IEEE_PROJECTION_OR_NULL_REF = {"$ref": "#/$defs/ieeeProjectionOrNull"}
_RATIONAL_DECIMAL_OR_NULL_REF = {"$ref": "#/$defs/rationalDecimalOrNull"}

_TEXT_OR_NULL_DEFINITION = {"oneOf": [{"type": "string"}, {"type": "null"}]}
_VALUE_DEFINITION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "exact": _TEXT_OR_NULL_REF,
        "approx": _TEXT_OR_NULL_REF,
    },
    "required": ["exact", "approx"],
}
_TEXT_MATRIX_DEFINITION = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}
_TEXT_VECTOR_DEFINITION = {"type": "array", "items": {"type": "string"}}
_TEXT_MATRIX_OR_NULL_DEFINITION = {"oneOf": [_TEXT_MATRIX_REF, {"type": "null"}]}
_VALUE_VECTOR_DEFINITION = {"type": "array", "items": _VALUE_REF}
_SHAPE_DEFINITION = {
    "type": "array",
    "items": {"type": "integer", "minimum": 1},
    "minItems": 2,
    "maxItems": 2,
}
_DIMENSION_VECTOR_DEFINITION = {
    "type": "object",
    "propertyNames": {"type": "string", "minLength": 1, "maxLength": 64},
    "additionalProperties": {
        "type": "string",
        "pattern": r"^-?(?:0|[1-9]\d*)(?:/[1-9]\d*)?$",
    },
    "maxProperties": 16,
}
_PROGRAMMER_REPRESENTATION_DEFINITION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "unsignedDecimal": {"type": "string"},
        "signedDecimal": {"type": "string"},
        "decimal": {"type": "string"},
        "binary": {"type": "string", "pattern": r"^[01]+$"},
        "octal": {"type": "string", "pattern": r"^[0-7]+$"},
        "hexadecimal": {"type": "string", "pattern": r"^[0-9A-F]+$"},
        "character": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "validUnicodeScalar": {"type": "boolean"},
                "unicodeScalar": _TEXT_OR_NULL_REF,
                "unicodeName": _TEXT_OR_NULL_REF,
                "character": _TEXT_OR_NULL_REF,
                "ascii": {"type": "boolean"},
                "printable": {"type": "boolean"},
            },
            "required": [
                "validUnicodeScalar",
                "unicodeScalar",
                "unicodeName",
                "character",
                "ascii",
                "printable",
            ],
        },
    },
    "required": [
        "unsignedDecimal",
        "signedDecimal",
        "decimal",
        "binary",
        "octal",
        "hexadecimal",
        "character",
    ],
}
_PROGRAMMER_REPRESENTATION_OR_NULL_DEFINITION = {
    "oneOf": [_PROGRAMMER_REPRESENTATION_REF, {"type": "null"}]
}
_RATIONAL_DECIMAL_DEFINITION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rational": {"type": "string"},
        "decimal": {"type": "string"},
    },
    "required": ["rational", "decimal"],
}
_RATIONAL_DECIMAL_OR_NULL_DEFINITION = {
    "oneOf": [{"$ref": "#/$defs/rationalDecimal"}, {"type": "null"}]
}
_IEEE_NEIGHBOR_DEFINITION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rawHex": {"type": "string"},
        "roundTripDecimal": {"type": "string"},
    },
    "required": ["rawHex", "roundTripDecimal"],
}
_IEEE_PROJECTION_DEFINITION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "classification": {"enum": ["zero", "subnormal", "normal", "infinity", "nan"]},
        "sign": {"enum": [0, 1]},
        "negativeZero": {"type": "boolean"},
        "rawHex": {"type": "string"},
        "exponentBits": {"type": "string", "pattern": "^[01]+$"},
        "fractionBits": {"type": "string", "pattern": "^[01]+$"},
        "unbiasedExponent": {"oneOf": [{"type": "integer"}, {"type": "null"}]},
        "exactValue": _RATIONAL_DECIMAL_OR_NULL_REF,
        "roundTripDecimal": {"type": "string"},
        "ulp": _RATIONAL_DECIMAL_OR_NULL_REF,
        "previous": {"oneOf": [{"$ref": "#/$defs/ieeeNeighbor"}, {"type": "null"}]},
        "next": {"oneOf": [{"$ref": "#/$defs/ieeeNeighbor"}, {"type": "null"}]},
        "inputRounded": {"type": "boolean"},
        "roundingDirection": {"enum": ["exact", "up", "down", "overflow"]},
    },
    "required": [
        "classification",
        "sign",
        "negativeZero",
        "rawHex",
        "exponentBits",
        "fractionBits",
        "unbiasedExponent",
        "exactValue",
        "roundTripDecimal",
        "ulp",
        "previous",
        "next",
        "inputRounded",
        "roundingDirection",
    ],
}
_IEEE_PROJECTION_OR_NULL_DEFINITION = {
    "oneOf": [_IEEE_PROJECTION_REF, {"type": "null"}]
}
_SCHEMA_DEFINITIONS = {
    "textOrNull": _TEXT_OR_NULL_DEFINITION,
    "value": _VALUE_DEFINITION,
    "textMatrix": _TEXT_MATRIX_DEFINITION,
    "textVector": _TEXT_VECTOR_DEFINITION,
    "textMatrixOrNull": _TEXT_MATRIX_OR_NULL_DEFINITION,
    "valueVector": _VALUE_VECTOR_DEFINITION,
    "shape": _SHAPE_DEFINITION,
    "dimensionVector": _DIMENSION_VECTOR_DEFINITION,
    "programmerRepresentation": _PROGRAMMER_REPRESENTATION_DEFINITION,
    "programmerRepresentationOrNull": _PROGRAMMER_REPRESENTATION_OR_NULL_DEFINITION,
    "rationalDecimal": _RATIONAL_DECIMAL_DEFINITION,
    "rationalDecimalOrNull": _RATIONAL_DECIMAL_OR_NULL_DEFINITION,
    "ieeeNeighbor": _IEEE_NEIGHBOR_DEFINITION,
    "ieeeProjection": _IEEE_PROJECTION_DEFINITION,
    "ieeeProjectionOrNull": _IEEE_PROJECTION_OR_NULL_DEFINITION,
}

_TEXT_OR_NULL = _TEXT_OR_NULL_REF
_VALUE = _VALUE_REF
_TEXT_MATRIX = _TEXT_MATRIX_REF
_TEXT_VECTOR = _TEXT_VECTOR_REF
_TEXT_MATRIX_OR_NULL = _TEXT_MATRIX_OR_NULL_REF
_VALUE_VECTOR = _VALUE_VECTOR_REF
_SHAPE = _SHAPE_REF
_DIMENSION_VECTOR = _DIMENSION_VECTOR_REF
_DIMENSION_VECTOR_OR_NULL = {"oneOf": [_DIMENSION_VECTOR, {"type": "null"}]}
_MATRIX_COMPONENT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "exact": _TEXT_MATRIX,
        "approx": _TEXT_MATRIX,
        "precision": {"type": "integer", "minimum": 2},
        "shape": _SHAPE,
    },
    "required": ["exact", "approx", "precision", "shape"],
}
_BASE_OK_PROPERTIES = {
    "status": {"const": "ok"},
    "operation": {"type": "string"},
    "kind": {"type": "string"},
    "warnings": {"type": "array", "items": {"type": "string"}},
    **BASE_ASSURANCE_PROPERTIES,
}


def _ok_schema(
    kind: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    statuses: tuple[str, ...] = ("ok",),
) -> dict[str, Any]:
    status_schema: dict[str, Any] = (
        {"const": statuses[0]} if len(statuses) == 1 else {"enum": list(statuses)}
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            **deepcopy(_BASE_OK_PROPERTIES),
            "status": status_schema,
            "kind": {"const": kind},
            **properties,
        },
        "required": [
            "status",
            "operation",
            "kind",
            "warnings",
            "assurance",
            "claim",
            "scope",
            "assumptions",
            "provenance",
            "certificate",
            "checkedBy",
            *required,
        ],
    }


def _numeric_linear_algebra_schema(
    action: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return _ok_schema(
        "numeric_linear_algebra",
        {
            "action": {"const": action},
            "inputShape": _SHAPE,
            "rank": {"type": "integer", "minimum": 0},
            "conditionNumber": {"type": "string"},
            "singularValues": _TEXT_VECTOR,
            "tolerance": {"type": "string"},
            "precision": {"type": "integer", "minimum": 2, "maximum": 15},
            "numericFormat": {"const": "binary64"},
            **properties,
        },
        [
            "action",
            "inputShape",
            "rank",
            "conditionNumber",
            "singularValues",
            "tolerance",
            "precision",
            "numericFormat",
            *required,
        ],
    )


ERROR_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"const": "error"},
        "error": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "retryable": {"type": "boolean"},
                "phase": {
                    "enum": [
                        "input",
                        "admission",
                        "queue",
                        "startup",
                        "execution",
                        "output",
                        "batch",
                        "cancellation",
                    ]
                },
                "retryAfterMs": {"type": "integer", "minimum": 1},
                "suggestedAction": {
                    "enum": [
                        "correct_input",
                        "search_operation",
                        "reduce_request",
                        "split_or_reduce",
                        "retry",
                        "stop",
                    ]
                },
                "details": {"type": "object"},
            },
            "required": ["code", "message", "retryable", "phase", "suggestedAction"],
        },
    },
    "required": ["status", "error"],
}
