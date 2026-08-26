from __future__ import annotations

from .shared import (
    _SHAPE,
    _TEXT_MATRIX_OR_NULL,
    _TEXT_OR_NULL,
    _VALUE,
    _ok_schema,
)


RESULT_VARIANTS = (
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
            "derivative_scalar",
            {
                "action": {
                    "enum": [
                        "directional_derivative",
                        "divergence",
                        "laplacian",
                    ]
                },
                "variables": {"type": "array", "items": {"type": "string"}},
                "exact": _TEXT_OR_NULL,
                "approx": _TEXT_OR_NULL,
                "precision": {"type": "integer", "minimum": 2},
            },
            ["action", "variables", "exact", "approx", "precision"],
        ),
        _ok_schema(
            "derivative_matrix",
            {
                "action": {
                    "enum": [
                        "gradient",
                        "jacobian",
                        "hessian",
                        "curl",
                    ]
                },
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
)
