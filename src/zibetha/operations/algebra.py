from __future__ import annotations

from typing import Any

import sympy as sp

from ..errors import require
from ..formatting import solution_result, typed_scalar_result
from ..safe_expression import make_symbols, parse_equation, parse_expression
from ..validation import enum_arg, integer_arg, string_arg, variables_arg


_TRANSFORMS = ("simplify", "expand", "factor", "cancel", "apart", "collect")


def transform(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", _TRANSFORMS, default="simplify")
    expression_text = string_arg(arguments, "expression")
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    variable_names = arguments.get("variables", [])
    require(isinstance(variable_names, list), "E_INPUT", "variables must be an array")
    require(all(isinstance(name, str) for name in variable_names), "E_INPUT", "variables must contain strings")

    focus_variable = arguments.get("variable")
    if action in {"apart", "collect"}:
        require(isinstance(focus_variable, str) and focus_variable.strip(), "E_INPUT", f"{action} requires variable")
        focus_variable = focus_variable.strip()
        if focus_variable not in variable_names:
            variable_names = [*variable_names, focus_variable]

    symbols = make_symbols(variable_names)
    expression = parse_expression(expression_text, symbols=symbols)
    if action == "simplify":
        result = sp.simplify(expression)
    elif action == "expand":
        result = sp.expand(expression)
    elif action == "factor":
        result = sp.factor(expression)
    elif action == "cancel":
        result = sp.cancel(expression)
    elif action == "apart":
        result = sp.apart(expression, symbols[str(focus_variable)])
    else:
        result = sp.collect(expression, symbols[str(focus_variable)])
    return typed_scalar_result(
        "algebra.transform",
        "transformation",
        result,
        precision,
        action=action,
    )


def solve(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_equations = arguments.get("equations")
    if isinstance(raw_equations, str):
        equation_texts = [raw_equations]
    else:
        require(
            isinstance(raw_equations, list)
            and raw_equations
            and all(isinstance(item, str) for item in raw_equations),
            "E_INPUT",
            "equations must be a string or non-empty array of strings",
        )
        equation_texts = raw_equations
    require(len(equation_texts) <= 16, "E_LIMIT", "at most 16 equations are allowed")

    variable_names = variables_arg(arguments, maximum=8)
    symbols = make_symbols(variable_names)
    equations = [parse_equation(text, symbols) for text in equation_texts]
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    domain = enum_arg(arguments, "domain", ("real", "complex"), default="complex")

    ordered_symbols = list(symbols.values())
    target_domain = sp.S.Reals if domain == "real" else sp.S.Complexes
    solutions: list[dict[sp.Symbol, sp.Expr]] = []
    warnings: list[str] = []
    if len(ordered_symbols) == 1:
        symbol = ordered_symbols[0]
        expression = _equation_expression(equations[0])
        solution_set = sp.solveset(expression, symbol, domain=target_domain)
        complete = not solution_set.has(sp.ConditionSet)
        if solution_set is sp.S.EmptySet:
            classification = "none"
        elif isinstance(solution_set, sp.FiniteSet):
            classification = "finite"
            solutions = [{symbol: value} for value in solution_set]
        elif complete:
            classification = "infinite"
        else:
            classification = "unknown"
            warnings.append("The symbolic engine returned a conditional solution set; completeness is not proven.")
    else:
        expressions = [_equation_expression(equation) for equation in equations]
        solution_set = sp.nonlinsolve(expressions, ordered_symbols)
        complete = not solution_set.has(sp.ConditionSet)
        if solution_set is sp.S.EmptySet:
            classification = "none"
        else:
            tuples = list(solution_set) if isinstance(solution_set, sp.FiniteSet) else []
            retained: list[tuple[sp.Expr, ...]] = []
            for values in tuples:
                value_tuple = tuple(values)
                if domain == "real" and any(value.is_real is False for value in value_tuple):
                    continue
                if domain == "real" and any(value.is_real is None for value in value_tuple):
                    complete = False
                    warnings.append("Some symbolic solutions could not be proven real and were retained.")
                retained.append(value_tuple)
            solutions = [dict(zip(ordered_symbols, values, strict=True)) for values in retained]
            has_free_values = any(
                value in {sp.S.Reals, sp.S.Complexes} or bool(value.free_symbols & set(ordered_symbols))
                for values in retained
                for value in values
            )
            if not retained and tuples:
                classification = "none"
            elif has_free_values or not isinstance(solution_set, sp.FiniteSet):
                classification = "infinite"
            elif complete:
                classification = "finite"
            else:
                classification = "unknown"
    return solution_result(
        "algebra.solve",
        solutions,
        precision,
        warnings=list(dict.fromkeys(warnings)),
        classification=classification,
        complete=complete,
        solution_set=sp.sstr(solution_set),
    )


def _equation_expression(equation: Any) -> sp.Expr:
    if equation is sp.S.true:
        return sp.Integer(0)
    if equation is sp.S.false:
        return sp.Integer(1)
    return equation.lhs - equation.rhs
