from __future__ import annotations

from .shared import (
    OperationSpec,
    _EXPRESSION,
    _PRECISION,
    _VARIABLES,
    _object,
    algebra,
)


SPECS = (
    OperationSpec(
        id="algebra.transform",
        category="algebra",
        summary="Transform an expression into a requested algebraic form.",
        description="Apply one explicit symbolic transformation: simplify, expand, factor, cancel, partial fractions, or collect by a variable.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["simplify", "expand", "factor", "cancel"]},
                        "expression": _EXPRESSION,
                        "variables": {**_VARIABLES, "minItems": 0},
                        "precision": _PRECISION,
                    },
                    ("action", "expression"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["apart", "collect"]},
                        "expression": _EXPRESSION,
                        "variable": {"type": "string"},
                        "variables": {**_VARIABLES, "minItems": 0},
                        "precision": _PRECISION,
                    },
                    ("action", "expression", "variable"),
                ),
            ]
        },
        examples=(
            {"action": "factor", "expression": "x^2 - 1", "variables": ["x"]},
            {"action": "apart", "expression": "1/(x*(x+1))", "variable": "x"},
        ),
        handler=algebra.transform,
        backends=("sympy",),
        keywords=("expand", "factor", "partial fractions", "collect", "展开", "因式分解", "部分分式", "合并同类项"),
    ),
    OperationSpec(
        id="algebra.solve",
        category="algebra",
        summary="Solve one equation or a system symbolically.",
        description="Return a classified symbolic solution set, whether completeness is proven, and finite solutions separately when enumerable.",
        input_schema=_object(
            {
                "equations": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 16},
                    ]
                },
                "variables": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                "domain": {"type": "string", "enum": ["real", "complex"], "default": "complex"},
                "precision": _PRECISION,
            },
            ("equations", "variables"),
        ),
        examples=(
            {"equations": "x^3 - 2*x - 5 = 0", "variables": ["x"], "domain": "real", "precision": 50},
            {"equations": ["x + y = 7", "x - y = 1"], "variables": ["x", "y"]},
        ),
        handler=algebra.solve,
        backends=("sympy",),
        keywords=("equation", "system", "roots", "unknowns", "解方程", "方程组", "求解"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
