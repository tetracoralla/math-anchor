from __future__ import annotations

from typing import Any

import mpmath as mp
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import scalar_result, value_result
from ..safe_expression import make_symbols, parse_expression
from ..validation import integer_arg, string_arg


def evaluate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = string_arg(arguments, "expression")
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    variables = arguments.get("variables", {})
    require(isinstance(variables, dict), "E_INPUT", "variables must be an object")
    require(len(variables) <= 16, "E_LIMIT", "variables may contain at most 16 entries")
    value = parse_expression(expression, values=variables)
    return scalar_result("expression.evaluate", value, precision)


def simplify(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = string_arg(arguments, "expression")
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    variable_names = arguments.get("variables", [])
    require(isinstance(variable_names, list), "E_INPUT", "variables must be an array")
    require(all(isinstance(name, str) for name in variable_names), "E_INPUT", "variables must contain strings")
    symbols = make_symbols(variable_names)
    value = sp.simplify(parse_expression(expression, symbols=symbols))
    return scalar_result("expression.simplify", value, precision)


def sample(arguments: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one expression over an explicit point list or an even grid.

    One call replaces a chatter of single-point evaluations. Points where
    the expression is undefined are reported as undefined rows instead of
    failing the whole table, because a sampled range legitimately crosses
    poles and domain boundaries.
    """
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols([variable])
    symbol = symbols[variable]
    expression = parse_expression(expression_text, symbols=symbols)

    raw_points = arguments.get("points")
    grid_present = "lower" in arguments or "upper" in arguments or "count" in arguments
    points_present = raw_points is not None
    require(
        points_present != grid_present,
        "E_INPUT",
        "supply either points or lower, upper, and count, exactly one of the two",
    )
    point_texts: list[str]
    if raw_points is not None:
        require(
            isinstance(raw_points, list) and raw_points,
            "E_INPUT",
            "points must be a non-empty array of decimal texts",
        )
        require(len(raw_points) <= 256, "E_LIMIT", "points may contain at most 256 values")
        require(all(isinstance(item, str) for item in raw_points), "E_INPUT", "points must contain decimal texts")
        point_texts = raw_points
    else:
        lower_text = string_arg(arguments, "lower", max_length=256)
        upper_text = string_arg(arguments, "upper", max_length=256)
        count = integer_arg(arguments, "count", default=20, minimum=2, maximum=1000)
        with mp.workdps(50):
            try:
                lower = mp.mpf(lower_text)
                upper = mp.mpf(upper_text)
            except (TypeError, ValueError) as error:
                raise CalculatorError("E_INPUT", "grid bounds must be decimal text") from error
            require(mp.isfinite(lower) and mp.isfinite(upper), "E_DOMAIN", "grid bounds must be finite")
            require(lower < upper, "E_INPUT", "grid bounds must satisfy lower < upper")
            point_texts = [
                mp.nstr(lower + (upper - lower) * index / (count - 1), 17)
                for index in range(count)
            ]

    # Validate every point text up front: malformed points are a caller
    # error and must fail the call, not silently become undefined rows.
    for text in point_texts:
        point_value = parse_expression(text)
        require(not point_value.free_symbols, "E_INPUT", f"point {text} must be a numeric expression")

    rows: list[dict[str, Any]] = []
    undefined = 0
    for text in point_texts:
        try:
            # parse_expression keeps the lexical decimal exact, matching the
            # provenance rule of every other decimal-text input.
            value = expression.subs(symbol, parse_expression(text))
            formatted = value_result(value, precision)
            rows.append({"x": text, "exact": formatted["exact"], "approx": formatted["approx"], "undefined": False})
        except (ArithmeticError, TypeError, ValueError, ZeroDivisionError, CalculatorError):
            undefined += 1
            rows.append({"x": text, "exact": None, "approx": None, "undefined": True})

    warnings: list[str] = []
    if undefined:
        warnings.append(
            f"{undefined} sampled point(s) are outside the expression's domain and are reported as undefined."
        )
    return {
        "_usedBackends": ["sympy"] if points_present else ["mpmath", "sympy"],
        "status": "ok",
        "operation": "function.sample",
        "kind": "function_table",
        "count": len(rows),
        "points": rows,
        "warnings": warnings,
    }
