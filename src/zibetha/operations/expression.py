from __future__ import annotations

from typing import Any

import sympy as sp

from ..errors import require
from ..formatting import scalar_result
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

