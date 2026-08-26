from __future__ import annotations

from .shared import (
    OperationSpec,
    _CANDIDATE,
    _DECIMAL_TEXT,
    _EXPRESSION,
    _PRECISION,
    _object,
    verification,
)


SPECS = (
    OperationSpec(
        id="expression.equivalent",
        category="verification",
        summary="Verify semantic equivalence of two expressions.",
        description="Compare values under an explicit real or complex domain, with a strict option that also requires the same definedness domain; return a proof, counterexample, or honest unknown.",
        input_schema=_object(
            {
                "left": _EXPRESSION,
                "right": _EXPRESSION,
                "variables": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 16},
                "domain": {"type": "string", "enum": ["real", "complex"], "default": "real"},
                "definednessPolicy": {"type": "string", "enum": ["strict", "common_domain"], "default": "strict"},
                "precision": _PRECISION,
            },
            ("left", "right", "variables"),
        ),
        examples=(
            {"left": "(x^2 - 1)/(x - 1)", "right": "x + 1", "variables": ["x"], "domain": "real"},
            {"left": "sin(x)^2 + cos(x)^2", "right": "1", "variables": ["x"], "domain": "real"},
        ),
        handler=verification.expression_equivalent,
        keywords=("semantic equivalence", "same expression", "identity", "等价性验证", "恒等式", "表达式等价"),
    ),
    OperationSpec(
        id="solution.verify",
        category="verification",
        summary="Verify candidate solutions against equations or inequalities.",
        description="Substitute one or more candidates into bounded constraints, report every residual, apply an explicit numeric tolerance, and optionally assess omissions for a finite univariate equation.",
        input_schema=_object(
            {
                "constraints": {
                    "oneOf": [
                        {"type": "string", "maxLength": 4096},
                        {"type": "array", "items": {"type": "string", "maxLength": 4096}, "minItems": 1, "maxItems": 16},
                    ]
                },
                "variables": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                "candidates": {"type": "array", "items": _CANDIDATE, "minItems": 1, "maxItems": 64},
                "domain": {"type": "string", "enum": ["real", "complex"], "default": "real"},
                "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                "checkCompleteness": {"type": "boolean", "default": False},
                "precision": _PRECISION,
            },
            ("constraints", "variables", "candidates"),
        ),
        examples=(
            {"constraints": "x^2 = 2", "variables": ["x"], "candidates": [{"x": "sqrt(2)"}, {"x": "-sqrt(2)"}], "checkCompleteness": True},
            {"constraints": ["x + y = 7", "x > y"], "variables": ["x", "y"], "candidates": [{"x": 4, "y": 3}]},
        ),
        handler=verification.solution_verify,
        keywords=("check solution", "substitute", "residual", "omitted roots", "解验证", "验根", "候选解", "残差"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
