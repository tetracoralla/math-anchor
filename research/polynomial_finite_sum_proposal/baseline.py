"""No-model SymPy baseline for the same finite-sum task.

This path trusts SymPy's `summation` for the closed value. It does not
construct a certificate, apply the telescoping combination rule, or consult
Math Anchor. It exists so A0 can compare 'SymPy alone' with the checked
vertical without pretending they are the same artifact.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy as sp

from math_anchor.errors import CalculatorError
from math_anchor.safe_expression import make_symbols, parse_expression

from .polynomials import DomainError, fraction_payload, require_integer


def sympy_finite_sum(
    *,
    summand: str,
    variable: str = "k",
    lower: object,
    upper: object,
) -> dict[str, Any]:
    start = require_integer("lower", lower)
    stop = require_integer("upper", upper)
    symbols = make_symbols([variable])
    try:
        expression = parse_expression(summand, symbols=symbols)
    except CalculatorError as error:
        raise DomainError(
            "E_UNSUPPORTED",
            f"baseline summand could not be parsed: {error.message}",
        ) from error
    closed = sp.summation(expression, (symbols[variable], start, stop))
    if not isinstance(closed, sp.Rational):
        raise DomainError(
            "E_UNSUPPORTED",
            "SymPy summation did not return an exact rational for these bounds",
        )
    value = Fraction(int(closed.p), int(closed.q))
    return {
        "status": "ok",
        "kind": "sympy_summation_baseline",
        "engine": "sympy.summation",
        "summand": summand,
        "variable": variable,
        "lower": start,
        "upper": stop,
        "value": fraction_payload(value),
        "boundConvention": (
            "SymPy follows the Karr convention: reversed bounds evaluate to the "
            "negative of the swapped inclusive sum. This baseline therefore does "
            "not match the proposal's fail-closed reversed-bound policy."
        ),
        "limitations": [
            "no_independent_certificate",
            "no_explicit_combination_rule",
            "karr_reversed_bounds_are_accepted",
        ],
    }
