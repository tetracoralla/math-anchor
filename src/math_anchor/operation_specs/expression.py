from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _EXPRESSION,
    _PRECISION,
    _object,
    expression,
)


SPECS = (
    OperationSpec(
        id="expression.evaluate",
        category="expression",
        summary="Evaluate an arithmetic or scientific expression.",
        description="Evaluate a safe expression with exact symbolic arithmetic where possible and an explicit approximation, including registered Airy, Bessel, beta, gamma, error, Lambert W, polygamma, and zeta functions.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variables": {
                    "type": "object",
                    "additionalProperties": {"oneOf": [{"type": "number"}, {"type": "string"}]},
                    "maxProperties": 16,
                },
                "precision": _PRECISION,
            },
            ("expression",),
        ),
        examples=(
            {"expression": "sqrt(2)", "precision": 50},
            {"expression": "airyai(0) + bessely(0, 1) + polygamma(1, 1)", "precision": 40},
            {"expression": "power * hours * days", "variables": {"power": 72, "hours": 9.5, "days": 30}},
        ),
        handler=expression.evaluate,
        backends=("sympy",),
        keywords=("calculate", "arithmetic", "scientific", "trigonometry", "logarithm", "Airy", "Bessel", "beta", "gamma", "polygamma", "special functions", "计算", "算术", "科学计算", "特殊函数"),
    ),
    OperationSpec(
        id="expression.simplify",
        category="expression",
        summary="Simplify a symbolic expression.",
        description="Parse a symbolic expression through the safe grammar and ask SymPy for a simpler equivalent form.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variables": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
                "precision": _PRECISION,
            },
            ("expression",),
        ),
        examples=({"expression": "(x^2 - 1)/(x - 1)", "variables": ["x"]},),
        handler=expression.simplify,
        backends=("sympy",),
        keywords=("reduce", "simplify", "symbolic", "化简", "约简"),
    ),
    OperationSpec(
        id="function.sample",
        category="expression",
        summary="Evaluate an expression at many points in one call.",
        description="Build a function table from an explicit point list (up to 256 exact numeric expressions) or an even grid (up to 1000 points). Each row keeps exact and approximate provenance; points outside the expression's domain are reported as undefined rows instead of failing the table. One call replaces repeated single-point evaluations.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "points": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 256},
                    "minItems": 1,
                    "maxItems": 256,
                    "description": "Explicit numeric expression texts to evaluate at.",
                },
                "lower": _DECIMAL_TEXT,
                "upper": _DECIMAL_TEXT,
                "count": {"type": "integer", "minimum": 2, "maximum": 1000, "default": 20},
                "precision": _PRECISION,
            },
            ("expression", "variable"),
        ),
        examples=(
            {"expression": "sin(x)/x", "variable": "x", "lower": "-3", "upper": "3", "count": 13},
            {"expression": "exp(-x^2)", "variable": "x", "points": ["-2", "-1", "0", "1", "2"]},
        ),
        handler=expression.sample,
        keywords=("function table", "sample", "evaluate at points", "plot data", "grid", "函数表", "采样", "多点求值", "绘图数据"),
        backends=("mpmath", "sympy"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
