from __future__ import annotations

import ast
from fractions import Fraction
from hashlib import sha256
import json
from typing import Any

import sympy as sp
from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from ..errors import CalculatorError, require
from ..safe_expression import make_symbols, normalize_expression_source, parse_expression
from ..validation import string_arg, variables_arg


CERTIFICATE_FORMAT = "math-anchor.polynomial-identity.v1"
MAX_CERTIFICATE_TERMS = 512
MAX_POLYNOMIAL_DEGREE = 64
MAX_COEFFICIENT_BITS = 16_384
MAX_AST_NODES = 1_024
PolynomialShape = set[tuple[int, ...]]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return f"sha256:{sha256(_canonical_json(value)).hexdigest()}"


def _fraction_text(value: sp.Rational) -> str:
    fraction = Fraction(int(value.p), int(value.q))
    require(
        fraction.numerator.bit_length() <= MAX_COEFFICIENT_BITS
        and fraction.denominator.bit_length() <= MAX_COEFFICIENT_BITS,
        "E_LIMIT",
        "polynomial certificate coefficients are too large",
    )
    if fraction.denominator == 1:
        return str(fraction.numerator)
    return f"{fraction.numerator}/{fraction.denominator}"


def _bounded_shape(shape: PolynomialShape) -> PolynomialShape:
    require(
        len(shape) <= MAX_CERTIFICATE_TERMS,
        "E_LIMIT",
        f"polynomial certificate may contain at most {MAX_CERTIFICATE_TERMS} terms",
    )
    if shape:
        require(
            max(sum(powers) for powers in shape) <= MAX_POLYNOMIAL_DEGREE,
            "E_LIMIT",
            f"polynomial certificate degree may not exceed {MAX_POLYNOMIAL_DEGREE}",
        )
    return shape


def _multiply_shapes(left: PolynomialShape, right: PolynomialShape) -> PolynomialShape:
    result: PolynomialShape = set()
    for left_powers in left:
        for right_powers in right:
            result.add(tuple(a + b for a, b in zip(left_powers, right_powers, strict=True)))
            _bounded_shape(result)
    return result


def _power_shape(base: PolynomialShape, exponent: int, variable_count: int) -> PolynomialShape:
    require(
        0 <= exponent <= MAX_POLYNOMIAL_DEGREE,
        "E_LIMIT",
        f"polynomial certificate degree may not exceed {MAX_POLYNOMIAL_DEGREE}",
    )
    result = {(0,) * variable_count}
    factor = base
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = _multiply_shapes(result, factor)
        remaining >>= 1
        if remaining:
            factor = _multiply_shapes(factor, factor)
    return result


class _PolynomialShapeAnalyzer(ast.NodeVisitor):
    """Bound polynomial expansion before asking SymPy to perform it.

    This deliberately overestimates terms when cancellation is possible. A
    bounded certificate operation may reject an oversized intermediate even if
    symbolic cancellation could later make it small.
    """

    def __init__(self, variables: list[str]) -> None:
        self.variables = tuple(variables)
        self.node_count = 0

    def visit(self, node: ast.AST) -> PolynomialShape:  # type: ignore[override]
        self.node_count += 1
        require(self.node_count <= MAX_AST_NODES, "E_LIMIT", "certificate expression is too complex")
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> PolynomialShape:
        raise CalculatorError(
            "E_AST_BLOCK",
            f"unsupported certificate syntax: {type(node).__name__}",
        )

    def visit_Expression(self, node: ast.Expression) -> PolynomialShape:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> PolynomialShape:
        require(
            isinstance(node.value, int) and not isinstance(node.value, bool),
            "E_DOMAIN",
            "polynomial certificates require integer literals; write exact rational coefficients as integer division",
        )
        return {(0,) * len(self.variables)}

    def visit_Name(self, node: ast.Name) -> PolynomialShape:
        require(
            node.id in self.variables,
            "E_DOMAIN",
            f"polynomial certificate contains an undeclared variable: {node.id}",
        )
        powers = [0] * len(self.variables)
        powers[self.variables.index(node.id)] = 1
        return {tuple(powers)}

    def visit_Call(self, node: ast.Call) -> PolynomialShape:
        if isinstance(node.func, ast.Name) and not node.func.id.startswith("_"):
            raise CalculatorError(
                "E_DOMAIN",
                "certificate.polynomial_identity requires a polynomial over rational coefficients",
            )
        raise CalculatorError("E_AST_BLOCK", "unsupported certificate call syntax")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> PolynomialShape:
        require(
            isinstance(node.op, (ast.UAdd, ast.USub)),
            "E_DOMAIN",
            "polynomial certificate contains an unsupported unary operator",
        )
        return self.visit(node.operand)

    def visit_BinOp(self, node: ast.BinOp) -> PolynomialShape:
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return _bounded_shape(self.visit(node.left) | self.visit(node.right))
        if isinstance(node.op, ast.Mult):
            return _multiply_shapes(self.visit(node.left), self.visit(node.right))
        if isinstance(node.op, ast.Div):
            numerator = self.visit(node.left)
            denominator = self.visit(node.right)
            require(
                denominator == {(0,) * len(self.variables)},
                "E_DOMAIN",
                "polynomial division requires a nonzero rational constant",
            )
            return numerator
        if isinstance(node.op, ast.Pow):
            require(
                isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, int)
                and not isinstance(node.right.value, bool),
                "E_DOMAIN",
                "polynomial exponents must be nonnegative integers",
            )
            return _power_shape(self.visit(node.left), node.right.value, len(self.variables))
        raise CalculatorError(
            "E_DOMAIN",
            "certificate.polynomial_identity supports only +, -, *, / by a constant, and nonnegative integer powers",
        )


def _preflight_shape(source: str, variables: list[str]) -> PolynomialShape:
    try:
        parsed = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise CalculatorError("E_SYNTAX", f"invalid expression: {error.msg}") from error
    return _PolynomialShapeAnalyzer(variables).visit(parsed)


def polynomial_identity(arguments: dict[str, Any]) -> dict[str, Any]:
    left_text = string_arg(arguments, "left")
    right_text = string_arg(arguments, "right")
    variable_names = variables_arg(arguments, maximum=8)
    symbols = make_symbols(variable_names)
    left_source = normalize_expression_source(left_text)
    right_source = normalize_expression_source(right_text)
    _bounded_shape(
        _preflight_shape(left_source, variable_names)
        | _preflight_shape(right_source, variable_names)
    )
    left = parse_expression(left_source, symbols=symbols)
    right = parse_expression(right_source, symbols=symbols)
    try:
        polynomial = sp.Poly(
            sp.expand(left - right),
            *(symbols[name] for name in variable_names),
            domain=sp.QQ,
        )
    except (CoercionFailed, PolynomialError) as error:
        raise CalculatorError(
            "E_DOMAIN",
            "certificate.polynomial_identity requires a polynomial over rational coefficients",
        ) from error

    if not polynomial.is_zero:
        require(
            int(polynomial.total_degree()) <= MAX_POLYNOMIAL_DEGREE,
            "E_LIMIT",
            f"polynomial certificate degree may not exceed {MAX_POLYNOMIAL_DEGREE}",
        )
    terms = [
        {
            "powers": list(monomial),
            "coefficient": _fraction_text(coefficient),
        }
        for monomial, coefficient in sorted(polynomial.terms(), reverse=True)
        if coefficient != 0
    ]
    require(
        len(terms) <= MAX_CERTIFICATE_TERMS,
        "E_LIMIT",
        f"polynomial certificate may contain at most {MAX_CERTIFICATE_TERMS} terms",
    )
    statement = {
        "left": left_source,
        "right": right_source,
        "variables": variable_names,
    }
    certificate: dict[str, Any] = {
        "format": CERTIFICATE_FORMAT,
        "statement": statement,
        "statementDigest": _digest(statement),
        "identity": polynomial.is_zero,
        "normalizedDifference": terms,
    }
    certificate["certificateDigest"] = _digest(certificate)
    return {
        "status": "ok",
        "operation": "certificate.polynomial_identity",
        "kind": "polynomial_identity_certificate",
        "identity": polynomial.is_zero,
        "variables": variable_names,
        "assumptions": [
            "Variables are commuting indeterminates.",
            "All coefficients are rational numbers.",
        ],
        "certificate": certificate,
        "checkedBy": None,
        "warnings": [
            "The certificate is independently checkable but has not been accepted by a formal proof kernel."
        ],
    }
