from __future__ import annotations

from typing import Any

import mpmath as mp
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import matrix_value, scalar_result, typed_scalar_result
from ..safe_expression import make_symbols, parse_expression
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
    action = enum_arg(arguments, "action", ("gradient", "jacobian", "hessian"), default="gradient")
    variable_names = variables_arg(arguments, maximum=8)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    symbols = make_symbols(variable_names)
    ordered_symbols = [symbols[name] for name in variable_names]
    if action == "jacobian":
        expression_texts = list_arg(arguments, "expressions", maximum=16)
        require(
            all(isinstance(value, str) for value in expression_texts),
            "E_INPUT",
            "expressions must contain strings",
        )
        expressions = [parse_expression(value, symbols=symbols) for value in expression_texts]
        result = sp.Matrix(expressions).jacobian(ordered_symbols)
    else:
        expression = parse_expression(string_arg(arguments, "expression"), symbols=symbols)
        if action == "gradient":
            result = sp.Matrix([sp.diff(expression, symbol) for symbol in ordered_symbols])
        else:
            result = sp.hessian(expression, ordered_symbols)
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
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    function = sp.lambdify(symbols[variable], expression, modules="mpmath")
    try:
        with mp.workdps(precision + 10):
            lower_value = mp.mpf(lower_text)
            upper_value = mp.mpf(upper_text)
            tolerance = mp.mpf(tolerance_text)
            require(mp.isfinite(lower_value) and mp.isfinite(upper_value), "E_DOMAIN", "root bracket must be finite")
            require(lower_value < upper_value, "E_INPUT", "bracket must be ordered from lower to upper")
            require(mp.isfinite(tolerance) and tolerance > 0, "E_INPUT", "tolerance must be positive and finite")
            lower_result = function(lower_value)
            upper_result = function(upper_value)
            require(
                mp.isfinite(lower_result) and mp.isfinite(upper_result),
                "E_DOMAIN",
                "root bracket endpoints must evaluate to finite values",
            )
            require(
                mp.im(lower_result) == 0 and mp.im(upper_result) == 0,
                "E_DOMAIN",
                "root bracket endpoints must evaluate to real values",
            )
            require(
                lower_result == 0 or upper_result == 0 or mp.sign(lower_result) != mp.sign(upper_result),
                "E_DOMAIN",
                "root could not be bracketed: endpoint values must have opposite signs",
            )
            if lower_result == 0:
                result = lower_value
                result_value = lower_result
                error_bound = mp.mpf("0")
                iterations = 0
            elif upper_result == 0:
                result = upper_value
                result_value = upper_result
                error_bound = mp.mpf("0")
                iterations = 0
            else:
                result = (lower_value + upper_value) / 2
                result_value = function(result)
                for iterations in range(1, max_iterations + 1):
                    result = (lower_value + upper_value) / 2
                    result_value = function(result)
                    require(
                        mp.isfinite(result_value) and mp.im(result_value) == 0,
                        "E_DOMAIN",
                        "root bracket crosses a point where the expression is not finite and real",
                    )
                    error_bound = (upper_value - lower_value) / 2
                    if result_value == 0 or error_bound <= tolerance:
                        break
                    if mp.sign(result_value) == mp.sign(lower_result):
                        lower_value = result
                        lower_result = result_value
                    else:
                        upper_value = result
                        upper_result = result_value
                else:
                    raise CalculatorError(
                        "E_CONVERGENCE",
                        f"root bisection did not reach tolerance within {max_iterations} iterations",
                        {"errorBound": mp.nstr(error_bound, precision)},
                    )
                scale = max(mp.mpf("1"), abs(lower_result), abs(upper_result))
                residual_limit = max(tolerance, mp.sqrt(tolerance)) * scale
                require(
                    abs(result_value) <= residual_limit,
                    "E_DOMAIN",
                    "the sign change does not certify a root; the bracket may contain a discontinuity",
                )
            result_text = mp.nstr(result, precision)
            error_text = mp.nstr(error_bound, precision)
            residual_text = mp.nstr(abs(result_value), precision)
            final_bracket = [mp.nstr(lower_value, precision), mp.nstr(upper_value, precision)]
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
        "method": "bisection",
        "converged": True,
        "iterations": iterations,
        "tolerance": tolerance_text,
        "errorBound": error_text,
        "residual": residual_text,
        "finalBracket": final_bracket,
        "warnings": ["Numerical root with a bracket-width error bound; no exact symbolic value is claimed."],
    }
