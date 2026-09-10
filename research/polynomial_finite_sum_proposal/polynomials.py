"""Bounded rational-polynomial helpers for the finite-sum proposal.

Construction may use SymPy. Identity checking and integer-point evaluation
reuse the independent standard-library polynomial parser so they cannot accept
a larger language than `certificate_checker`.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy as sp
from sympy.concrete.gosper import gosper_sum
from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from math_anchor.certificate_checker import (
    MAX_COEFFICIENT_BITS,
    MAX_POLYNOMIAL_DEGREE,
    _PolynomialParser,
)
from math_anchor.errors import CalculatorError
from math_anchor.expression_source import normalize_expression_source
from math_anchor.safe_expression import make_symbols, parse_expression


MAX_ABS_BOUND = 1_000_000
UnivariatePolynomial = dict[int, Fraction]


class DomainError(CalculatorError):
    """Input is outside the first-round rational-polynomial finite-sum domain."""


def require_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise DomainError(
            "E_DOMAIN",
            f"{name} must be an integer; boolean and non-integer values are unsupported",
        )
    if abs(value) > MAX_ABS_BOUND:
        raise DomainError(
            "E_LIMIT",
            f"{name} magnitude may be at most {MAX_ABS_BOUND} in this proposal",
        )
    return value


def parse_summand(source: str, variable: str) -> tuple[str, UnivariatePolynomial, sp.Expr]:
    if not isinstance(source, str) or not source.strip():
        raise DomainError("E_INPUT", "summand must be a non-empty expression string")
    symbols = make_symbols([variable])
    try:
        expression = parse_expression(source, symbols=symbols)
    except CalculatorError as error:
        if error.code in {"E_AST_BLOCK", "E_DOMAIN", "E_NAME", "E_SYNTAX"}:
            raise DomainError(
                "E_UNSUPPORTED",
                f"summand is outside the rational-polynomial domain: {error.message}",
            ) from error
        raise
    if expression.free_symbols - {symbols[variable]}:
        extra = ", ".join(sorted(str(symbol) for symbol in expression.free_symbols - {symbols[variable]}))
        raise DomainError(
            "E_UNSUPPORTED",
            f"summand depends on extra symbols ({extra}); only a univariate polynomial in {variable} is supported",
        )
    if expression.has(sp.Float, sp.oo, sp.zoo, sp.nan, sp.I):
        raise DomainError(
            "E_UNSUPPORTED",
            "summand must be a rational-coefficient polynomial; floats, infinities, and non-reals are unsupported",
        )
    polynomial = as_univariate_rational_polynomial(expression, symbols[variable])
    return normalize_expression_source(source), polynomial, expression


def as_univariate_rational_polynomial(expression: sp.Expr, symbol: sp.Symbol) -> UnivariatePolynomial:
    try:
        polynomial = sp.Poly(sp.expand(expression), symbol, domain=sp.QQ)
    except (CoercionFailed, PolynomialError) as error:
        raise DomainError(
            "E_UNSUPPORTED",
            "summand is not a rational-coefficient polynomial with constant denominators only",
        ) from error
    if polynomial.free_symbols - {symbol}:
        raise DomainError(
            "E_UNSUPPORTED",
            "summand is not a univariate rational-coefficient polynomial in the summation variable",
        )
    terms: UnivariatePolynomial = {}
    for monomial, coefficient in polynomial.terms():
        power = int(monomial[0])
        fraction = Fraction(int(coefficient.p), int(coefficient.q))
        if fraction:
            terms[power] = fraction
    _bounded_univariate(terms)
    return terms


def construct_antidifference(expression: sp.Expr, symbol: sp.Symbol) -> tuple[UnivariatePolynomial, str]:
    """Construct G such that G(k+1) - G(k) = p(k), reusing SymPy Gosper/summation.

    This is construction only. The caller must still verify the difference
    identity with the independent checker.
    """

    constructed = gosper_sum(expression, symbol)
    constructor = "sympy.concrete.gosper.gosper_sum"
    if constructed is None:
        dummy = sp.Dummy("n")
        constructed = sp.summation(expression, (symbol, 0, dummy - 1)).subs(dummy, symbol)
        constructor = "sympy.summation"
    if constructed is None or constructed.has(sp.Sum, sp.Piecewise):
        raise DomainError(
            "E_UNSUPPORTED",
            "SymPy Gosper/summation did not produce a closed polynomial antidifference",
        )
    if constructed.free_symbols - {symbol}:
        raise DomainError(
            "E_UNSUPPORTED",
            "constructed antidifference depends on symbols other than the summation variable",
        )
    terms = as_univariate_rational_polynomial(sp.together(constructed), symbol)
    return terms, constructor


def parse_antidifference(source: str, variable: str) -> UnivariatePolynomial:
    _normalized, terms, _expression = parse_summand(source, variable)
    return terms


def _bounded_univariate(terms: UnivariatePolynomial) -> None:
    if not terms:
        return
    degree = max(terms)
    if degree > MAX_POLYNOMIAL_DEGREE:
        raise DomainError(
            "E_LIMIT",
            f"polynomial degree may not exceed {MAX_POLYNOMIAL_DEGREE}",
        )
    for coefficient in terms.values():
        if (
            coefficient.numerator.bit_length() > MAX_COEFFICIENT_BITS
            or coefficient.denominator.bit_length() > MAX_COEFFICIENT_BITS
        ):
            raise DomainError("E_LIMIT", "polynomial coefficient exceeds the checker limit")


def _fraction_source(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _monomial_source(variable: str, power: int, *, shifted: bool) -> str:
    base = f"({variable} + 1)" if shifted else variable
    if power == 0:
        return "1"
    if power == 1:
        return base
    return f"{base}**{power}"


def _term_source(variable: str, power: int, coefficient: Fraction, *, shifted: bool) -> str:
    magnitude = abs(coefficient)
    monomial = _monomial_source(variable, power, shifted=shifted)
    if power == 0:
        body = _fraction_source(magnitude)
    elif magnitude == 1:
        body = monomial
    else:
        body = f"({_fraction_source(magnitude)})*{monomial}"
    return body


def polynomial_source(
    terms: UnivariatePolynomial,
    variable: str,
    *,
    shifted: bool = False,
) -> str:
    ordered = [(power, coefficient) for power, coefficient in sorted(terms.items(), reverse=True) if coefficient]
    if not ordered:
        return "0"
    pieces: list[str] = []
    for index, (power, coefficient) in enumerate(ordered):
        body = _term_source(variable, power, coefficient, shifted=shifted)
        if index == 0:
            pieces.append(body if coefficient > 0 else f"-{body}")
        elif coefficient > 0:
            pieces.append(f"+ {body}")
        else:
            pieces.append(f"- {body}")
    return " ".join(pieces)


def difference_identity_sources(
    antidifference: UnivariatePolynomial,
    summand: UnivariatePolynomial,
    variable: str,
) -> dict[str, str]:
    left = (
        f"({polynomial_source(antidifference, variable, shifted=True)}) - "
        f"({polynomial_source(antidifference, variable)})"
    )
    return {
        "left": left,
        "right": polynomial_source(summand, variable),
        "antidifference": polynomial_source(antidifference, variable),
        "antidifferenceAtPlusOne": polynomial_source(antidifference, variable, shifted=True),
    }


def evaluate_univariate(source: str, variable: str, value: int) -> Fraction:
    """Evaluate a checker-language univariate polynomial at an integer.

    Uses the independent certificate parser, not SymPy.
    """

    polynomial = _PolynomialParser((variable,)).parse(source)
    total = Fraction(0)
    for powers, coefficient in polynomial.items():
        total += coefficient * (value ** powers[0])
        if (
            total.numerator.bit_length() > MAX_COEFFICIENT_BITS
            or total.denominator.bit_length() > MAX_COEFFICIENT_BITS
        ):
            raise DomainError("E_LIMIT", "evaluated value exceeds the checker coefficient limit")
    return total


def fraction_payload(value: Fraction) -> dict[str, Any]:
    return {
        "exact": str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}",
        "numerator": int(value.numerator),
        "denominator": int(value.denominator),
    }
