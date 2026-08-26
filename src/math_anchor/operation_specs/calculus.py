from __future__ import annotations

from .shared import (
    OperationSpec,
    _EXACT_VECTOR,
    _EXPRESSION,
    _PRECISION,
    _VARIABLES,
    _object,
    calculus,
)


SPECS = (
    OperationSpec(
        id="calculus.derivative",
        category="calculus",
        summary="Differentiate a symbolic expression.",
        description="Compute a derivative of order 1 through 10 with respect to one variable.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "order": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
                "precision": _PRECISION,
            },
            ("expression", "variable"),
        ),
        examples=({"expression": "sin(x) * exp(x)", "variable": "x"},),
        handler=calculus.derivative,
        keywords=("differentiate", "slope", "rate of change", "求导", "导数", "微分"),
    ),
    OperationSpec(
        id="calculus.integrate",
        category="calculus",
        summary="Integrate a symbolic expression.",
        description="Compute an indefinite integral or a definite integral when both bounds are supplied.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "lower": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                "upper": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                "precision": _PRECISION,
            },
            ("expression", "variable"),
        ),
        examples=(
            {"expression": "x^2", "variable": "x"},
            {"expression": "sin(x)", "variable": "x", "lower": 0, "upper": "pi"},
        ),
        handler=calculus.integrate,
        keywords=("integral", "area", "antiderivative", "积分", "定积分", "不定积分"),
    ),
    OperationSpec(
        id="calculus.limit",
        category="calculus",
        summary="Compute a symbolic limit.",
        description="Compute a two-sided, left-hand, or right-hand limit at a finite or infinite point.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "point": {"type": "string"},
                "direction": {"type": "string", "enum": ["+", "-", "+-"], "default": "+-"},
                "precision": _PRECISION,
            },
            ("expression", "variable", "point"),
        ),
        examples=({"expression": "sin(x)/x", "variable": "x", "point": "0"},),
        handler=calculus.limit,
        keywords=("approaches", "asymptote", "convergence", "极限", "趋近", "收敛"),
    ),
    OperationSpec(
        id="calculus.series",
        category="calculus",
        summary="Expand a function as a Taylor or Laurent series.",
        description="Return a symbolic series about an explicit point through a bounded order, including the order term.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "point": {"oneOf": [{"type": "number"}, {"type": "string"}], "default": "0"},
                "order": {"type": "integer", "minimum": 1, "maximum": 50, "default": 6},
                "precision": _PRECISION,
            },
            ("expression", "variable"),
        ),
        examples=({"expression": "exp(x)", "variable": "x", "point": 0, "order": 6},),
        handler=calculus.series,
        keywords=("Taylor", "Laurent", "power series", "级数展开", "泰勒展开", "洛朗展开"),
    ),
    OperationSpec(
        id="calculus.multivariate",
        category="calculus",
        summary="Compute scalar or vector multivariate derivatives.",
        description="Compute a gradient, Jacobian, Hessian, unnormalized directional derivative, divergence, curl, or Laplacian with respect to an ordered variable list.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["gradient", "hessian", "laplacian"]},
                        "expression": _EXPRESSION,
                        "variables": {**_VARIABLES, "maxItems": 8},
                        "precision": _PRECISION,
                    },
                    ("action", "expression", "variables"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["jacobian", "divergence", "curl"]},
                        "expressions": {
                            "type": "array",
                            "items": _EXPRESSION,
                            "minItems": 1,
                            "maxItems": 16,
                        },
                        "variables": {**_VARIABLES, "maxItems": 8},
                        "precision": _PRECISION,
                    },
                    ("action", "expressions", "variables"),
                ),
                _object(
                    {
                        "action": {"const": "directional_derivative"},
                        "expression": _EXPRESSION,
                        "variables": {**_VARIABLES, "maxItems": 8},
                        "direction": {
                            **_EXACT_VECTOR,
                            "maxItems": 8,
                            "description": "Exact vector applied as supplied; it is not normalized.",
                        },
                        "precision": _PRECISION,
                    },
                    ("action", "expression", "variables", "direction"),
                ),
            ]
        },
        examples=(
            {"action": "gradient", "expression": "x^2 + x*y + y^2", "variables": ["x", "y"]},
            {"action": "jacobian", "expressions": ["x*y", "x+y"], "variables": ["x", "y"]},
            {"action": "curl", "expressions": ["y*z", "x*z", "x*y"], "variables": ["x", "y", "z"]},
            {"action": "directional_derivative", "expression": "x^2 + y^2", "variables": ["x", "y"], "direction": [3, 4]},
        ),
        handler=calculus.multivariate,
        keywords=("gradient", "Jacobian", "Hessian", "directional derivative", "divergence", "curl", "Laplacian", "multivariable", "梯度", "雅可比", "海森矩阵", "方向导数", "散度", "旋度", "拉普拉斯算子", "多元微分"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
