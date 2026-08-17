from __future__ import annotations

import sys
from typing import Any

from mpmath.libmp import prec_to_dps
import sympy as sp

from .errors import CalculatorError


_MAX_INTEGER_STRING_DIGITS = 20_000


def _allow_bounded_large_integer_output() -> None:
    get_limit = getattr(sys, "get_int_max_str_digits", None)
    set_limit = getattr(sys, "set_int_max_str_digits", None)
    if get_limit is None or set_limit is None:
        return
    current = get_limit()
    if current != 0 and current < _MAX_INTEGER_STRING_DIGITS:
        set_limit(_MAX_INTEGER_STRING_DIGITS)


def _text(value: sp.Expr) -> str:
    _allow_bounded_large_integer_output()
    return sp.sstr(value)


def _require_defined(values: list[sp.Expr]) -> None:
    if any(value.has(sp.zoo, sp.nan) for value in values):
        raise CalculatorError("E_DOMAIN", "result is undefined for the supplied input")


# Guard digits used while evaluating an approximation. Evaluating the whole
# expression tree at the requested precision alone leaves the trailing digits
# unreliable for cancellation-heavy inputs (acos(tanh(10)) at precision 30 was
# correct only to ~24 digits) and collapses chained near-unit arguments to
# exact constants (ln(tanh(42 + pi)) at precision 30 evaluated to exactly 0).
# The value is evaluated with guard digits and then rounded to the requested
# precision, so the printed digit count -- and therefore the precision
# provenance reported alongside it -- is unchanged.
_GUARD_DIGITS = 10


def _uncertainty_zero(value: sp.Expr) -> bool:
    """Detect mpmath's inexact-uncertainty marker ("0.e+4619"): a magnitude
    with NO computed significant digits, produced when evalf cannot resolve a
    cancellation. Such a Float is numerically nonzero and ``is_zero`` is
    False, so only its printed form identifies it; re-rounding it fabricates
    digits that were never computed.
    """
    return ".e" in sp.sstr(value)


def _reconcile(direct: sp.Expr, evaluated: sp.Expr, precision: int) -> sp.Expr:
    """Choose the printed value between the requested-precision evaluation
    (``direct``) and the guard-digit evaluation rounded back (``evaluated``).

    See approximate() for the unresolvable regimes and their rationale.
    """
    non_finite = any(lane is sp.nan for lane in (direct, evaluated)) or (
        direct.is_finite is False or evaluated.is_finite is False
    )
    if non_finite:
        # N can RETURN a non-finite value (e.g. asin(inf) -> nan, an mpmath
        # NaN whose is_finite is None); the comparisons below raise for those.
        return direct
    if _uncertainty_zero(direct) or _uncertainty_zero(evaluated):
        return direct
    if direct.is_zero:
        if not evaluated.is_zero and abs(evaluated) > 1:
            return direct
        return sp.N(evaluated, precision)
    if evaluated.is_zero or abs(evaluated - direct) > abs(direct) * 10 ** _GUARD_DIGITS:
        return direct
    return sp.N(evaluated, precision)


def approximate(value: sp.Expr, precision: int) -> str | None:
    if value.has(sp.zoo, sp.nan) or value in (sp.oo, -sp.oo):
        return _text(value)
    if value.is_number:
        try:
            direct = sp.N(value, precision)
            evaluated = sp.N(value, precision + _GUARD_DIGITS)
        except TypeError as error:
            # Deferred ordering over non-real operands (e.g. an unevaluated
            # Min/Max whose comparison only happens at evaluation time).
            raise CalculatorError("E_DOMAIN", "result is undefined for the supplied input") from error
        except (OverflowError, ValueError) as error:
            # Magnitudes beyond convertible range (e.g. cos(cosh(5^1000))).
            raise CalculatorError("E_LIMIT", "value is too large to evaluate") from error
        # Reconcile the two evaluations. Rounding the guard evaluation back
        # keeps trailing digits honest for cancellation-heavy inputs and
        # recovers sub-precision nonzero values. Two unresolvable regimes
        # keep the requested-precision lane instead:
        #   * an mpmath uncertainty zero ("0.e+4612": a magnitude with NO
        #     computed significant digits; both is_zero and == 0 are False)
        #     means evalf could not resolve the cancellation even at guard
        #     precision; re-rounding such a Float FABRICATES magnitude digits
        #     (the fractional part of sinh(sinh(10)) needs ~4600 digits), so
        #     SymPy's uncertainty notation is printed as-is;
        #   * a disagreement far larger than the guard digits could reconcile
        #     means evalf itself was unstable.
        # In both regimes no decimal is trustworthy; the exact symbolic field
        # remains the truth carrier.
        try:
            rounded = _reconcile(direct, evaluated, precision)
        except (TypeError, ValueError, OverflowError) as error:
            # The reconciliation arithmetic itself can be impossible (complex
            # or undefined numeric results raise on comparison). The
            # reconciliation is an enhancement lane, never an authority: on
            # any failure the requested-precision evaluation is printed.
            rounded = direct
        # full_prec keeps Floats inside compound numbers (complex values such
        # as 84*I/5) at the requested precision; the default printer renders
        # them at a shortest binary64-style repr ("16.8*I") instead.
        return sp.sstr(rounded, full_prec=True)
    return None


def effective_precision(values: list[sp.Expr], requested: int) -> int:
    float_atoms = [atom for value in values for atom in value.atoms(sp.Float)]
    if not float_atoms:
        return requested
    available = min(prec_to_dps(atom._prec) for atom in float_atoms)
    return max(2, min(requested, available))


def value_result(value: sp.Expr, precision: int) -> dict[str, str | None]:
    _require_defined([value])
    reported_precision = effective_precision([value], precision)
    return {
        "exact": None if value.atoms(sp.Float) else _text(value),
        "approx": approximate(value, reported_precision),
    }


def scalar_result(
    operation: str,
    value: sp.Expr,
    precision: int,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    _require_defined([value])
    contains_float = bool(value.atoms(sp.Float))
    reported_precision = effective_precision([value], precision)
    return {
        "status": "ok",
        "operation": operation,
        "kind": "scalar",
        "exact": None if contains_float else _text(value),
        "approx": approximate(value, reported_precision),
        "precision": reported_precision,
        "unit": None,
        "warnings": warnings or [],
    }


def typed_scalar_result(
    operation: str,
    kind: str,
    value: sp.Expr,
    precision: int,
    **metadata: Any,
) -> dict[str, Any]:
    result = scalar_result(operation, value, precision)
    result["kind"] = kind
    result.pop("unit")
    result.update(metadata)
    return result


def matrix_value(matrix: sp.MatrixBase, precision: int) -> dict[str, Any]:
    rows = matrix.tolist()
    values = [value for row in rows for value in row]
    _require_defined(values)
    contains_float = any(value.atoms(sp.Float) for value in values)
    reported_precision = effective_precision(values, precision)
    return {
        "exact": None if contains_float else [[_text(value) for value in row] for row in rows],
        "approx": [[approximate(value, reported_precision) or _text(value) for value in row] for row in rows],
        "precision": reported_precision,
        "shape": [matrix.rows, matrix.cols],
    }


def matrix_result(operation: str, matrix: sp.MatrixBase, precision: int) -> dict[str, Any]:
    formatted = matrix_value(matrix, precision)
    return {
        "status": "ok",
        "operation": operation,
        "kind": "matrix",
        **formatted,
        "warnings": [],
    }


def values_result(operation: str, values: list[sp.Expr], precision: int) -> dict[str, Any]:
    _require_defined(values)
    reported_precision = effective_precision(values, precision)
    return {
        "status": "ok",
        "operation": operation,
        "kind": "values",
        "values": [value_result(value, reported_precision) for value in values],
        "precision": reported_precision,
        "warnings": [],
    }


def solution_result(
    operation: str,
    solutions: list[dict[sp.Symbol, sp.Expr]],
    precision: int,
    *,
    warnings: list[str] | None = None,
    classification: str,
    complete: bool,
    solution_set: str,
) -> dict[str, Any]:
    values = [value for solution in solutions for value in solution.values()]
    _require_defined(values)
    reported_precision = effective_precision(values, precision)
    payload = []
    for solution in solutions:
        payload.append(
            {
                str(symbol): {
                    "exact": None if value.atoms(sp.Float) else _text(value),
                    "approx": approximate(value, reported_precision),
                }
                for symbol, value in solution.items()
            }
        )
    return {
        "status": "ok",
        "operation": operation,
        "kind": "solutions",
        "classification": classification,
        "complete": complete,
        "solutionSet": solution_set,
        "solutions": payload,
        "precision": reported_precision,
        "warnings": warnings or [],
    }
