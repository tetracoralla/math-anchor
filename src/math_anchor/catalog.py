from __future__ import annotations

import re
from typing import Any

from .errors import CalculatorError
from .models import OperationSpec
from .operations import (
    algebra,
    calculus,
    combinatorics,
    data,
    expression,
    finance,
    inference,
    matrix,
    number_theory,
    numerical,
    optimization,
    probability,
    quantity,
    verification,
)


MAX_SEARCH_QUERY_LENGTH = 256
MAX_CATEGORY_LENGTH = 64
MAX_OPERATION_ID_LENGTH = 128


_PRECISION = {
    "type": "integer",
    "minimum": 2,
    "maximum": 200,
    "default": 16,
    "description": "Decimal digits used for approximate output.",
}
_EXPRESSION = {
    "type": "string",
    "maxLength": 4096,
    "description": "Safe mathematical expression. Use explicit * for multiplication and ^ or ** for powers.",
}
_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 50,
        "items": {"oneOf": [{"type": "number"}, {"type": "string"}]},
    },
}
_EXACT_CELL = {
    "oneOf": [
        {"type": "integer"},
        {
            "type": "string",
            "maxLength": 256,
            "description": "Exact integer or rational expression text such as 1/10.",
        },
    ]
}
_EXACT_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 50,
        "items": _EXACT_CELL,
    },
}
_EXACT_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 50,
    "items": _EXACT_CELL,
}
_MAX_STANDARD_INTEGER = 9_007_199_254_740_991
_EXACT_INTEGER = {
    "oneOf": [
        {
            "type": "integer",
            "minimum": -_MAX_STANDARD_INTEGER,
            "maximum": _MAX_STANDARD_INTEGER,
        },
        {
            "type": "string",
            "pattern": r"^[+-]?\d+$",
            "maxLength": 17,
        },
    ]
}
_POSITIVE_MODULUS = {
    "oneOf": [
        {
            "type": "integer",
            "minimum": 2,
            "maximum": _MAX_STANDARD_INTEGER,
        },
        {
            "type": "string",
            "pattern": r"^(?:[+]?[2-9]|[+]?[1-9]\d+)$",
            "maxLength": 17,
        },
    ]
}
_VARIABLES = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "maxItems": 16,
}
_DECIMAL_TEXT = {
    "type": "string",
    "pattern": r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$",
    "maxLength": 256,
    "description": "Decimal text for exact decimal provenance, such as 0.1 or 1e-6.",
}
_DECIMAL_VALUE_SCHEMA = {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]}
_DECIMAL_TEXT_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100_000,
    "items": _DECIMAL_TEXT,
}
_APPROXIMATE_MATRIX = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100,
    "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 100,
        "items": _DECIMAL_TEXT,
    },
}
_APPROXIMATE_VECTOR = {
    "type": "array",
    "minItems": 1,
    "maxItems": 100,
    "items": _DECIMAL_TEXT,
}
_CANDIDATE = {
    "type": "object",
    "propertyNames": {"pattern": r"^[A-Za-z_][A-Za-z0-9_]*$"},
    "additionalProperties": {"oneOf": [{"type": "number"}, {"type": "string", "maxLength": 4096}]},
    "minProperties": 1,
    "maxProperties": 8,
}


def _object(
    properties: dict[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


_SPECS = (
    OperationSpec(
        id="expression.evaluate",
        category="expression",
        summary="Evaluate an arithmetic or scientific expression.",
        description="Evaluate a safe expression with exact symbolic arithmetic where possible and an explicit approximation.",
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
            {"expression": "power * hours * days", "variables": {"power": 72, "hours": 9.5, "days": 30}},
        ),
        handler=expression.evaluate,
        keywords=("calculate", "arithmetic", "scientific", "trigonometry", "logarithm", "计算", "算术", "科学计算"),
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
    ),
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
        keywords=("equation", "system", "roots", "unknowns", "解方程", "方程组", "求解"),
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
        summary="Compute a gradient, Jacobian, or Hessian.",
        description="Differentiate one scalar expression or a vector of expressions with respect to an ordered variable list.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["gradient", "hessian"]},
                        "expression": _EXPRESSION,
                        "variables": {**_VARIABLES, "maxItems": 8},
                        "precision": _PRECISION,
                    },
                    ("action", "expression", "variables"),
                ),
                _object(
                    {
                        "action": {"const": "jacobian"},
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
            ]
        },
        examples=(
            {"action": "gradient", "expression": "x^2 + x*y + y^2", "variables": ["x", "y"]},
            {"action": "jacobian", "expressions": ["x*y", "x+y"], "variables": ["x", "y"]},
        ),
        handler=calculus.multivariate,
        keywords=("gradient", "Jacobian", "Hessian", "multivariable", "梯度", "雅可比", "海森矩阵", "多元微分"),
    ),
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
    ),
    OperationSpec(
        id="numeric.minimize",
        category="numeric",
        summary="Certifiably locate the global minimum or maximum over a bracket.",
        description="Interval-arithmetic branch and bound returns a rigorous enclosure of the global extremum value plus cover intervals for every minimizer, or degrades honestly to the best certified bound when the evaluation budget runs out. The expression must be defined everywhere on the bracket; brackets containing poles or undefined points are rejected rather than certified.",
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
                    "description": "Requested width of the certified value enclosure.",
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
        keywords=("global minimum", "global maximum", "optimization", "argmin", "certified", "interval arithmetic", "全局最优", "最小值", "最大值", "区间分支定界"),
    ),
    OperationSpec(
        id="integer.factorization",
        category="integer",
        summary="Test primality and return an exact prime factorization.",
        description="Factor one bounded nonzero integer into ordered prime powers and report its sign and primality.",
        input_schema=_object({"value": _EXACT_INTEGER}, ("value",)),
        examples=({"value": 360}, {"value": "9007199254740991"}),
        handler=number_theory.factorization,
        keywords=("prime factors", "is prime", "factor integer", "质因数分解", "素数判断", "整数分解"),
    ),
    OperationSpec(
        id="integer.gcd_lcm",
        category="integer",
        summary="Compute the exact GCD and LCM of integers.",
        description="Return the nonnegative greatest common divisor and least common multiple for one bounded integer list.",
        input_schema=_object(
            {
                "values": {
                    "type": "array",
                    "items": _EXACT_INTEGER,
                    "minItems": 1,
                    "maxItems": 128,
                }
            },
            ("values",),
        ),
        examples=({"values": [12, 18, 30]},),
        handler=number_theory.gcd_lcm,
        keywords=("greatest common divisor", "least common multiple", "gcd", "lcm", "最大公约数", "最小公倍数"),
    ),
    OperationSpec(
        id="integer.modular",
        category="integer",
        summary="Compute a modular remainder, power, or inverse.",
        description="Perform one explicit bounded modular arithmetic operation and return an exact canonical residue.",
        input_schema={
            "oneOf": [
                _object(
                    {"action": {"const": "remainder"}, "value": _EXACT_INTEGER, "modulus": _POSITIVE_MODULUS},
                    ("action", "value", "modulus"),
                ),
                _object(
                    {
                        "action": {"const": "power"},
                        "value": _EXACT_INTEGER,
                        "exponent": {"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
                        "modulus": _POSITIVE_MODULUS,
                    },
                    ("action", "value", "exponent", "modulus"),
                ),
                _object(
                    {"action": {"const": "inverse"}, "value": _EXACT_INTEGER, "modulus": _POSITIVE_MODULUS},
                    ("action", "value", "modulus"),
                ),
            ]
        },
        examples=(
            {"action": "power", "value": 7, "exponent": 128, "modulus": 13},
            {"action": "inverse", "value": 3, "modulus": 11},
        ),
        handler=number_theory.modular,
        keywords=("modulo", "modular inverse", "modular exponent", "模运算", "模逆", "模幂"),
    ),
    OperationSpec(
        id="combinatorics.count",
        category="combinatorics",
        summary="Compute an exact combination, permutation, or multinomial count.",
        description="Return one bounded exact combinatorial count with an explicit counting convention.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["binomial", "permutations"]},
                        "n": {"type": "integer", "minimum": 0, "maximum": 5_000},
                        "k": {"type": "integer", "minimum": 0, "maximum": 5_000},
                    },
                    ("action", "n", "k"),
                ),
                _object(
                    {
                        "action": {"const": "multinomial"},
                        "counts": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 0, "maximum": 5_000},
                            "minItems": 1,
                            "maxItems": 128,
                        },
                    },
                    ("action", "counts"),
                ),
            ]
        },
        examples=(
            {"action": "binomial", "n": 52, "k": 5},
            {"action": "multinomial", "counts": [2, 3, 1]},
        ),
        handler=combinatorics.count,
        keywords=("combination", "permutation", "multinomial", "choose", "组合数", "排列数", "多项式系数"),
    ),
    OperationSpec(
        id="matrix.determinant",
        category="matrix",
        summary="Compute a square matrix determinant.",
        description="Compute the exact determinant of a square matrix.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[1, 2], [3, 4]]},),
        handler=matrix.determinant,
        keywords=("linear algebra", "det", "行列式", "矩阵"),
    ),
    OperationSpec(
        id="matrix.inverse",
        category="matrix",
        summary="Invert a nonsingular square matrix.",
        description="Return a square matrix inverse under the caller's exact/approximate output selection and strict byte budget.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[1, 2], [3, 4]]},),
        handler=matrix.inverse,
        keywords=("linear algebra", "reciprocal matrix", "逆矩阵", "矩阵求逆"),
    ),
    OperationSpec(
        id="matrix.eigenvalues",
        category="matrix",
        summary="Compute square matrix eigenvalues.",
        description="Return eigenvalues with multiplicity, preserving exact values when SymPy can derive them.",
        input_schema=_object({"matrix": _MATRIX, "precision": _PRECISION}, ("matrix",)),
        examples=({"matrix": [[2, 0], [0, 3]]},),
        handler=matrix.eigenvalues,
        keywords=("linear algebra", "spectrum", "characteristic", "特征值", "矩阵特征值"),
    ),
    OperationSpec(
        id="matrix.solve",
        category="matrix",
        summary="Solve one exact linear system A x = b.",
        description="Classify an exact linear system as unique, inconsistent, or infinite and return a particular solution plus nullspace basis when applicable.",
        input_schema=_object(
            {
                "matrix": _EXACT_MATRIX,
                "constants": _EXACT_VECTOR,
                "variables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 50,
                },
                "precision": _PRECISION,
            },
            ("matrix", "constants"),
        ),
        examples=(
            {"matrix": [[1, 1], [1, -1]], "constants": [7, 1], "variables": ["x", "y"]},
            {"matrix": [[1, 2], [2, 4]], "constants": [3, 6]},
        ),
        handler=matrix.solve,
        keywords=("linear system", "Ax=b", "simultaneous equations", "线性方程组", "矩阵求解", "增广矩阵"),
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
    ),
    OperationSpec(
        id="matrix.reduce",
        category="matrix",
        summary="Compute exact rank, RREF, nullspace, or column space.",
        description="Apply one exact structural matrix operation; approximate floating entries are rejected because rank and basis classification require an explicit tolerance policy.",
        input_schema=_object(
            {
                "action": {"type": "string", "enum": ["rank", "rref", "nullspace", "columnspace"]},
                "matrix": _EXACT_MATRIX,
                "precision": _PRECISION,
            },
            ("action", "matrix"),
        ),
        examples=(
            {"action": "rref", "matrix": [[1, 2, 3], [2, 4, 6]]},
            {"action": "nullspace", "matrix": [[1, 2], [2, 4]]},
        ),
        handler=matrix.reduce,
        keywords=("rank", "row reduce", "RREF", "null space", "column space", "秩", "行最简形", "零空间", "列空间"),
    ),
    OperationSpec(
        id="statistics.describe",
        category="statistics",
        summary="Compute descriptive statistics for numeric values.",
        description="Return count, mean, median, standard deviation, range, and quartiles; decimal text stays on an exact rational path and approximate inputs use NumPy.",
        input_schema=_object(
            {
                "values": {
                    "type": "array",
                    "items": {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]},
                    "minItems": 1,
                    "maxItems": 100000,
                    "description": "Numbers are approximate when sent as JSON decimals; decimal strings preserve exact decimal provenance.",
                },
                "ddof": {"type": "integer", "minimum": 0, "default": 0},
                "quartileMethod": {"type": "string", "enum": ["linear"], "default": "linear"},
                "precision": _PRECISION,
            },
            ("values",),
        ),
        examples=({"values": [12, 15, 18, 21, 24], "ddof": 1},),
        handler=data.statistics_describe,
        keywords=("mean", "median", "standard deviation", "quartile", "summary", "统计", "平均数", "中位数", "标准差", "四分位数"),
    ),
    OperationSpec(
        id="statistics.infer",
        category="statistics",
        summary="Compute a mean interval, one-sample t test, or simple linear regression.",
        description="Use bounded decimal-text samples and explicit methods to return approximate inferential results, sample constraints, and interpretation assumptions.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "mean_confidence_interval"},
                        "sample": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "confidenceLevel": {**_DECIMAL_TEXT, "default": "0.95"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sample"),
                ),
                _object(
                    {
                        "action": {"const": "one_sample_t_test"},
                        "sample": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "nullMean": _DECIMAL_TEXT,
                        "alternative": {"type": "string", "enum": ["two_sided", "less", "greater"], "default": "two_sided"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sample", "nullMean"),
                ),
                _object(
                    {
                        "action": {"const": "linear_regression"},
                        "x": {**_DECIMAL_TEXT_VECTOR, "minItems": 3},
                        "y": {**_DECIMAL_TEXT_VECTOR, "minItems": 3},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "x", "y"),
                ),
            ]
        },
        examples=(
            {"action": "mean_confidence_interval", "sample": ["10", "12", "9", "11", "13"], "confidenceLevel": "0.95"},
            {"action": "one_sample_t_test", "sample": ["10", "12", "9", "11", "13"], "nullMean": "10"},
            {"action": "linear_regression", "x": ["1", "2", "3"], "y": ["2", "4.1", "5.9"]},
        ),
        handler=inference.infer,
        keywords=("confidence interval", "t test", "regression", "hypothesis test", "置信区间", "t检验", "回归", "假设检验"),
    ),
    OperationSpec(
        id="probability.distribution",
        category="probability",
        summary="Evaluate common probability distributions.",
        description="Evaluate normal PDF/CDF/quantiles, binomial PMF/CDF, or Poisson PMF/CDF with explicit parameters and arbitrary-precision numerical methods.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "distribution": {"const": "normal"},
                        "function": {"type": "string", "enum": ["pdf", "cdf"]},
                        "x": _DECIMAL_TEXT,
                        "mean": {**_DECIMAL_TEXT, "default": "0"},
                        "standardDeviation": {**_DECIMAL_TEXT, "default": "1"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "x"),
                ),
                _object(
                    {
                        "distribution": {"const": "normal"},
                        "function": {"const": "quantile"},
                        "probability": _DECIMAL_TEXT,
                        "mean": {**_DECIMAL_TEXT, "default": "0"},
                        "standardDeviation": {**_DECIMAL_TEXT, "default": "1"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "probability"),
                ),
                _object(
                    {
                        "distribution": {"const": "binomial"},
                        "function": {"type": "string", "enum": ["pmf", "cdf"]},
                        "n": {"type": "integer", "minimum": 0, "maximum": 100_000},
                        "k": {"type": "integer", "minimum": 0, "maximum": 100_000},
                        "probability": _DECIMAL_TEXT,
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "n", "k", "probability"),
                ),
                _object(
                    {
                        "distribution": {"const": "poisson"},
                        "function": {"type": "string", "enum": ["pmf", "cdf"]},
                        "k": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
                        "rate": _DECIMAL_TEXT,
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "k", "rate"),
                ),
            ]
        },
        examples=(
            {"distribution": "normal", "function": "cdf", "x": "1.96"},
            {"distribution": "binomial", "function": "cdf", "n": 20, "k": 4, "probability": "0.1"},
            {"distribution": "poisson", "function": "pmf", "k": 3, "rate": "2.5"},
        ),
        handler=probability.distribution,
        keywords=("normal distribution", "binomial", "Poisson", "cdf", "pmf", "概率分布", "正态分布", "二项分布", "泊松分布"),
    ),
    OperationSpec(
        id="units.convert",
        category="units",
        summary="Convert a physical quantity between compatible units.",
        description="Use Pint for dimensional conversion and claim an exact result only when the source value and full conversion path are rational.",
        input_schema=_object(
            {
                "value": {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]},
                "fromUnit": {"type": "string", "maxLength": 128},
                "toUnit": {"type": "string", "maxLength": 128},
                "precision": _PRECISION,
            },
            ("value", "fromUnit", "toUnit"),
        ),
        examples=(
            {"value": 72, "fromUnit": "watt", "toUnit": "kilowatt"},
            {"value": 68, "fromUnit": "degF", "toUnit": "degC"},
        ),
        handler=data.units_convert,
        keywords=("measurement", "dimension", "temperature", "length", "energy", "单位换算", "单位转换", "温度转换"),
    ),
    OperationSpec(
        id="quantity.evaluate",
        category="units",
        summary="Evaluate arithmetic over unit-bearing quantities.",
        description="Parse a small unit-expression grammar with explicit multiplication, division, parentheses, and integer powers; enforce dimensional compatibility and optionally convert the result.",
        input_schema=_object(
            {
                "expression": {
                    "type": "string",
                    "maxLength": 2048,
                    "description": "Unit-bearing expression such as 80 * kg * 9.81 * m / s^2. Multiplication must be explicit.",
                },
                "toUnit": {"type": "string", "maxLength": 128},
                "precision": _PRECISION,
            },
            ("expression",),
        ),
        examples=(
            {"expression": "80 * kg * 9.81 * m / s^2", "toUnit": "newton"},
            {"expression": "3 * meter + 25 * centimeter", "toUnit": "meter"},
        ),
        handler=quantity.evaluate,
        keywords=("dimensional analysis", "unit expression", "force", "compound units", "带单位表达式", "量纲分析", "单位运算"),
    ),
    OperationSpec(
        id="finance.calculate",
        category="finance",
        summary="Calculate compound value, effective annual rate, loan payment, NPV, or bracketed IRR.",
        description="Use decimal arithmetic with explicit nominal-rate, compounding, period, cash-flow timing, root-bracket, and output-rounding conventions.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "compound_value"},
                        "principal": _DECIMAL_TEXT,
                        "annualRate": _DECIMAL_TEXT,
                        "periodsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "numberOfPeriods": {"type": "integer", "minimum": 0, "maximum": 10_000_000},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "principal", "annualRate", "periodsPerYear", "numberOfPeriods"),
                ),
                _object(
                    {
                        "action": {"const": "effective_annual_rate"},
                        "nominalAnnualRate": _DECIMAL_TEXT,
                        "compoundsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 12},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "nominalAnnualRate", "compoundsPerYear"),
                ),
                _object(
                    {
                        "action": {"const": "loan_payment"},
                        "principal": _DECIMAL_TEXT,
                        "annualRate": _DECIMAL_TEXT,
                        "paymentsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "numberOfPayments": {"type": "integer", "minimum": 1, "maximum": 10_000_000},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "principal", "annualRate", "paymentsPerYear", "numberOfPayments"),
                ),
                _object(
                    {
                        "action": {"const": "npv"},
                        "cashFlows": {"type": "array", "items": _DECIMAL_TEXT, "minItems": 2, "maxItems": 10_000},
                        "ratePerPeriod": _DECIMAL_TEXT,
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "cashFlows", "ratePerPeriod"),
                ),
                _object(
                    {
                        "action": {"const": "irr"},
                        "cashFlows": {"type": "array", "items": _DECIMAL_TEXT, "minItems": 2, "maxItems": 10_000},
                        "lowerRate": _DECIMAL_TEXT,
                        "upperRate": _DECIMAL_TEXT,
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-18"},
                        "maxIterations": {"type": "integer", "minimum": 1, "maximum": 2_000, "default": 256},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 12},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "cashFlows", "lowerRate", "upperRate"),
                ),
            ]
        },
        examples=(
            {"action": "compound_value", "principal": "10000", "annualRate": "0.05", "periodsPerYear": 12, "numberOfPeriods": 120},
            {"action": "effective_annual_rate", "nominalAnnualRate": "0.12", "compoundsPerYear": 12},
            {"action": "loan_payment", "principal": "300000", "annualRate": "0.045", "paymentsPerYear": 12, "numberOfPayments": 360},
            {"action": "npv", "cashFlows": ["-1000", "400", "400", "400"], "ratePerPeriod": "0.1"},
            {"action": "irr", "cashFlows": ["-1000", "400", "400", "400"], "lowerRate": "0", "upperRate": "1"},
        ),
        handler=finance.calculate,
        keywords=("compound interest", "APR", "effective annual rate", "loan payment", "NPV", "IRR", "cash flow", "复利", "年化率", "贷款", "净现值", "内部收益率", "现金流"),
    ),
)

OPERATIONS = {spec.id: spec for spec in _SPECS}


def search_operations(query: str = "", category: str | None = None) -> dict[str, Any]:
    if not isinstance(query, str):
        raise CalculatorError("E_INPUT", "query must be a string")
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"query must contain at most {MAX_SEARCH_QUERY_LENGTH} characters",
        )
    if category is not None and not isinstance(category, str):
        raise CalculatorError("E_INPUT", "category must be a string or null")
    if category is not None and len(category) > MAX_CATEGORY_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"category must contain at most {MAX_CATEGORY_LENGTH} characters",
        )
    normalized_query = query.strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized_query))
    candidates = [spec for spec in _SPECS if category is None or spec.category == category]
    if normalized_query:
        scored: list[tuple[int, OperationSpec]] = []
        for spec in candidates:
            haystack = " ".join((spec.id, spec.category, spec.summary, spec.description, *spec.keywords)).lower()
            alias_score = sum(
                4
                for keyword in spec.keywords
                if keyword.lower() in normalized_query or normalized_query in keyword.lower()
            )
            score = (
                (4 if normalized_query in haystack else 0)
                + alias_score
                + sum(1 for token in tokens if token in haystack)
            )
            if score:
                scored.append((score, spec))
        candidates = [spec for _, spec in sorted(scored, key=lambda item: (-item[0], item[1].id))]
    return {
        "status": "ok",
        "query": query,
        "category": category,
        "operations": [spec.compact() for spec in candidates],
        "count": len(candidates),
    }


def describe_operation(operation: str) -> dict[str, Any]:
    if not isinstance(operation, str) or not operation:
        raise CalculatorError("E_INPUT", "operation must be a non-empty string")
    if len(operation) > MAX_OPERATION_ID_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"operation must contain at most {MAX_OPERATION_ID_LENGTH} characters",
        )
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError(
            "E_OPERATION",
            "unknown operation id",
            {"available": sorted(OPERATIONS)},
        )
    return {"status": "ok", "operation": spec.describe()}


def operation_schemas() -> list[tuple[str, dict[str, Any]]]:
    return [(spec.id, spec.input_schema) for spec in _SPECS]
