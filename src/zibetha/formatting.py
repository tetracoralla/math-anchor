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


def approximate(value: sp.Expr, precision: int) -> str | None:
    if value.has(sp.zoo, sp.nan) or value in (sp.oo, -sp.oo):
        return _text(value)
    if value.is_number:
        return _text(sp.N(value, precision))
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
