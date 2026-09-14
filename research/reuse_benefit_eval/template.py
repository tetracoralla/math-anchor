"""Fair SymPy-side cached parametric antidifference for (k+c)^2.

This is a strong baseline, not a method pack. Prep stores G(k,c) as a SymPy
expression. Each task substitutes rational c and evaluates G(b+1)-G(a) with
exact rationals. No Gosper, no obligation checker, no eval/exec.

Reversed bounds are evaluated (Karr), matching an uncrippled CAS template.
Out-of-family summands are refused.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy as sp

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.polynomials import (
    DomainError,
    fraction_payload,
    parse_summand,
    require_integer,
)

from .protocol import CACHED_G_SOURCE


INDEX = "k"
PARAMETER = "c"


class TemplateBaselineError(CalculatorError):
    """Family-template baseline refused or failed."""


_K, _C = sp.symbols(INDEX), sp.symbols(PARAMETER)
CACHED_G = _K * (_K - 1) * (2 * _K - 1) / 6 + _C * _K * (_K - 1) + (_C ** 2) * _K


def prepare_template() -> dict[str, Any]:
    """One-time cache: confirm the stored G satisfies the bivariate identity in SymPy."""

    delta = sp.expand(CACHED_G.subs(_K, _K + 1) - CACHED_G)
    residual = sp.expand(delta - (_K + _C) ** 2)
    if residual != 0:
        raise TemplateBaselineError(
            "E_RUNTIME",
            "cached G(k,c) does not satisfy G(k+1,c)-G(k,c)=(k+c)^2",
        )
    return {
        "arm": "B_template",
        "artifact": "cached sympy G(k,c)",
        "source": CACHED_G_SOURCE,
        "identityHoldsInSymPy": True,
        "independentChecker": False,
        "once": True,
    }


def evaluate_template(task: dict[str, Any]) -> dict[str, Any]:
    lower = require_integer("lower", task["lower"])
    upper = require_integer("upper", task["upper"])
    variable = str(task.get("variable") or INDEX)
    parameter = _match_family(str(task["summand"]), variable, task.get("parameterC"))
    value = _eval_g(parameter, lower, upper)
    reversed_bounds = upper < lower - 1
    return {
        "status": "ok",
        "kind": "sympy_cached_parametric_antidifference_template",
        "engine": "sympy.Expr.subs on cached G(k,c)",
        "constructor": "instantiated-cached-parametric-antidifference",
        "cachedFormula": CACHED_G_SOURCE,
        "summand": str(task["summand"]),
        "variable": variable,
        "lower": lower,
        "upper": upper,
        "parameterC": _fraction_text(parameter),
        "value": fraction_payload(value),
        "usedSavedContent": True,
        "gosperCalled": False,
        "reconstructionDisabled": False,
        "independentChecker": False,
        "exactArithmetic": "sympy.Rational then fractions.Fraction",
        "floatingApproximation": False,
        "karrReversedBoundsAccepted": reversed_bounds,
        "stepsExecuted": [
            "applicability",
            "instantiate_saved_G",
            "evaluate_telescoping",
        ],
        "limitations": [
            "no_independent_certificate",
            "no_explicit_combination_rule",
            "karr_reversed_bounds_are_accepted",
        ],
    }


def _match_family(summand: str, variable: str, declared: object) -> Fraction:
    try:
        _source, terms, _expression = parse_summand(summand, variable)
    except DomainError as error:
        raise TemplateBaselineError(
            error.code,
            error.message,
            {"applicability": "rejected", "reason": "input_outside_declared_family"},
        ) from error
    extra = set(terms) - {0, 1, 2}
    if extra or terms.get(2) != Fraction(1):
        raise TemplateBaselineError(
            "E_UNSUPPORTED",
            "summand is not in the shifted-square family (k+c)^2",
            {"applicability": "rejected", "reason": "wrong_template", "summand": summand},
        )
    linear = terms.get(1, Fraction(0))
    parameter = linear / 2
    constant = terms.get(0, Fraction(0))
    if constant != parameter * parameter:
        raise TemplateBaselineError(
            "E_UNSUPPORTED",
            "summand quadratic is not a perfect square of (k+c) for rational c",
            {"applicability": "rejected", "reason": "wrong_template", "summand": summand},
        )
    if declared is not None:
        expected = _parse_rational(declared)
        if expected != parameter:
            raise TemplateBaselineError(
                "E_DOMAIN",
                "parameterC does not match the (k+c)^2 template implied by the summand",
                {"applicability": "rejected", "reason": "parameter_summand_mismatch"},
            )
    return parameter


def _eval_g(parameter: Fraction, lower: int, upper: int) -> Fraction:
    substituted = CACHED_G.subs(_C, sp.Rational(parameter.numerator, parameter.denominator))
    upper_value = substituted.subs(_K, upper + 1)
    lower_value = substituted.subs(_K, lower)
    return _as_fraction(upper_value - lower_value)


def _as_fraction(expr: sp.Expr) -> Fraction:
    value = sp.together(sp.expand(expr))
    if isinstance(value, sp.Integer):
        return Fraction(int(value), 1)
    if isinstance(value, sp.Rational):
        return Fraction(int(value.p), int(value.q))
    raise TemplateBaselineError(
        "E_UNSUPPORTED",
        "cached G evaluation did not return an exact rational",
        {"expression": str(value)},
    )


def _parse_rational(value: object) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str):
        text = value.strip().replace("−", "-")
        if "/" in text:
            numerator_text, denominator_text = text.split("/", 1)
            return Fraction(int(numerator_text), int(denominator_text))
        return Fraction(int(text), 1)
    raise TemplateBaselineError("E_INPUT", "parameterC must be an int or exact rational string")


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
