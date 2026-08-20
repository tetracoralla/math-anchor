from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .errors import CalculatorError
from .output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
)


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
_TEXT_MATRIX_OR_NULL_REF = {"$ref": "#/$defs/textMatrixOrNull"}
_VALUE_VECTOR_REF = {"$ref": "#/$defs/valueVector"}
_SHAPE_REF = {"$ref": "#/$defs/shape"}
_DIMENSION_VECTOR_REF = {"$ref": "#/$defs/dimensionVector"}

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
_SCHEMA_DEFINITIONS = {
    "textOrNull": _TEXT_OR_NULL_DEFINITION,
    "value": _VALUE_DEFINITION,
    "textMatrix": _TEXT_MATRIX_DEFINITION,
    "textMatrixOrNull": _TEXT_MATRIX_OR_NULL_DEFINITION,
    "valueVector": _VALUE_VECTOR_DEFINITION,
    "shape": _SHAPE_DEFINITION,
    "dimensionVector": _DIMENSION_VECTOR_DEFINITION,
}

_TEXT_OR_NULL = _TEXT_OR_NULL_REF
_VALUE = _VALUE_REF
_TEXT_MATRIX = _TEXT_MATRIX_REF
_TEXT_MATRIX_OR_NULL = _TEXT_MATRIX_OR_NULL_REF
_VALUE_VECTOR = _VALUE_VECTOR_REF
_SHAPE = _SHAPE_REF
_DIMENSION_VECTOR = _DIMENSION_VECTOR_REF
_DIMENSION_VECTOR_OR_NULL = {"oneOf": [_DIMENSION_VECTOR, {"type": "null"}]}
_BASE_OK_PROPERTIES = {
    "status": {"const": "ok"},
    "operation": {"type": "string"},
    "kind": {"type": "string"},
    "warnings": {"type": "array", "items": {"type": "string"}},
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
        "required": ["status", "operation", "kind", "warnings", *required],
    }


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
                "details": {"type": "object"},
            },
            "required": ["code", "message"],
        },
    },
    "required": ["status", "error"],
}

RUN_RESULT_SCHEMA = {
    "$defs": deepcopy(_SCHEMA_DEFINITIONS),
    "oneOf": [
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
        _ok_schema(
            "factorization",
            {
                "value": {"type": "string"},
                "sign": {"enum": [-1, 1]},
                "isPrime": {"type": "boolean"},
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "prime": {"type": "string"},
                            "exponent": {"type": "integer", "minimum": 1},
                        },
                        "required": ["prime", "exponent"],
                    },
                },
            },
            ["value", "sign", "isPrime", "factors"],
        ),
        _ok_schema(
            "gcd_lcm",
            {
                "count": {"type": "integer", "minimum": 1},
                "gcd": {"type": "string"},
                "lcm": {"type": "string"},
            },
            ["count", "gcd", "lcm"],
        ),
        _ok_schema(
            "modular",
            {
                "action": {"enum": ["remainder", "power", "inverse"]},
                "modulus": {"type": "string"},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "modulus", "exact", "approx", "precision"],
        ),
        _ok_schema(
            "integer_count",
            {
                "action": {"enum": ["binomial", "permutations", "multinomial"]},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "exact", "approx", "precision"],
        ),
        _ok_schema(
            "matrix",
            {
                "exact": _TEXT_MATRIX_OR_NULL,
                "approx": _TEXT_MATRIX_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "shape": _SHAPE,
            },
            ["exact", "approx", "precision", "shape"],
        ),
        _ok_schema(
            "linear_system",
            {
                "classification": {"enum": ["unique", "infinite", "inconsistent"]},
                "variables": {"type": "array", "items": {"type": "string"}},
                "rank": {"type": "integer", "minimum": 0},
                "augmentedRank": {"type": "integer", "minimum": 0},
                "particular": {"oneOf": [_VALUE_VECTOR, {"type": "null"}]},
                "nullspace": {"type": "array", "items": _VALUE_VECTOR},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["classification", "variables", "rank", "augmentedRank", "particular", "nullspace", "precision"],
        ),
        _ok_schema(
            "matrix_reduction",
            {
                "action": {"const": "rank"},
                "rank": {"type": "integer", "minimum": 0},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "rank", "precision"],
        ),
        _ok_schema(
            "matrix_reduction",
            {
                "action": {"const": "rref"},
                "exact": _TEXT_MATRIX_OR_NULL,
                "approx": _TEXT_MATRIX_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "shape": _SHAPE,
                "pivots": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            },
            ["action", "exact", "approx", "precision", "shape", "pivots"],
        ),
        _ok_schema(
            "matrix_reduction",
            {
                "action": {"enum": ["nullspace", "columnspace"]},
                "basis": {"type": "array", "items": _VALUE_VECTOR},
                "dimension": {"type": "integer", "minimum": 0},
                "vectorSize": {"type": "integer", "minimum": 1},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "basis", "dimension", "vectorSize", "precision"],
        ),
        _ok_schema(
            "series",
            {
                "variable": {"type": "string"},
                "point": {"type": "string"},
                "order": {"type": "integer", "minimum": 1, "maximum": 50},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["variable", "point", "order", "exact", "approx", "precision"],
        ),
        _ok_schema(
            "derivative_matrix",
            {
                "action": {"enum": ["gradient", "jacobian", "hessian"]},
                "variables": {"type": "array", "items": {"type": "string"}},
                "exact": _TEXT_MATRIX_OR_NULL,
                "approx": _TEXT_MATRIX_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "shape": _SHAPE,
            },
            ["action", "variables", "exact", "approx", "precision", "shape"],
        ),
        _ok_schema(
            "values",
            {
                "values": {"type": "array", "items": _VALUE},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["values", "precision"],
        ),
        _ok_schema(
            "solutions",
            {
                "classification": {"enum": ["none", "finite", "infinite", "unknown"]},
                "complete": {"type": "boolean"},
                "solutionSet": {"type": "string"},
                "solutions": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": _VALUE},
                },
                "precision": {"type": "integer", "minimum": 2},
            },
            ["classification", "complete", "solutionSet", "solutions", "precision"],
        ),
        _ok_schema(
            "statistics",
            {
                "count": {"type": "integer", "minimum": 1},
                "mean": _VALUE,
                "median": _VALUE,
                "standardDeviation": _VALUE,
                "minimum": _VALUE,
                "maximum": _VALUE,
                "range": _VALUE,
                "quartiles": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "method": {"type": "string"},
                        "q1": _VALUE,
                        "q3": _VALUE,
                    },
                    "required": ["method", "q1", "q3"],
                },
                "precision": {"type": "integer", "minimum": 2},
                "ddof": {"type": "integer", "minimum": 0},
            },
            [
                "count",
                "mean",
                "median",
                "standardDeviation",
                "minimum",
                "maximum",
                "range",
                "quartiles",
                "precision",
                "ddof",
            ],
        ),
        _ok_schema(
            "quantity",
            {
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "unit": {"type": "string"},
                "from": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "value": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                        "unit": {"type": "string"},
                    },
                    "required": ["value", "unit"],
                },
            },
            ["exact", "approx", "precision", "unit", "from"],
        ),
        _ok_schema(
            "equivalence_verification",
            {
                "equivalence": {"enum": ["equivalent", "not_equivalent", "unknown"]},
                "proven": {"type": "boolean"},
                "domain": {"enum": ["real", "complex"]},
                "definednessPolicy": {"enum": ["strict", "common_domain"]},
                "definedness": {"enum": ["same", "different", "unknown"]},
                "leftDomain": _TEXT_OR_NULL,
                "rightDomain": _TEXT_OR_NULL,
                "difference": _VALUE,
                "counterexample": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "values": {"type": "object", "additionalProperties": _VALUE},
                                "left": _VALUE,
                                "right": _VALUE,
                                "reason": {"type": "string"},
                            },
                            "required": ["values", "left", "right", "reason"],
                        },
                        {"type": "null"},
                    ]
                },
                "precision": {"type": "integer", "minimum": 2},
            },
            [
                "equivalence",
                "proven",
                "domain",
                "definednessPolicy",
                "definedness",
                "leftDomain",
                "rightDomain",
                "difference",
                "counterexample",
                "precision",
            ],
        ),
        _ok_schema(
            "solution_verification",
            {
                "domain": {"enum": ["real", "complex"]},
                "tolerance": {"type": "string"},
                "allValid": {"oneOf": [{"type": "boolean"}, {"type": "null"}]},
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {"type": "integer", "minimum": 0},
                            "values": {"type": "object", "additionalProperties": _VALUE},
                            "valid": {"oneOf": [{"type": "boolean"}, {"type": "null"}]},
                            "checks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "constraint": {"type": "string"},
                                        "relation": {"enum": ["=", "!=", "<", "<=", ">", ">="]},
                                        "defined": {"type": "boolean"},
                                        "satisfied": {"oneOf": [{"type": "boolean"}, {"type": "null"}]},
                                        "residual": _VALUE,
                                        "residualMagnitude": _TEXT_OR_NULL,
                                        "reason": _TEXT_OR_NULL,
                                    },
                                    "required": ["constraint", "relation", "defined", "satisfied", "residual", "residualMagnitude", "reason"],
                                },
                            },
                        },
                        "required": ["index", "values", "valid", "checks"],
                    },
                },
                "completeness": {"enum": ["complete", "incomplete", "unknown", "not_checked"]},
                "omissionRisk": {"enum": ["none_proven", "known_omissions", "not_assessed"]},
                "omittedSolutions": _VALUE_VECTOR,
                "precision": {"type": "integer", "minimum": 2},
            },
            [
                "domain",
                "tolerance",
                "allValid",
                "candidates",
                "completeness",
                "omissionRisk",
                "omittedSolutions",
                "precision",
            ],
        ),
        _ok_schema(
            "quantity_expression",
            {
                "expression": {"type": "string"},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "unit": {"type": "string"},
                "dimensionality": {"type": "string"},
                "convertedTo": _TEXT_OR_NULL,
            },
            ["expression", "exact", "approx", "precision", "unit", "dimensionality", "convertedTo"],
        ),
        _ok_schema(
            "dimensional_analysis",
            {
                "scope": {"const": "dimensional_consistency_only"},
                "dimensionallyConsistent": {"type": "boolean"},
                "leftExpression": {"type": "string"},
                "rightExpression": {"type": "string"},
                "leftDimension": _DIMENSION_VECTOR_OR_NULL,
                "rightDimension": _DIMENSION_VECTOR_OR_NULL,
                "leftDisplay": _TEXT_OR_NULL,
                "rightDisplay": _TEXT_OR_NULL,
                "issues": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "code": {"const": "DIMENSION_ADD_MISMATCH"},
                                    "expression": {"type": "string"},
                                    "message": {"type": "string"},
                                    "left": _DIMENSION_VECTOR,
                                    "right": _DIMENSION_VECTOR,
                                },
                                "required": ["code", "expression", "message", "left", "right"],
                            },
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "code": {"const": "DIMENSION_EQUATION_MISMATCH"},
                                    "expression": {"type": "string"},
                                    "message": {"type": "string"},
                                    "left": _DIMENSION_VECTOR,
                                    "right": _DIMENSION_VECTOR,
                                },
                                "required": ["code", "expression", "message", "left", "right"],
                            },
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "code": {"const": "DIMENSION_FUNCTION_ARGUMENT"},
                                    "expression": {"type": "string"},
                                    "message": {"type": "string"},
                                    "function": {"enum": ["sin", "cos", "tan", "log", "exp"]},
                                    "actual": _DIMENSION_VECTOR,
                                },
                                "required": ["code", "expression", "message", "function", "actual"],
                            },
                        ]
                    },
                },
            },
            [
                "scope",
                "dimensionallyConsistent",
                "leftExpression",
                "rightExpression",
                "leftDimension",
                "rightDimension",
                "leftDisplay",
                "rightDisplay",
                "issues",
            ],
        ),
        _ok_schema(
            "dimensional_inference",
            {
                "scope": {"const": "dimensional_consistency_only"},
                "classification": {"enum": ["unique", "underdetermined", "inconsistent"]},
                "unknowns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 16,
                    "uniqueItems": True,
                },
                "inferred": {
                    "type": "object",
                    "propertyNames": {"type": "string", "minLength": 1, "maxLength": 64},
                    "additionalProperties": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "dimension": _DIMENSION_VECTOR,
                            "display": {"type": "string"},
                        },
                        "required": ["dimension", "display"],
                    },
                    "maxProperties": 16,
                },
                "unresolved": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 16,
                    "uniqueItems": True,
                },
                "rank": {"type": "integer", "minimum": 0},
                "constraintCount": {"type": "integer", "minimum": 1},
                "degreesOfFreedom": {"type": "integer", "minimum": 0},
                "conflictingDimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
            },
            [
                "scope",
                "classification",
                "unknowns",
                "inferred",
                "unresolved",
                "rank",
                "constraintCount",
                "degreesOfFreedom",
                "conflictingDimensions",
            ],
        ),
        _ok_schema(
            "dimensionless_groups",
            {
                "scope": {"const": "dimensionless_basis_only"},
                "basisConvention": {"const": "primitive_integer_exponents"},
                "variables": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 64},
                    "minItems": 1,
                    "maxItems": 16,
                    "uniqueItems": True,
                },
                "rank": {"type": "integer", "minimum": 0, "maximum": 16},
                "nullity": {"type": "integer", "minimum": 0, "maximum": 16},
                "groups": {
                    "type": "array",
                    "maxItems": 16,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "index": {"type": "integer", "minimum": 1, "maximum": 16},
                            "exponents": {
                                "type": "object",
                                "propertyNames": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 64,
                                },
                                "additionalProperties": {
                                    "type": "string",
                                    "pattern": r"^-?[1-9]\d*$",
                                },
                                "minProperties": 1,
                                "maxProperties": 16,
                            },
                            "expression": {"type": "string", "minLength": 1, "maxLength": 2048},
                        },
                        "required": ["index", "exponents", "expression"],
                    },
                },
            },
            [
                "scope",
                "basisConvention",
                "variables",
                "rank",
                "nullity",
                "groups",
            ],
        ),
        _ok_schema(
            "numerical_root",
            {
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "method": {"const": "brent"},
                "converged": {"type": "boolean"},
                "iterations": {"type": "integer", "minimum": 0},
                "tolerance": {"type": "string"},
                "errorBound": _TEXT_OR_NULL,
                "residual": _TEXT_OR_NULL,
                "finalBracket": {
                    "oneOf": [
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        {"type": "null"},
                    ]
                },
                "findAll": {"type": "boolean"},
                "resolution": _TEXT_OR_NULL,
                "count": {"type": "integer", "minimum": 0},
                "roots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "approx": {"type": "string"},
                            "errorBound": {"type": "string"},
                            "residual": {"type": "string"},
                            "finalBracket": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                        },
                        "required": ["approx", "errorBound", "residual", "finalBracket"],
                    },
                },
            },
            [
                "exact",
                "approx",
                "precision",
                "method",
                "converged",
                "iterations",
                "tolerance",
                "errorBound",
                "residual",
                "finalBracket",
            ],
        ),
        _ok_schema(
            "global_extremum",
            {
                "objective": {"enum": ["minimum", "maximum"]},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
                "method": {"const": "interval_branch_and_bound"},
                "certified": {"type": "boolean"},
                "tolerance": {"type": "string"},
                "argminTolerance": {"type": "string"},
                "valueEnclosure": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "extremumIntervals": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "evaluations": {"type": "integer", "minimum": 1},
                "intervalsExplored": {"type": "integer", "minimum": 1},
            },
            [
                "objective",
                "exact",
                "approx",
                "precision",
                "method",
                "certified",
                "tolerance",
                "argminTolerance",
                "valueEnclosure",
                "extremumIntervals",
                "evaluations",
                "intervalsExplored",
            ],
            statuses=("ok", "uncertain"),
        ),
        _ok_schema(
            "numerical_integral",
            {
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 16},
                "estimatedDigitsFromLocalError": {
                    "oneOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]
                },
                "method": {"const": "stratified_adaptive_clenshaw_curtis"},
                "converged": {"type": "boolean"},
                "localErrorToleranceMet": {"const": True},
                "convergenceBasis": {"type": "string"},
                "coverageStatus": {
                    "enum": [
                        "unverified",
                        "caller_supplied_feature_points",
                        "caller_supplied_feature_scale",
                    ]
                },
                "coverageAssumption": {"type": "string"},
                "evaluations": {"type": "integer", "minimum": 5},
                "probeSegments": {"type": "integer", "minimum": 1},
                "maxProbeSpacing": {"type": "string"},
                "breakpoints": {"type": "array", "items": {"type": "string"}},
                "featureScale": _TEXT_OR_NULL,
                "absoluteTolerance": {"type": "string"},
                "relativeTolerance": {"type": "string"},
                "errorEstimate": {"type": "string"},
                "resultInterval": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "errorBoundCertified": {"const": False},
            },
            [
                "exact",
                "approx",
                "precision",
                "estimatedDigitsFromLocalError",
                "method",
                "converged",
                "localErrorToleranceMet",
                "convergenceBasis",
                "coverageStatus",
                "coverageAssumption",
                "evaluations",
                "probeSegments",
                "maxProbeSpacing",
                "breakpoints",
                "featureScale",
                "absoluteTolerance",
                "relativeTolerance",
                "errorEstimate",
                "resultInterval",
                "errorBoundCertified",
            ],
            statuses=("ok", "uncertain"),
        ),
        _ok_schema(
            "approximate_linear_system",
            {
                "classification": {"enum": ["stable_for_tolerance", "ill_conditioned", "singular"]},
                "solution": {"oneOf": [_VALUE_VECTOR, {"type": "null"}]},
                "rank": {"type": "integer", "minimum": 0},
                "conditionNumber": {"type": "string"},
                "residualNorm": _TEXT_OR_NULL,
                "backwardError": _TEXT_OR_NULL,
                "relativeForwardErrorBound": _TEXT_OR_NULL,
                "tolerance": {"type": "string"},
                "precision": {"type": "integer", "minimum": 2},
                "numericFormat": {"const": "binary64"},
                "diagnosticNorm": {"const": "infinity"},
            },
            [
                "classification",
                "solution",
                "rank",
                "conditionNumber",
                "residualNorm",
                "backwardError",
                "relativeForwardErrorBound",
                "tolerance",
                "precision",
                "numericFormat",
                "diagnosticNorm",
            ],
        ),
        _ok_schema(
            "financial",
            {
                "action": {"enum": ["compound_value", "effective_annual_rate", "loan_payment", "npv", "irr"]},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "exact": _TEXT_OR_NULL,
                            "approx": _TEXT_OR_NULL,
                            "unit": {"enum": ["money", "rate"]},
                            "decimalPlaces": {"type": "integer", "minimum": 0},
                            "roundingMode": {"enum": ["half_even", "half_up"]},
                        },
                        "required": ["name", "exact", "approx", "unit", "decimalPlaces", "roundingMode"],
                    },
                },
                "method": {"type": "string"},
                "conventions": {"type": "array", "items": {"type": "string"}},
                "precision": {"type": "integer", "minimum": 16},
                "rounding": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "decimalPlaces": {"type": "integer", "minimum": 0},
                        "mode": {"enum": ["half_even", "half_up"]},
                    },
                    "required": ["decimalPlaces", "mode"],
                },
                "converged": {"oneOf": [{"type": "boolean"}, {"type": "null"}]},
                "iterations": {"oneOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]},
                "errorBound": _TEXT_OR_NULL,
                "residual": _TEXT_OR_NULL,
            },
            [
                "action",
                "results",
                "method",
                "conventions",
                "precision",
                "rounding",
                "converged",
                "iterations",
                "errorBound",
                "residual",
            ],
        ),
        _ok_schema(
            "probability",
            {
                "distribution": {"enum": ["normal", "binomial", "poisson"]},
                "function": {"enum": ["pdf", "cdf", "quantile", "pmf"]},
                "value": _VALUE,
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"name": {"type": "string"}, "value": {"type": "string"}},
                        "required": ["name", "value"],
                    },
                },
                "method": {"type": "string"},
                "support": {"type": "string"},
                "precision": {"type": "integer", "minimum": 16},
            },
            ["distribution", "function", "value", "parameters", "method", "support", "precision"],
        ),
        _ok_schema(
            "inference",
            {
                "action": {"enum": ["mean_confidence_interval", "one_sample_t_test", "linear_regression"]},
                "sampleSize": {"type": "integer", "minimum": 2},
                "estimates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"name": {"type": "string"}, "value": _VALUE},
                        "required": ["name", "value"],
                    },
                },
                "interval": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "level": {"type": "string"},
                                "degreesOfFreedom": {"type": "integer", "minimum": 1},
                                "lower": _VALUE,
                                "upper": _VALUE,
                            },
                            "required": ["level", "degreesOfFreedom", "lower", "upper"],
                        },
                        {"type": "null"},
                    ]
                },
                "test": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "statistic": _VALUE,
                                "degreesOfFreedom": {"type": "integer", "minimum": 1},
                                "pValue": _VALUE,
                                "alternative": {"enum": ["two_sided", "less", "greater"]},
                            },
                            "required": ["statistic", "degreesOfFreedom", "pValue", "alternative"],
                        },
                        {"type": "null"},
                    ]
                },
                "method": {"type": "string"},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "precision": {"type": "integer", "minimum": 16},
            },
            ["action", "sampleSize", "estimates", "interval", "test", "method", "assumptions", "precision"],
        ),
    ]
}

# Keep the complete per-kind schema above as the runtime validation authority.
# Advertising that entire union on every tool listing made Agents pay for more
# than 20 KB of result detail before making an ordinary call. The live tool
# therefore publishes the stable common envelope and dominant scalar fields;
# operation-specific output remains structured and is still validated against
# RUN_RESULT_SCHEMA before it crosses the execution boundary.
RUN_TOOL_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "status": {"enum": ["ok", "uncertain", "error"]},
        "operation": {"type": "string"},
        "kind": {"type": "string"},
        "exact": _TEXT_OR_NULL,
        "approx": _TEXT_OR_NULL,
        "precision": {"type": "integer", "minimum": 2},
        "unit": _TEXT_OR_NULL,
        "warnings": {"type": "array", "items": {"type": "string"}},
        "error": ERROR_RESULT_SCHEMA["properties"]["error"],
    },
    "required": ["status"],
    "$defs": {"textOrNull": deepcopy(_TEXT_OR_NULL_DEFINITION)},
}


_INDEXED_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "index": {"type": "integer", "minimum": 0},
        "status": {"type": "string"},
    },
    "required": ["index", "status"],
}

_BATCH_OK_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"enum": ["ok", "partial"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 32},
        "results": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "items": _INDEXED_RESULT_SCHEMA,
        },
    },
    "required": ["status", "count", "results"],
}

BATCH_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {"status": {"type": "string"}},
    "required": ["status"],
}


def validate_operation_arguments(operation: str, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    schema = _select_discriminated_schema(schema, arguments)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(arguments),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    path = ".".join(str(part) for part in error.absolute_path) or "arguments"
    code = "E_LIMIT" if error.validator in _LIMIT_VALIDATORS else "E_INPUT"
    message = error.message
    if len(message.encode("utf-8")) > _MAX_VALIDATION_MESSAGE_BYTES:
        message = f"value does not satisfy {error.validator}"
    raise CalculatorError(
        code,
        f"invalid {operation} arguments at {path}: {message}",
        {"path": list(error.absolute_path), "rule": error.validator},
    )


def _select_discriminated_schema(schema: dict[str, Any], instance: dict[str, Any]) -> dict[str, Any]:
    variants = schema.get("oneOf")
    action = instance.get("action")
    if not isinstance(variants, list) or not isinstance(action, str):
        return schema
    matching = []
    for variant in variants:
        action_schema = variant.get("properties", {}).get("action", {})
        if action_schema.get("const") == action or action in action_schema.get("enum", []):
            matching.append(variant)
    return matching[0] if len(matching) == 1 else schema


def validate_result(result: dict[str, Any]) -> None:
    try:
        Draft202012Validator(RUN_RESULT_SCHEMA).validate(result)
    except ValidationError as error:
        path = ".".join(str(part) for part in error.absolute_path) or "result"
        raise CalculatorError(
            "E_RUNTIME",
            f"operation returned a result outside the public contract at {path}",
        ) from error


def operation_request_variants(
    operation_schemas: list[tuple[str, dict[str, Any]]],
    *,
    include_limits: bool,
    close_object: bool = True,
    inherit_root_contract: bool = False,
) -> list[dict[str, Any]]:
    variants = []
    for operation, arguments_schema in operation_schemas:
        properties = {
            "operation": {"const": operation},
            "arguments": deepcopy(arguments_schema),
        }
        if include_limits:
            properties.update(deepcopy(_LIMIT_PROPERTIES))
        variant = {"properties": properties}
        if not inherit_root_contract:
            variant["type"] = "object"
            variant["required"] = ["operation", "arguments"]
        if close_object:
            variant["additionalProperties"] = False
        variants.append(variant)
    return variants


def run_tool_parameters(operation_schemas: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    return {
        "title": "math_runArguments",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "operation": {
                "type": "string",
                "enum": [operation for operation, _ in operation_schemas],
            },
            "arguments": {"type": "object"},
            **deepcopy(_LIMIT_PROPERTIES),
        },
        "required": ["operation", "arguments"],
        "oneOf": operation_request_variants(
            operation_schemas,
            include_limits=False,
            close_object=False,
            inherit_root_contract=True,
        ),
    }


def batch_item_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        # The per-item limits are the same knob values math.run advertises;
        # publishing them keeps the per-item output budget discoverable
        # instead of failing with an undocumented default.
        "properties": {
            "operation": {"type": "string", "minLength": 1},
            "arguments": {"type": "object"},
            **deepcopy(_LIMIT_PROPERTIES),
        },
        "required": ["operation", "arguments"],
    }


def batch_tool_parameters() -> dict[str, Any]:
    return {
        "title": "math_batchArguments",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": batch_item_parameters(),
            },
            "timeoutMs": {
                "type": "integer",
                "minimum": 100,
                "maximum": 30_000,
                "default": 30_000,
                "description": "Cumulative deadline for the complete batch, including queued items.",
            },
            "maxOutputBytes": {
                "type": "integer",
                "minimum": MIN_OUTPUT_BYTES,
                "maximum": MAX_OUTPUT_BYTES,
                "default": DEFAULT_BATCH_MAX_OUTPUT_BYTES,
                "description": "Strict UTF-8 byte budget for the complete ordered batch result.",
            },
        },
        "required": ["items"],
    }
