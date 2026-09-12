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
    CertificateValidationError,
    _PolynomialParser,
)
from math_anchor.errors import CalculatorError
from math_anchor.expression_source import normalize_expression_source
from math_anchor.safe_expression import make_symbols


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
    """Parse a univariate QQ-polynomial, checking the original language first.

    Constant nonzero rational denominators are allowed. The independent
    certificate parser runs on the source *before* any SymPy arithmetic, so
    ``k/k``, ``(k-1)/(k-1)``, and ``0/k`` stay out of domain instead of
    collapsing to ``1``/``0``. The SymPy expression is rebuilt from the
    already-checked coefficients; this helper does not change general
    ``parse_expression`` semantics.
    """

    if not isinstance(source, str) or not source.strip():
        raise DomainError("E_INPUT", "summand must be a non-empty expression string")
    if not isinstance(variable, str) or not variable.strip():
        raise DomainError("E_INPUT", "variable must be a non-empty string")
    normalized = normalize_expression_source(source)
    try:
        parsed = _PolynomialParser((variable,)).parse(normalized)
    except CertificateValidationError as error:
        raise DomainError(
            "E_UNSUPPORTED",
            "summand is not a rational-coefficient polynomial with constant denominators only"
            f": {error}",
        ) from error
    terms: UnivariatePolynomial = {}
    for powers, coefficient in parsed.items():
        if coefficient:
            terms[int(powers[0])] = coefficient
    _bounded_univariate(terms)
    symbols = make_symbols([variable])
    return normalized, terms, _sympy_from_terms(terms, symbols[variable])


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


def rebuilt_difference_claim(g_source: str, summand: str, variable: str) -> dict[str, Any]:
    """Rebuild G(k+1)-G(k)=p(k) from current G and the original task summand."""

    g_terms = parse_antidifference(g_source, variable)
    _source, p_terms, _expression = parse_summand(summand, variable)
    sources = difference_identity_sources(g_terms, p_terms, variable)
    return {
        "left": sources["left"],
        "right": sources["right"],
        "variables": [variable],
        "antidifference": sources["antidifference"],
    }


def checker_polynomials_equal(left: str, right: str, variable: str) -> bool:
    """True iff left and right are the same rational polynomial in the checker language."""

    parser = _PolynomialParser((variable,))
    try:
        left_terms = parser.parse(normalize_expression_source(left))
        right_terms = parser.parse(normalize_expression_source(right))
    except CertificateValidationError:
        return False
    return left_terms == right_terms


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


def rational_from_payload(payload: object) -> Fraction:
    """Read a rational from one canonical payload. exact must match num/den."""

    if not isinstance(payload, dict):
        raise DomainError("E_INPUT", "rational payload must be an object")
    numerator = payload.get("numerator")
    denominator = payload.get("denominator")
    if type(numerator) is not int or type(denominator) is not int or denominator == 0:
        raise DomainError(
            "E_INPUT",
            "rational payload must have integer numerator and nonzero denominator",
        )
    value = Fraction(numerator, denominator)
    canonical = fraction_payload(value)
    if numerator != canonical["numerator"] or denominator != canonical["denominator"]:
        raise DomainError(
            "E_INPUT",
            "rational payload numerator/denominator must be the reduced canonical form",
            {"canonical": canonical, "payload": {"numerator": numerator, "denominator": denominator}},
        )
    exact = payload.get("exact")
    if exact is not None and exact != canonical["exact"]:
        raise DomainError(
            "E_INPUT",
            "rational payload exact text disagrees with numerator/denominator",
            {"canonical": canonical, "payload": payload},
        )
    return value


def _sympy_from_terms(terms: UnivariatePolynomial, symbol: sp.Symbol) -> sp.Expr:
    expression: sp.Expr = sp.Integer(0)
    for power, coefficient in sorted(terms.items()):
        expression += sp.Rational(coefficient.numerator, coefficient.denominator) * symbol**power
    return expression
