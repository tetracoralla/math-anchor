from __future__ import annotations

from .shared import (
    OperationSpec,
    _DIMENSION_EQUATION,
    _DIMENSION_EXPRESSION_TEXT,
    _DIMENSION_PI_VARIABLES,
    _DIMENSION_SYMBOLS,
    _DIMENSION_SYMBOL_NAME,
    _object,
    dimension,
)


SPECS = (
    OperationSpec(
        id="dimension.check",
        category="dimension",
        summary="Check a symbolic equation for dimensional consistency.",
        description="Check both sides and additive or function constraints with exact dimension vectors. Consistency does not prove the physical formula.",
        input_schema=_object(
            {
                "left": _DIMENSION_EXPRESSION_TEXT,
                "right": _DIMENSION_EXPRESSION_TEXT,
                "symbols": _DIMENSION_SYMBOLS,
            },
            ("left", "right", "symbols"),
        ),
        examples=(
            {
                "left": "F",
                "right": "m * a",
                "symbols": {"F": "newton", "m": "kilogram", "a": "meter / second^2"},
            },
            {
                "left": "d",
                "right": "v * t + 0.5 * a * t^2",
                "symbols": {
                    "d": "meter",
                    "v": "meter / second",
                    "a": "meter / second^2",
                    "t": "second",
                },
            },
        ),
        handler=dimension.check,
        backends=("pint", "sympy"),
        keywords=(
            "dimensional consistency",
            "dimensional analysis",
            "check formula dimensions",
            "symbolic units",
            "physical equation",
            "量纲检查",
            "量纲分析",
            "量纲一致性",
            "公式维度",
            "物理公式检查",
        ),
        assurance_scope="dimensional_consistency_only",
    ),
    OperationSpec(
        id="dimension.infer",
        category="dimension",
        summary="Infer unknown symbol dimensions from equations.",
        description="Solve exact dimensional constraints and report unique, underdetermined, or inconsistent results. Dimensions are not units.",
        input_schema=_object(
            {
                "equations": {
                    "type": "array",
                    "items": _DIMENSION_EQUATION,
                    "minItems": 1,
                    "maxItems": 32,
                },
                "known": _DIMENSION_SYMBOLS,
                "unknown": {
                    "type": "array",
                    "items": _DIMENSION_SYMBOL_NAME,
                    "minItems": 1,
                    "maxItems": 16,
                    "uniqueItems": True,
                },
            },
            ("equations", "unknown"),
        ),
        examples=(
            {
                "equations": [{"left": "F", "right": "m * a"}],
                "known": {"F": "newton", "m": "kilogram"},
                "unknown": ["a"],
            },
            {
                "equations": [{"left": "z", "right": "x * y"}],
                "known": {"z": {"length": "1"}},
                "unknown": ["x", "y"],
            },
        ),
        handler=dimension.infer,
        backends=("pint", "sympy"),
        keywords=(
            "infer dimensions",
            "infer variable dimension",
            "infer acceleration dimension",
            "unknown dimension",
            "dimension constraints",
            "formula analysis",
            "推断未知变量的量纲",
            "推断量纲",
            "未知维度",
            "量纲约束",
            "公式推理",
        ),
        assurance_scope="dimensional_consistency_only",
    ),
    OperationSpec(
        id="dimension.pi_groups",
        category="dimension",
        summary="Construct a basis of dimensionless Buckingham Pi groups.",
        description="Return a deterministic primitive-integer basis for the dimensionless products spanned by declared variables. Equivalent bases are possible.",
        input_schema=_object(
            {
                "variables": _DIMENSION_PI_VARIABLES,
            },
            ("variables",),
        ),
        examples=(
            {
                "variables": {
                    "rho": "kilogram / meter^3",
                    "v": "meter / second",
                    "L": "meter",
                    "mu": "pascal * second",
                }
            },
            {
                "variables": {
                    "force": "newton",
                    "density": "kilogram / meter^3",
                    "speed": "meter / second",
                    "length": "meter",
                }
            },
        ),
        handler=dimension.pi_groups,
        backends=("pint", "sympy"),
        keywords=(
            "Buckingham Pi theorem",
            "Buckingham π theorem",
            "dimensionless groups",
            "dimensionless products",
            "similarity analysis",
            "Pi groups",
            "无量纲组合",
            "白金汉π定理",
            "白金汉 Pi 定理",
            "相似性分析",
        ),
        assurance_scope="dimensionless_basis_only",
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
