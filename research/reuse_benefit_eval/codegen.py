"""Exact generated evaluator for sums of (k+c)^2.

Prep uses sympy.Poly to emit a QQ coefficient table for
S(c,a,b)=G(b+1,c)-G(a,c). Per-task evaluation is Fraction arithmetic on that
table. This is codegen of an exact rational evaluator.

Skipped backends (documented, not faked):
- sympy.utilities.codegen C: emits double/pow (float), and would need a compiler
- pycode: emits `/` (Python 3 float division); exec is forbidden in this repo
- autowrap: compiler/Cython deps and still typically float

No eval, exec, sympify, or parse_expr.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy as sp

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.polynomials import (
    fraction_payload,
    require_integer,
)

from .protocol import CACHED_G_SOURCE
from .template import _match_family


class CodegenBaselineError(CalculatorError):
    """Exact codegen baseline refused or failed."""


_TERMS: list[tuple[tuple[int, int, int], Fraction]] | None = None


def prepare_codegen() -> dict[str, Any]:
    """One-time generation of the QQ coefficient table."""

    global _TERMS
    k, c, a, b = sp.symbols("k c a b")
    cached_g = k * (k - 1) * (2 * k - 1) / 6 + c * k * (k - 1) + (c ** 2) * k
    closed = sp.expand(cached_g.subs(k, b + 1) - cached_g.subs(k, a))
    polynomial = sp.Poly(closed, c, b, a, domain=sp.QQ)
    terms: list[tuple[tuple[int, int, int], Fraction]] = []
    payload: list[dict[str, int]] = []
    for exponents, coefficient in polynomial.terms():
        fraction = Fraction(int(coefficient.p), int(coefficient.q))
        if not fraction:
            continue
        powers = (int(exponents[0]), int(exponents[1]), int(exponents[2]))
        terms.append((powers, fraction))
        payload.append(
            {
                "c": powers[0],
                "b": powers[1],
                "a": powers[2],
                "numerator": int(fraction.numerator),
                "denominator": int(fraction.denominator),
            }
        )
    _TERMS = terms
    self_check = _eval_terms(terms, Fraction(1), 0, 4)
    if self_check != Fraction(55):
        raise CodegenBaselineError(
            "E_RUNTIME",
            "generated QQ evaluator failed its P0 self-check",
            {"value": str(self_check)},
        )
    return {
        "arm": "B_codegen",
        "artifact": "QQ coefficient table of S(c,a,b)=G(b+1,c)-G(a,c)",
        "sourceFormula": CACHED_G_SOURCE,
        "terms": payload,
        "termCount": len(payload),
        "domain": "QQ",
        "exactNotFloat": True,
        "selfCheckP0": "55",
        "once": True,
        "independentChecker": False,
        "skippedBackends": skip_reasons(),
    }


def skip_reasons() -> dict[str, Any]:
    c_probe = probe_c_codegen_is_float()
    return {
        "sympy.utilities.codegen.C": {
            "used": False,
            "reason": (
                "C codegen emits a floating type (double/pow) for this closed form; "
                "it is not an exact rational evaluator. A compiler would also be required."
            ),
            "probe": c_probe,
        },
        "sympy.printing.pycode": {
            "used": False,
            "reason": (
                "pycode emits `/`, which is Python 3 float division. "
                "exec of generated source is forbidden in this repository."
            ),
        },
        "sympy.utilities.autowrap": {
            "used": False,
            "reason": "requires a compiler/Cython toolchain and would still typically be float",
        },
    }


def probe_c_codegen_is_float() -> dict[str, Any]:
    from sympy.utilities.codegen import codegen

    a, b, c = sp.symbols("a b c")
    k = sp.symbols("k")
    cached_g = k * (k - 1) * (2 * k - 1) / 6 + c * k * (k - 1) + (c ** 2) * k
    closed = sp.expand(cached_g.subs(k, b + 1) - cached_g.subs(k, a))
    try:
        [( _name, code), _header] = codegen(
            ("shifted_square_closed", closed),
            language="C",
            header=False,
            empty=False,
        )
    except Exception as error:  # pragma: no cover - optional backend
        return {
            "available": False,
            "emitsFloatingType": None,
            "errorType": type(error).__name__,
        }
    floating = "double" in code or "float" in code
    lines = [line for line in code.splitlines() if line.strip()][:6]
    return {
        "available": True,
        "emitsFloatingType": floating,
        "used": False,
        "leadingLines": lines,
    }


def evaluate_codegen(task: dict[str, Any]) -> dict[str, Any]:
    if _TERMS is None:
        prepare_codegen()
    assert _TERMS is not None
    lower = require_integer("lower", task["lower"])
    upper = require_integer("upper", task["upper"])
    variable = str(task.get("variable") or "k")
    parameter = _match_family(str(task["summand"]), variable, task.get("parameterC"))
    value = _eval_terms(_TERMS, parameter, lower, upper)
    if isinstance(value, float):
        raise CodegenBaselineError("E_RUNTIME", "codegen evaluator produced a float")
    reversed_bounds = upper < lower - 1
    return {
        "status": "ok",
        "kind": "sympy_poly_qq_coefficient_table_evaluator",
        "engine": "sympy.Poly QQ coefficient table + fractions.Fraction",
        "constructor": "generated-exact-rational-evaluator",
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
        "exactArithmetic": "fractions.Fraction",
        "floatingApproximation": False,
        "karrReversedBoundsAccepted": reversed_bounds,
        "stepsExecuted": ["applicability", "codegen_eval"],
        "limitations": [
            "no_independent_certificate",
            "no_explicit_combination_rule",
            "karr_reversed_bounds_are_accepted",
            "c_float_codegen_not_used",
        ],
    }


def _eval_terms(
    terms: list[tuple[tuple[int, int, int], Fraction]],
    parameter: Fraction,
    lower: int,
    upper: int,
) -> Fraction:
    total = Fraction(0)
    for (c_power, b_power, a_power), coefficient in terms:
        total += coefficient * (parameter ** c_power) * (upper ** b_power) * (lower ** a_power)
    return total


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
