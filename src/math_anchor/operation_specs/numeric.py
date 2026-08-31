from __future__ import annotations

from .shared import (
    OperationSpec,
    _APPROXIMATE_MATRIX,
    _APPROXIMATE_VECTOR,
    _DECIMAL_TEXT,
    _DECIMAL_VALUE_SCHEMA,
    _EXPRESSION,
    _IEEE_FORMAT,
    _IEEE_INPUT_MODE,
    _IEEE_VALUE,
    _NUMERIC_LINALG_MATRIX,
    _NUMERIC_LINALG_VECTOR,
    _PRECISION,
    _object,
    calculus,
    floating,
    linear_algebra,
    numerical,
    optimization,
)


SPECS = (
    OperationSpec(
        id="numeric.root",
        category="numeric",
        summary="Find a numerical root inside a bracket, optionally all sign-changing roots.",
        description="Find a bracketed real root at the requested decimal precision without claiming an exact symbolic value. Uses the Illinois bracketed solver: superlinear for smooth functions, bisection-fallback safeguarded, with the same rigorous bracket-width error bound as bisection. With findAll, scan the bracket on a caller-chosen resolution grid and return every sign-changing root; even-multiplicity roots or roots closer together than the resolution can be missed and that limitation is reported.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "bracket": {
                    "type": "array",
                    "items": _DECIMAL_VALUE_SCHEMA,
                    "minItems": 2,
                    "maxItems": 2,
                },
                "tolerance": _DECIMAL_TEXT,
                "maxIterations": {"type": "integer", "minimum": 1, "maximum": 2_000, "default": 512},
                "precision": {**_PRECISION, "maximum": 50},
                "findAll": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enumerate every sign-changing root in the bracket instead of one.",
                },
                "resolution": {
                    "type": "integer",
                    "minimum": 16,
                    "maximum": 4096,
                    "default": 64,
                    "description": "Grid segment count used to locate sign changes when findAll is enabled.",
                },
            },
            ("expression", "variable", "bracket"),
        ),
        examples=(
            {"expression": "x^3 - 2*x - 5", "variable": "x", "bracket": ["2", "3"], "tolerance": "1e-30", "precision": 30},
            {"expression": "sin(x)", "variable": "x", "bracket": ["-10", "10"], "findAll": True, "resolution": 256},
        ),
        handler=calculus.numeric_root,
        keywords=("numerically solve", "nonlinear", "high precision", "zero", "all roots", "数值求根", "数值解", "零点", "所有根"),
        assurance="diagnostic",
        assurance_scope="bracketed_roots_under_declared_resolution",
        backends=("mpmath", "sympy"),
    ),
    OperationSpec(
        id="numeric.integrate",
        category="numeric",
        summary="Numerically integrate over a finite real interval with an error estimate.",
        description="Use a stratified deterministic probe plus adaptive embedded Clenshaw-Curtis (CC17/CC9) refinement with explicit tolerances and an estimated interval. Without caller-supplied breakpoints or a minimum featureScale, the result is machine-readably uncertain because arbitrary narrow features cannot be excluded.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "lower": _DECIMAL_TEXT,
                "upper": _DECIMAL_TEXT,
                "absoluteTolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                "relativeTolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                "maxEvaluations": {"type": "integer", "minimum": 5, "maximum": 1_000_000, "default": 100_000},
                "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                "breakpoints": {
                    "type": "array",
                    "items": _DECIMAL_TEXT,
                    "maxItems": 64,
                    "description": "Caller-supplied points identifying every material discontinuity or localized feature.",
                },
                "featureScale": {
                    **_DECIMAL_TEXT,
                    "description": "Caller-supplied lower bound on the width of every material feature over the interval.",
                },
            },
            ("expression", "variable", "lower", "upper"),
        ),
        examples=(
            {"expression": "sin(x)", "variable": "x", "lower": "0", "upper": "3.14159265358979323846"},
            {"expression": "exp(-x^2)", "variable": "x", "lower": "-1", "upper": "1", "absoluteTolerance": "1e-20", "relativeTolerance": "1e-20", "precision": 30},
        ),
        handler=numerical.integrate,
        keywords=("numerical integration", "quadrature", "error estimate", "adaptive Clenshaw-Curtis", "数值积分", "误差估计", "区间结果"),
        assurance="diagnostic",
        assurance_scope="estimated_quadrature_interval_not_rigorous_enclosure",
        backends=("mpmath", "sympy"),
    ),
    OperationSpec(
        id="numeric.minimize",
        category="numeric",
        summary="Bound a global minimum or maximum over a bracket with interval arithmetic.",
        description="Interval-arithmetic branch and bound returns an internal enclosure of the global extremum value plus cover intervals for every minimizer over the supported expression subset, or degrades honestly to the best bound obtained when the evaluation budget runs out. The expression must be defined everywhere on the bracket; brackets containing poles or undefined points are rejected. This is not an external certificate or a proof-kernel result.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "variable": {"type": "string"},
                "bracket": {
                    "type": "array",
                    "items": _DECIMAL_VALUE_SCHEMA,
                    "minItems": 2,
                    "maxItems": 2,
                },
                "objective": {
                    "type": "string",
                    "enum": ["minimum", "maximum"],
                    "default": "minimum",
                    "description": "Search for the global minimum or maximum.",
                },
                "tolerance": {
                    **_DECIMAL_TEXT,
                    "default": "1e-12",
                    "description": "Requested width of the internal value enclosure.",
                },
                "argminTolerance": {
                    **_DECIMAL_TEXT,
                    "default": "1e-8",
                    "description": "Requested maximum width of each reported extremum interval.",
                },
                "maxEvaluations": {"type": "integer", "minimum": 32, "maximum": 1_000_000, "default": 20_000},
                "precision": {**_PRECISION, "minimum": 16, "maximum": 100, "default": 30},
            },
            ("expression", "variable", "bracket"),
        ),
        examples=(
            {"expression": "x^2 - 2", "variable": "x", "bracket": ["-2", "2"]},
            {"expression": "sin(x) + x/3", "variable": "x", "bracket": ["-4", "4"], "objective": "minimum"},
        ),
        handler=optimization.minimize,
        keywords=("global minimum", "global maximum", "optimization", "argmin", "interval bound", "interval arithmetic", "全局最优", "最小值", "最大值", "区间分支定界"),
        assurance="diagnostic",
        assurance_scope="internal_mpmath_interval_enclosure_for_supported_expression_subset",
        backends=("mpmath", "sympy"),
    ),
    OperationSpec(
        id="float.ieee754",
        category="numeric",
        summary="Inspect or compare IEEE 754 binary32/binary64 values, bits, rounding, neighbors, and ULP distance.",
        description="Convert explicit decimal text or raw bits under IEEE 754 ties-to-even semantics and expose classification, sign/exponent/significand fields, exact represented value, rounding direction, adjacent values, and comparisons without claiming decimal input stayed exact.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "inspect"},
                        "value": _IEEE_VALUE,
                        "format": _IEEE_FORMAT,
                        "inputMode": _IEEE_INPUT_MODE,
                    },
                    ("action", "value"),
                ),
                _object(
                    {
                        "action": {"const": "compare"},
                        "left": _IEEE_VALUE,
                        "right": _IEEE_VALUE,
                        "format": _IEEE_FORMAT,
                        "inputMode": _IEEE_INPUT_MODE,
                    },
                    ("action", "left", "right"),
                ),
            ]
        },
        examples=(
            {"action": "inspect", "value": "0.1", "format": "binary64"},
            {"action": "inspect", "value": "0x3F800000", "format": "binary32", "inputMode": "bits"},
            {"action": "compare", "left": "0.1", "right": "0.10000000000000001", "format": "binary64"},
        ),
        handler=floating.ieee754,
        backends=("python",),
        keywords=("IEEE 754", "binary32", "binary64", "float bits", "ULP", "subnormal", "NaN", "rounding error", "浮点", "尾数", "指数", "舍入误差"),
    ),
    OperationSpec(
        id="matrix.solve_approximate",
        category="numeric",
        summary="Solve an approximate square linear system with stability diagnostics.",
        description="Convert decimal-text entries to binary64, apply an explicit rank tolerance, and report the condition number, residual, backward error, and a relative forward-error bound when available.",
        input_schema=_object(
            {
                "matrix": _APPROXIMATE_MATRIX,
                "constants": _APPROXIMATE_VECTOR,
                "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                "precision": {"type": "integer", "minimum": 2, "maximum": 15, "default": 15},
            },
            ("matrix", "constants"),
        ),
        examples=(
            {"matrix": [["3", "1"], ["1", "2"]], "constants": ["9", "8"], "tolerance": "1e-12"},
            {"matrix": [["1", "1"], ["1", "1.000000000001"]], "constants": ["2", "2.000000000001"], "tolerance": "1e-12"},
        ),
        handler=numerical.solve_approximate_linear_system,
        keywords=("numerical linear algebra", "condition number", "backward error", "ill conditioned", "数值线性代数", "条件数", "病态矩阵", "数值稳定性"),
        assurance="diagnostic",
        assurance_scope="binary64_solution_under_declared_rank_tolerance",
        backends=("numpy",),
    ),
    OperationSpec(
        id="linear_algebra.numeric",
        category="numeric",
        summary="Run binary64 least squares, QR, SVD, or Moore-Penrose pseudoinverse with diagnostics.",
        description="Convert decimal text to binary64, use an explicit relative singular-value tolerance, and report rank, condition number, residual or reconstruction diagnostics without claiming exactness; least squares states uniqueness and the minimum-norm selection convention.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "least_squares"},
                        "matrix": _NUMERIC_LINALG_MATRIX,
                        "constants": _NUMERIC_LINALG_VECTOR,
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                        "precision": {"type": "integer", "minimum": 2, "maximum": 15, "default": 15},
                    },
                    ("action", "matrix", "constants"),
                ),
                _object(
                    {
                        "action": {"const": "qr"},
                        "matrix": _NUMERIC_LINALG_MATRIX,
                        "mode": {"type": "string", "enum": ["reduced", "complete"], "default": "reduced"},
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                        "precision": {"type": "integer", "minimum": 2, "maximum": 15, "default": 15},
                    },
                    ("action", "matrix"),
                ),
                _object(
                    {
                        "action": {"const": "svd"},
                        "matrix": _NUMERIC_LINALG_MATRIX,
                        "fullMatrices": {"type": "boolean", "default": False},
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                        "precision": {"type": "integer", "minimum": 2, "maximum": 15, "default": 15},
                    },
                    ("action", "matrix"),
                ),
                _object(
                    {
                        "action": {"const": "pseudoinverse"},
                        "matrix": _NUMERIC_LINALG_MATRIX,
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-12"},
                        "precision": {"type": "integer", "minimum": 2, "maximum": 15, "default": 15},
                    },
                    ("action", "matrix"),
                ),
            ]
        },
        examples=(
            {"action": "least_squares", "matrix": [["1", "0"], ["1", "1"], ["1", "2"]], "constants": ["1", "2", "2"]},
            {"action": "svd", "matrix": [["3", "0"], ["0", "2"]]},
            {"action": "pseudoinverse", "matrix": [["2", "0"], ["0", "0"]]},
        ),
        handler=linear_algebra.numeric,
        keywords=("least squares", "QR decomposition", "SVD", "singular value decomposition", "pseudoinverse", "Moore Penrose", "numerical linear algebra", "最小二乘", "QR分解", "奇异值分解", "伪逆"),
        assurance="diagnostic",
        assurance_scope="binary64_linear_algebra_under_declared_tolerance",
        backends=("numpy",),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
