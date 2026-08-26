from __future__ import annotations

from typing import Any

import mpmath as mp
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import matrix_value, scalar_result, typed_scalar_result
from ..safe_expression import make_symbols, parse_expression, parse_matrix
from ..validation import enum_arg, integer_arg, list_arg, string_arg, variables_arg


def derivative(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    order = integer_arg(arguments, "order", default=1, minimum=1, maximum=10)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols([variable])
    result = sp.diff(parse_expression(expression_text, symbols=symbols), symbols[variable], order)
    return scalar_result("calculus.derivative", result, precision)


def integrate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    lower_present = "lower" in arguments
    upper_present = "upper" in arguments
    require(lower_present == upper_present, "E_INPUT", "lower and upper must be supplied together")
    if lower_present:
        lower = parse_expression(str(arguments["lower"]))
        upper = parse_expression(str(arguments["upper"]))
        result = sp.integrate(expression, (symbols[variable], lower, upper))
    else:
        result = sp.integrate(expression, symbols[variable])
    return scalar_result("calculus.integrate", result, precision)


def limit(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    point_text = string_arg(arguments, "point", max_length=256)
    direction = enum_arg(arguments, "direction", ("+", "-", "+-"), default="+-")
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    point = parse_expression(point_text)
    result = sp.limit(expression, symbols[variable], point, dir=direction)
    return scalar_result("calculus.limit", result, precision)


def series(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    point_text = str(arguments.get("point", "0"))
    order = integer_arg(arguments, "order", default=6, minimum=1, maximum=50)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    point = parse_expression(point_text)
    try:
        result = sp.series(expression, symbols[variable], point, order)
    except (NotImplementedError, TypeError, ValueError) as error:
        raise CalculatorError("E_DOMAIN", f"series expansion is not available for this input: {error}") from error
    return typed_scalar_result(
        "calculus.series",
        "series",
        result,
        precision,
        variable=variable,
        point=sp.sstr(point),
        order=order,
    )


def multivariate(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        (
            "gradient",
            "jacobian",
            "hessian",
            "directional_derivative",
            "divergence",
            "curl",
            "laplacian",
        ),
        default="gradient",
    )
    variable_names = variables_arg(arguments, maximum=8)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols(variable_names)
    ordered_symbols = [symbols[name] for name in variable_names]
    if action in {"jacobian", "divergence", "curl"}:
        expression_texts = list_arg(arguments, "expressions", maximum=16)
        require(
            all(isinstance(value, str) for value in expression_texts),
            "E_INPUT",
            "expressions must contain strings",
        )
        expressions = [parse_expression(value, symbols=symbols) for value in expression_texts]
        if action == "jacobian":
            result = sp.Matrix(expressions).jacobian(ordered_symbols)
        elif action == "divergence":
            require(
                len(expressions) == len(ordered_symbols),
                "E_INPUT",
                "divergence requires one vector-field component per variable",
            )
            result = sum(
                sp.diff(value, symbol)
                for value, symbol in zip(expressions, ordered_symbols)
            )
        else:
            require(
                len(expressions) == len(ordered_symbols) == 3,
                "E_INPUT",
                "curl requires exactly three vector-field components and three variables",
            )
            first, second, third = expressions
            x, y, z = ordered_symbols
            result = sp.Matrix(
                [
                    sp.diff(third, y) - sp.diff(second, z),
                    sp.diff(first, z) - sp.diff(third, x),
                    sp.diff(second, x) - sp.diff(first, y),
                ]
            )
    else:
        expression = parse_expression(string_arg(arguments, "expression"), symbols=symbols)
        if action == "gradient":
            result = sp.Matrix([sp.diff(expression, symbol) for symbol in ordered_symbols])
        elif action == "hessian":
            result = sp.hessian(expression, ordered_symbols)
        elif action == "laplacian":
            result = sum(sp.diff(expression, symbol, 2) for symbol in ordered_symbols)
        else:
            direction_values = list_arg(arguments, "direction", maximum=8)
            require(
                len(direction_values) == len(ordered_symbols),
                "E_INPUT",
                "direction must contain one component per variable",
            )
            direction = parse_matrix([direction_values])
            require(
                not any(value.atoms(sp.Float) for value in direction),
                "E_INPUT",
                "directional derivative requires exact direction components",
            )
            require(any(value != 0 for value in direction), "E_DOMAIN", "direction vector must be nonzero")
            result = sum(
                sp.diff(expression, symbol) * component
                for symbol, component in zip(ordered_symbols, direction)
            )
    if action in {"directional_derivative", "divergence", "laplacian"}:
        return typed_scalar_result(
            "calculus.multivariate",
            "derivative_scalar",
            result,
            precision,
            action=action,
            variables=variable_names,
        )
    return {
        "status": "ok",
        "operation": "calculus.multivariate",
        "kind": "derivative_matrix",
        "action": action,
        "variables": variable_names,
        **matrix_value(result, precision),
        "warnings": [],
    }


def numeric_root(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    bracket = arguments.get("bracket")
    require(
        isinstance(bracket, list)
        and len(bracket) == 2
        and all(isinstance(value, (int, float, str)) and not isinstance(value, bool) for value in bracket),
        "E_INPUT",
        "bracket must contain two numbers or decimal strings",
    )
    lower_text, upper_text = str(bracket[0]), str(bracket[1])
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=50)
    tolerance_text = arguments.get("tolerance", f"1e-{precision}")
    require(isinstance(tolerance_text, str), "E_INPUT", "tolerance must be positive decimal text")
    max_iterations = integer_arg(arguments, "maxIterations", default=512, minimum=1, maximum=2_000)
    find_all = arguments.get("findAll", False)
    require(isinstance(find_all, bool), "E_INPUT", "findAll must be a boolean")
    resolution = integer_arg(arguments, "resolution", default=64, minimum=16, maximum=4_096)
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    function = sp.lambdify(symbols[variable], expression, modules="mpmath")
    try:
        with mp.workdps(precision + 10):
            lower = mp.mpf(lower_text)
            upper = mp.mpf(upper_text)
            tolerance = mp.mpf(tolerance_text)
            require(mp.isfinite(lower) and mp.isfinite(upper), "E_DOMAIN", "root bracket must be finite")
            require(lower < upper, "E_INPUT", "bracket must be ordered from lower to upper")
            require(mp.isfinite(tolerance) and tolerance > 0, "E_INPUT", "tolerance must be positive and finite")

            def evaluate(point: mp.mpf) -> mp.mpf:
                require(mp.isfinite(point), "E_DOMAIN", "root candidate left the finite range")
                value = function(point)
                require(
                    mp.isfinite(value) and mp.im(value) == 0,
                    "E_DOMAIN",
                    "root bracket crosses a point where the expression is not finite and real",
                )
                return mp.re(value)

            if find_all:
                return _all_roots_result(
                    evaluate,
                    lower,
                    upper,
                    tolerance,
                    max_iterations,
                    resolution,
                    precision,
                )

            result, residual, error_bound, final_bracket, iterations, value_scale = _bracketed_root(
                evaluate, lower, upper, tolerance, max_iterations, precision
            )
            residual_limit = max(tolerance, mp.sqrt(tolerance)) * value_scale
            require(
                residual <= residual_limit,
                "E_DOMAIN",
                "the sign change does not certify a root; the bracket may contain a discontinuity",
            )
            result_text = mp.nstr(result, precision)
            error_text = mp.nstr(error_bound, precision)
            residual_text = mp.nstr(residual, precision)
            bracket_texts = [mp.nstr(point, precision) for point in final_bracket]
    except CalculatorError:
        raise
    except (ArithmeticError, TypeError, ValueError) as error:
        raise CalculatorError("E_DOMAIN", f"root could not be bracketed: {error}") from error
    return {
        "status": "ok",
        "operation": "numeric.root",
        "kind": "numerical_root",
        "exact": None,
        "approx": result_text,
        "precision": precision,
        "method": "brent",
        "converged": True,
        "iterations": iterations,
        "tolerance": tolerance_text,
        "errorBound": error_text,
        "residual": residual_text,
        "finalBracket": bracket_texts,
        "warnings": ["Numerical root with a bracket-width error bound; no exact symbolic value is claimed."],
    }


def _bracketed_root(
    evaluate: Any,
    lower: mp.mpf,
    upper: mp.mpf,
    tolerance: mp.mpf,
    max_iterations: int,
    precision: int,
) -> tuple[mp.mpf, mp.mpf, mp.mpf, list[mp.mpf], int, mp.mpf]:
    """Solve one sign-changing bracket with Brent's method.

    Inverse-quadratic or secant steps are accepted only when they stay
    inside the maintained bracket and contract at least as fast as
    bisection; otherwise the step is the bisection midpoint. The bracket
    (b, c) always holds opposite-sign values - the counterpoint is
    repaired from the previous iterate before any step and before any
    termination check - so the returned half-width is the same rigorous
    error bound pure bisection provided, while smooth functions converge
    superlinearly. Returns (root, residual, error_bound, final_bracket,
    iterations, value_scale) where root is the bracket midpoint and
    value_scale bounds |f| at the final bracket ends.
    """
    f_lower = evaluate(lower)
    f_upper = evaluate(upper)
    require(
        f_lower == 0 or f_upper == 0 or mp.sign(f_lower) != mp.sign(f_upper),
        "E_DOMAIN",
        "root could not be bracketed: endpoint values must have opposite signs",
    )
    if f_lower == 0:
        return lower, mp.mpf("0"), mp.mpf("0"), [lower, lower], 0, mp.mpf("1")
    if f_upper == 0:
        return upper, mp.mpf("0"), mp.mpf("0"), [upper, upper], 0, mp.mpf("1")

    a, f_a = lower, f_lower
    b, f_b = upper, f_upper
    c, f_c = lower, f_lower
    last_step = upper - lower
    step_two_ago = upper - lower
    iterations = 0
    while iterations < max_iterations:
        if (f_b > 0) == (f_c > 0):
            # The counterpoint drifted onto b's side; restore the bracket
            # from the previous iterate before anything else happens.
            c, f_c = a, f_a
            last_step = step_two_ago = b - a
        if abs(f_c) < abs(f_b):
            a, f_a = b, f_b
            b, f_b = c, f_c
            c, f_c = a, f_a
        error_bound = abs(c - b) / 2
        value_scale = max(mp.mpf("1"), abs(f_b), abs(f_c))
        if f_b == 0:
            return b, mp.mpf("0"), error_bound, sorted((b, c)), iterations, value_scale
        if error_bound <= tolerance:
            midpoint = (b + c) / 2
            return midpoint, abs(evaluate(midpoint)), error_bound, sorted((b, c)), iterations, value_scale
        minimum_step = tolerance / 2 + abs(b) * mp.mpf(10) ** (-(precision + 8))
        half_width = (c - b) / 2
        if abs(step_two_ago) >= minimum_step and abs(f_a) > abs(f_b):
            if a == c:
                numerator = 2 * half_width * (f_b / f_a)
                denominator = 1 - f_b / f_a
            else:
                ratio_a = f_a / f_c
                ratio_b = f_b / f_c
                ratio = f_b / f_a
                numerator = ratio * (
                    2 * half_width * ratio_a * (ratio_a - ratio_b) - (b - a) * (ratio_b - 1)
                )
                denominator = (ratio_a - 1) * (ratio_b - 1) * (ratio - 1)
            if numerator > 0:
                denominator = -denominator
            magnitude = abs(numerator)
            if denominator != 0 and 2 * magnitude < min(
                3 * half_width * abs(denominator) - abs(minimum_step * denominator),
                abs(step_two_ago * denominator),
            ):
                step_two_ago = last_step
                last_step = magnitude / denominator
            else:
                step_two_ago = last_step = half_width
        else:
            step_two_ago = last_step = half_width
        a, f_a = b, f_b
        if abs(last_step) > minimum_step:
            b = b + last_step
        else:
            b = b + (minimum_step if half_width > 0 else -minimum_step)
        f_b = evaluate(b)
        iterations += 1
    raise CalculatorError(
        "E_CONVERGENCE",
        f"root search did not reach tolerance within {max_iterations} iterations",
        {"errorBound": mp.nstr(abs(c - b) / 2, precision)},
    )


def _all_roots_result(
    evaluate: Any,
    lower: mp.mpf,
    upper: mp.mpf,
    tolerance: mp.mpf,
    max_iterations: int,
    resolution: int,
    precision: int,
) -> dict[str, Any]:
    """Enumerate every sign-changing root in the bracket at a fixed grid
    resolution. Roots whose intervals overlap after solving (including a
    root sitting exactly on a grid point, which sign-changes on both
    sides) are merged. Roots without a sign change, such as even
    multiplicities, or closer together than the grid resolution, can be
    missed; that limitation is reported, not hidden.
    """
    spacing = (upper - lower) / resolution
    grid = [lower + spacing * index for index in range(resolution + 1)]
    values = [evaluate(point) for point in grid]
    intervals: list[tuple[mp.mpf, mp.mpf]] = []
    zeros: set[int] = set()
    for index in range(resolution):
        left_value = values[index]
        right_value = values[index + 1]
        if left_value == 0:
            zeros.add(index)
        if left_value != 0 and right_value != 0 and mp.sign(left_value) != mp.sign(right_value):
            intervals.append((grid[index], grid[index + 1]))
    if values[-1] == 0:
        zeros.add(resolution)

    solved: list[tuple[mp.mpf, mp.mpf, mp.mpf, list[mp.mpf], int]] = []
    iterations = 0
    for interval_lower, interval_upper in intervals:
        root, residual, error_bound, final_bracket, used, value_scale = _bracketed_root(
            evaluate, interval_lower, interval_upper, tolerance, max_iterations, precision
        )
        residual_limit = max(tolerance, mp.sqrt(tolerance)) * value_scale
        require(
            residual <= residual_limit,
            "E_DOMAIN",
            "a grid interval's sign change does not certify a root; the bracket may contain a discontinuity near "
            + mp.nstr(root, precision),
        )
        solved.append((root, residual, error_bound, final_bracket, used))
        iterations += used
    for index in sorted(zeros):
        point = grid[index]
        solved.append((point, abs(values[index]), mp.mpf("0"), [point, point], 0))

    merged: list[tuple[mp.mpf, mp.mpf, mp.mpf, list[mp.mpf]]] = []
    for root, residual, error_bound, final_bracket, _ in sorted(solved, key=lambda item: item[0]):
        interval = (root - max(error_bound, tolerance), root + max(error_bound, tolerance))
        if merged and interval[0] <= merged[-1][3][1]:
            previous_root, previous_residual, previous_error, previous_bracket = merged[-1]
            merged[-1] = (
                previous_root,
                previous_residual,
                max(previous_error, error_bound),
                [min(previous_bracket[0], final_bracket[0]), max(previous_bracket[1], final_bracket[1])],
            )
        else:
            merged.append((root, residual, error_bound, final_bracket))

    roots = [
        {
            "approx": mp.nstr(root, precision),
            "errorBound": mp.nstr(error_bound, precision),
            "residual": mp.nstr(residual, precision),
            "finalBracket": [mp.nstr(point, precision) for point in final_bracket],
        }
        for root, residual, error_bound, final_bracket in merged
    ]
    warnings = [
        "Sign-changing roots at the supplied resolution only; roots without a sign change or closer together than the resolution can be missed.",
        "Every root carries a bracket-width error bound; no exact symbolic value is claimed.",
    ]
    if not roots:
        warnings.append("No sign change was detected at the supplied resolution; this does not prove the bracket is root-free.")
    first = merged[0] if merged else None
    return {
        "status": "ok",
        "operation": "numeric.root",
        "kind": "numerical_root",
        "exact": None,
        "approx": mp.nstr(first[0], precision) if first else None,
        "precision": precision,
        "method": "brent",
        "converged": True,
        "iterations": iterations,
        "tolerance": mp.nstr(tolerance, precision),
        "errorBound": mp.nstr(first[2], precision) if first else None,
        "residual": mp.nstr(first[1], precision) if first else None,
        "finalBracket": [mp.nstr(point, precision) for point in first[3]] if first else None,
        "findAll": True,
        "resolution": mp.nstr(spacing, precision),
        "count": len(roots),
        "roots": roots,
        "warnings": warnings,
    }
