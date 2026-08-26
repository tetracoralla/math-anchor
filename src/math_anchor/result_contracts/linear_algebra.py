from __future__ import annotations

from .shared import (
    _MATRIX_COMPONENT,
    _SHAPE,
    _TEXT_MATRIX,
    _TEXT_MATRIX_OR_NULL,
    _TEXT_VECTOR,
    _VALUE,
    _VALUE_VECTOR,
    _numeric_linear_algebra_schema,
    _ok_schema,
)


RESULT_VARIANTS = (
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
            "exact_eigenspaces",
            {
                "action": {"const": "eigenspaces"},
                "matrixSize": {"type": "integer", "minimum": 1},
                "diagonalizable": {"type": "boolean"},
                "eigenspaces": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "eigenvalue": _VALUE,
                            "algebraicMultiplicity": {"type": "integer", "minimum": 1},
                            "geometricMultiplicity": {"type": "integer", "minimum": 1},
                            "basis": {"type": "array", "items": _VALUE_VECTOR},
                        },
                        "required": [
                            "eigenvalue",
                            "algebraicMultiplicity",
                            "geometricMultiplicity",
                            "basis",
                        ],
                    },
                    "minItems": 1,
                },
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "matrixSize", "diagonalizable", "eigenspaces", "precision"],
        ),
        _ok_schema(
            "exact_matrix_decomposition",
            {
                "action": {"const": "lu"},
                "factors": {
                    "type": "array",
                    "prefixItems": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"name": {"const": "L"}, **_MATRIX_COMPONENT["properties"]},
                            "required": ["name", *_MATRIX_COMPONENT["required"]],
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"name": {"const": "U"}, **_MATRIX_COMPONENT["properties"]},
                            "required": ["name", *_MATRIX_COMPONENT["required"]],
                        },
                    ],
                    "items": False,
                    "minItems": 2,
                    "maxItems": 2,
                },
                "permutation": _MATRIX_COMPONENT,
                "pivotSwaps": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "relation": {"const": "P*A = L*U"},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "factors", "permutation", "pivotSwaps", "relation", "precision"],
        ),
        _ok_schema(
            "exact_matrix_decomposition",
            {
                "action": {"const": "cholesky"},
                "factors": {
                    "type": "array",
                    "prefixItems": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"name": {"const": "L"}, **_MATRIX_COMPONENT["properties"]},
                            "required": ["name", *_MATRIX_COMPONENT["required"]],
                        },
                    ],
                    "items": False,
                    "minItems": 1,
                    "maxItems": 1,
                },
                "permutation": {"type": "null"},
                "pivotSwaps": {"type": "array", "maxItems": 0},
                "relation": {"const": "A = L*L.H"},
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "factors", "permutation", "pivotSwaps", "relation", "precision"],
        ),
        _ok_schema(
            "exact_matrix_algebra",
            {
                "action": {"enum": ["matrix_multiply", "transpose"]},
                "exact": _TEXT_MATRIX,
                "approx": _TEXT_MATRIX,
                "precision": {"type": "integer", "minimum": 2},
                "shape": _SHAPE,
            },
            ["action", "exact", "approx", "precision", "shape"],
        ),
        _ok_schema(
            "exact_vector_algebra",
            {
                "action": {"enum": ["dot", "norm", "norm_squared"]},
                "dimension": {"type": "integer", "minimum": 1},
                "result": _VALUE,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "dimension", "result", "precision"],
        ),
        _ok_schema(
            "exact_vector_algebra",
            {
                "action": {"enum": ["cross", "projection"]},
                "dimension": {"type": "integer", "minimum": 1},
                "result": _VALUE_VECTOR,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "dimension", "result", "precision"],
        ),
        _numeric_linear_algebra_schema(
            "least_squares",
            {
                "classification": {"enum": ["full_rank", "rank_deficient"]},
                "solutionUnique": {"type": "boolean"},
                "solutionConvention": {
                    "enum": [
                        "unique_least_squares_minimizer",
                        "minimum_euclidean_norm",
                    ]
                },
                "solution": _TEXT_VECTOR,
                "residualNorm": {"type": "string"},
                "relativeResidualNorm": {"type": "string"},
            },
            [
                "classification",
                "solutionUnique",
                "solutionConvention",
                "solution",
                "residualNorm",
                "relativeResidualNorm",
            ],
        ),
        _numeric_linear_algebra_schema(
            "qr",
            {
                "mode": {"enum": ["reduced", "complete"]},
                "q": _TEXT_MATRIX,
                "r": _TEXT_MATRIX,
                "reconstructionError": {"type": "string"},
                "orthogonalityError": {"type": "string"},
            },
            ["mode", "q", "r", "reconstructionError", "orthogonalityError"],
        ),
        _numeric_linear_algebra_schema(
            "svd",
            {
                "fullMatrices": {"type": "boolean"},
                "u": _TEXT_MATRIX,
                "vTranspose": _TEXT_MATRIX,
                "reconstructionError": {"type": "string"},
            },
            ["fullMatrices", "u", "vTranspose", "reconstructionError"],
        ),
        _numeric_linear_algebra_schema(
            "pseudoinverse",
            {
                "pseudoinverse": _TEXT_MATRIX,
                "penroseResiduals": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "aAaMinusA": {"type": "string"},
                        "aPlusAaPlusMinusAPlus": {"type": "string"},
                        "aAaSymmetry": {"type": "string"},
                        "aPlusASymmetry": {"type": "string"},
                    },
                    "required": [
                        "aAaMinusA",
                        "aPlusAaPlusMinusAPlus",
                        "aAaSymmetry",
                        "aPlusASymmetry",
                    ],
                },
            },
            ["pseudoinverse", "penroseResiduals"],
        ),
)
