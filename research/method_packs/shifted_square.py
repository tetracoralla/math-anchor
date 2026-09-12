"""Parameterized antidifference for sums of (k+c)^2.

Research-only. This module derives and instantiates a saved G(k,c). It does
not call Gosper, SymPy summation, eval, exec, sympify, or parse_expr.

Provenance (known-method adaptation, not a discovery):
- monomial antidifferences are solved by undetermined coefficients over Q;
- G(k,c) is the linear combination for (k+c)^2 = k^2 + 2 c k + c^2;
- the bivariate identity is checked by the existing polynomial certificate
  checker. Faulhaber / Gosper already know these formulas.
"""

from __future__ import annotations

from fractions import Fraction
from math import comb
from typing import Any

from math_anchor.certificate_checker import CertificateValidationError, _PolynomialParser
from math_anchor.errors import CalculatorError
from math_anchor.expression_source import normalize_expression_source

from research.polynomial_finite_sum_proposal.polynomials import (
    DomainError,
    UnivariatePolynomial,
    parse_summand,
    polynomial_source,
)


INDEX_VARIABLE = "k"
PARAMETER_VARIABLE = "c"
SUMMAND_TEMPLATE = "(k + c)**2"

# Factored form of the derived G. Extract verifies this equals the
# undetermined-coefficient solution as bivariate polynomials.
CANONICAL_G_SOURCE = "k*(k - 1)*(2*k - 1)/6 + c*k*(k - 1) + (c**2)*k"

BivariatePolynomial = dict[tuple[int, int], Fraction]


class ShiftedSquareError(CalculatorError):
    """Domain or payload failure for the shifted-square family."""


def parse_rational_parameter(value: object, *, name: str = "parameterC") -> Fraction:
    if isinstance(value, bool):
        raise ShiftedSquareError("E_DOMAIN", f"{name} must be an exact rational, not a boolean")
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str):
        text = value.strip().replace("−", "-")
        if not text:
            raise ShiftedSquareError("E_INPUT", f"{name} must be a non-empty exact rational")
        try:
            if "/" in text:
                numerator_text, denominator_text = text.split("/", 1)
                parsed = Fraction(int(numerator_text), int(denominator_text))
            else:
                parsed = Fraction(int(text), 1)
        except (TypeError, ValueError) as error:
            raise ShiftedSquareError(
                "E_DOMAIN",
                f"{name} must be an integer or integer/integer rational string",
            ) from error
        return parsed
    raise ShiftedSquareError(
        "E_DOMAIN",
        f"{name} must be an int or exact rational string; floats are unsupported",
    )


def fraction_source(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def monomial_antidifference(power: int) -> UnivariatePolynomial:
    """Solve G(k+1)-G(k)=k^power for a polynomial G of degree power+1 with G(0)=0.

    Forward-difference of k^d is sum_{j=0}^{d-1} C(d,j) k^j. The linear system
    over Q is solved by Gaussian elimination. This is undetermined coefficients,
    not Gosper.
    """

    if type(power) is not int or isinstance(power, bool) or power < 0 or power > 8:
        raise ShiftedSquareError("E_LIMIT", "monomial power is outside the derivation limit")
    dimension = power + 1
    matrix = [[Fraction(0) for _ in range(dimension)] for _ in range(dimension)]
    for degree in range(1, dimension + 1):
        for row in range(degree):
            matrix[row][degree - 1] = Fraction(comb(degree, row))
    rhs = [Fraction(1 if row == power else 0) for row in range(dimension)]
    coefficients = _solve_linear(matrix, rhs)
    terms: UnivariatePolynomial = {}
    for degree, coefficient in enumerate(coefficients, start=1):
        if coefficient:
            terms[degree] = coefficient
    return terms


def derive_parametric_antidifference() -> BivariatePolynomial:
    """G(k,c) for p(k,c)=(k+c)^2 by linearity of the discrete difference."""

    square = monomial_antidifference(2)
    linear = monomial_antidifference(1)
    constant = monomial_antidifference(0)
    terms: BivariatePolynomial = {}
    for power, coefficient in square.items():
        terms[(power, 0)] = terms.get((power, 0), Fraction(0)) + coefficient
    for power, coefficient in linear.items():
        terms[(power, 1)] = terms.get((power, 1), Fraction(0)) + 2 * coefficient
    for power, coefficient in constant.items():
        terms[(power, 2)] = terms.get((power, 2), Fraction(0)) + coefficient
    return {key: value for key, value in terms.items() if value}


def parse_bivariate(source: str, index: str = INDEX_VARIABLE, parameter: str = PARAMETER_VARIABLE) -> BivariatePolynomial:
    if not isinstance(source, str) or not source.strip():
        raise ShiftedSquareError("E_INPUT", "parametric antidifference source must be a non-empty string")
    if index == parameter:
        raise ShiftedSquareError("E_DOMAIN", "index variable and parameter name must differ")
    normalized = normalize_expression_source(source)
    try:
        parsed = _PolynomialParser((index, parameter)).parse(normalized)
    except CertificateValidationError as error:
        raise ShiftedSquareError(
            "E_UNSUPPORTED",
            f"parametric antidifference is not a QQ-polynomial in {index},{parameter}: {error}",
        ) from error
    terms: BivariatePolynomial = {}
    for powers, coefficient in parsed.items():
        if coefficient:
            terms[(int(powers[0]), int(powers[1]))] = coefficient
    return terms


def canonical_g_terms() -> BivariatePolynomial:
    derived = derive_parametric_antidifference()
    frozen = parse_bivariate(CANONICAL_G_SOURCE)
    if derived != frozen:
        raise ShiftedSquareError(
            "E_RUNTIME",
            "canonical G(k,c) source does not match the undetermined-coefficient derivation",
            {"derived": _terms_payload(derived), "frozen": _terms_payload(frozen)},
        )
    return frozen


def instantiate_univariate(terms: BivariatePolynomial, parameter: Fraction) -> UnivariatePolynomial:
    univariate: UnivariatePolynomial = {}
    for (index_power, parameter_power), coefficient in terms.items():
        univariate[index_power] = univariate.get(index_power, Fraction(0)) + coefficient * (
            parameter**parameter_power
        )
    return {power: coefficient for power, coefficient in univariate.items() if coefficient}


def match_shifted_square(summand: str, variable: str) -> Fraction:
    """Return rational c such that the summand equals (variable + c)^2.

    Matching uses the original-language polynomial parser (constant denominators
    only). Leading coefficient must be 1. This is not a general square-recognition
    engine.
    """

    try:
        _source, terms, _expression = parse_summand(summand, variable)
    except DomainError as error:
        raise ShiftedSquareError(
            error.code,
            error.message,
            {"reason": "input_outside_declared_pack_domain"},
        ) from error
    extra = set(terms) - {0, 1, 2}
    if extra or terms.get(2) != Fraction(1):
        raise ShiftedSquareError(
            "E_UNSUPPORTED",
            "summand is not in the shifted-square family (k+c)^2 with leading coefficient 1",
            {"reason": "wrong_template", "summand": summand},
        )
    linear = terms.get(1, Fraction(0))
    parameter = linear / 2
    constant = terms.get(0, Fraction(0))
    if constant != parameter * parameter:
        raise ShiftedSquareError(
            "E_UNSUPPORTED",
            "summand quadratic is not a perfect square of (k+c) for rational c",
            {
                "reason": "wrong_template",
                "summand": summand,
                "impliedC": fraction_source(parameter),
                "expectedConstant": fraction_source(parameter * parameter),
                "actualConstant": fraction_source(constant),
            },
        )
    return parameter


def summand_source_for_c(parameter: Fraction, variable: str) -> str:
    if parameter == 0:
        return f"{variable}**2"
    magnitude = abs(parameter)
    body = fraction_source(magnitude)
    if parameter > 0:
        return f"({variable} + {body})**2"
    return f"({variable} - {body})**2"


def shift_index(terms: BivariatePolynomial) -> BivariatePolynomial:
    shifted: BivariatePolynomial = {}
    for (index_power, parameter_power), coefficient in terms.items():
        for lower in range(index_power + 1):
            key = (lower, parameter_power)
            shifted[key] = shifted.get(key, Fraction(0)) + coefficient * Fraction(comb(index_power, lower))
    return {key: value for key, value in shifted.items() if value}


def subtract(left: BivariatePolynomial, right: BivariatePolynomial) -> BivariatePolynomial:
    keys = set(left) | set(right)
    return {
        key: left.get(key, Fraction(0)) - right.get(key, Fraction(0))
        for key in keys
        if left.get(key, Fraction(0)) - right.get(key, Fraction(0))
    }


def bivariate_source(terms: BivariatePolynomial, index: str, parameter: str) -> str:
    ordered = sorted(
        ((powers, coefficient) for powers, coefficient in terms.items() if coefficient),
        key=lambda item: (-item[0][0], -item[0][1]),
    )
    if not ordered:
        return "0"
    pieces: list[str] = []
    for position, (powers, coefficient) in enumerate(ordered):
        body = _bivariate_term(index, parameter, powers[0], powers[1], abs(coefficient))
        if position == 0:
            pieces.append(body if coefficient > 0 else f"-{body}")
        elif coefficient > 0:
            pieces.append(f"+ {body}")
        else:
            pieces.append(f"- {body}")
    return " ".join(pieces)


def general_identity_sources(
    g_terms: BivariatePolynomial,
    *,
    index: str = INDEX_VARIABLE,
    parameter: str = PARAMETER_VARIABLE,
) -> dict[str, str]:
    left = (
        f"({bivariate_source(shift_index(g_terms), index, parameter)}) - "
        f"({bivariate_source(g_terms, index, parameter)})"
    )
    return {
        "left": left,
        "right": f"({index} + {parameter})**2",
        "antidifference": bivariate_source(g_terms, index, parameter),
        "antidifferenceAtPlusOne": bivariate_source(shift_index(g_terms), index, parameter),
    }


def instance_summand_terms(parameter: Fraction) -> UnivariatePolynomial:
    terms: UnivariatePolynomial = {2: Fraction(1)}
    linear = 2 * parameter
    constant = parameter * parameter
    if linear:
        terms[1] = linear
    if constant:
        terms[0] = constant
    return terms


def instantiated_g_source(g_terms: BivariatePolynomial, parameter: Fraction, variable: str) -> str:
    return polynomial_source(instantiate_univariate(g_terms, parameter), variable)


def g_payload_from_pack(pack: dict[str, Any]) -> dict[str, Any]:
    semantics = pack.get("mathSemantics")
    if not isinstance(semantics, dict):
        raise ShiftedSquareError("E_INPUT", "method pack mathSemantics must be an object")
    payload = semantics.get("parametricAntidifference")
    if not isinstance(payload, dict):
        raise ShiftedSquareError(
            "E_INPUT",
            "method pack is missing the parametric antidifference payload; "
            "reconstruction is disabled so the task cannot proceed",
            {"reason": "missing_parametric_payload", "reconstructionDisabled": True},
        )
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ShiftedSquareError(
            "E_INPUT",
            "parametric antidifference source is missing; reconstruction is disabled",
            {"reason": "missing_parametric_source", "reconstructionDisabled": True},
        )
    if payload.get("notFromGosper") is not True:
        raise ShiftedSquareError(
            "E_INPUT",
            "shifted-square pack must declare the saved G is not a Gosper reconstruction",
        )
    index = payload.get("indexVariable", INDEX_VARIABLE)
    parameter = payload.get("parameterVariable", PARAMETER_VARIABLE)
    if index != INDEX_VARIABLE or parameter != PARAMETER_VARIABLE:
        raise ShiftedSquareError(
            "E_INPUT",
            "parametric antidifference must be stored in variables k and c",
        )
    terms = parse_bivariate(source, index, parameter)
    if not terms:
        raise ShiftedSquareError("E_INPUT", "parametric antidifference is the zero polynomial")
    return {
        "source": normalize_expression_source(source),
        "terms": terms,
        "indexVariable": index,
        "parameterVariable": parameter,
        "summandTemplate": payload.get("summandTemplate", SUMMAND_TEMPLATE),
        "derivationMethod": payload.get("derivationMethod"),
    }


def _bivariate_term(
    index: str,
    parameter: str,
    index_power: int,
    parameter_power: int,
    magnitude: Fraction,
) -> str:
    factors: list[str] = []
    if magnitude != 1:
        factors.append(f"({fraction_source(magnitude)})" if magnitude.denominator != 1 else fraction_source(magnitude))
    if index_power == 1:
        factors.append(index)
    elif index_power > 1:
        factors.append(f"{index}**{index_power}")
    if parameter_power == 1:
        factors.append(parameter)
    elif parameter_power > 1:
        factors.append(f"{parameter}**{parameter_power}")
    if not factors:
        return "1"
    return "*".join(factors)


def _terms_payload(terms: BivariatePolynomial) -> list[dict[str, Any]]:
    return [
        {
            "k": powers[0],
            "c": powers[1],
            "numerator": int(coefficient.numerator),
            "denominator": int(coefficient.denominator),
        }
        for powers, coefficient in sorted(terms.items())
    ]


def _solve_linear(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    size = len(rhs)
    if size == 0 or any(len(row) != size for row in matrix):
        raise ShiftedSquareError("E_RUNTIME", "linear system is not square")
    tableau = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot_row = next((row for row in range(column, size) if tableau[row][column] != 0), None)
        if pivot_row is None:
            raise ShiftedSquareError("E_RUNTIME", "singular system while deriving an antidifference")
        tableau[column], tableau[pivot_row] = tableau[pivot_row], tableau[column]
        pivot = tableau[column][column]
        tableau[column] = [entry / pivot for entry in tableau[column]]
        for row in range(size):
            if row == column:
                continue
            factor = tableau[row][column]
            if factor:
                tableau[row] = [
                    entry - factor * pivot_entry
                    for entry, pivot_entry in zip(tableau[row], tableau[column], strict=True)
                ]
    return [row[-1] for row in tableau]


# DomainError is re-exported for callers that catch the original-language parser.
__all__ = [
    "CANONICAL_G_SOURCE",
    "INDEX_VARIABLE",
    "PARAMETER_VARIABLE",
    "SUMMAND_TEMPLATE",
    "ShiftedSquareError",
    "canonical_g_terms",
    "derive_parametric_antidifference",
    "fraction_source",
    "g_payload_from_pack",
    "general_identity_sources",
    "instance_summand_terms",
    "instantiate_univariate",
    "instantiated_g_source",
    "match_shifted_square",
    "monomial_antidifference",
    "parse_bivariate",
    "parse_rational_parameter",
    "summand_source_for_c",
    "DomainError",
]
