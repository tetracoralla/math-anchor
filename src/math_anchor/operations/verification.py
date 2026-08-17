from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import islice
import ast
import re
from typing import Any

import sympy as sp
from sympy.calculus.util import continuous_domain

from ..errors import CalculatorError, require
from ..formatting import approximate, value_result
from ..safe_expression import make_symbols, normalize_expression_source, parse_expression
from ..validation import enum_arg, integer_arg, string_arg, variables_arg


_RELATION = re.compile(r"(?<![<>=!])(<=|>=|!=|=|<|>)(?![=])")
_PROBES = (
    sp.Integer(0),
    sp.Integer(1),
    sp.Integer(-1),
    sp.Rational(1, 2),
    sp.Rational(-1, 2),
    sp.Integer(2),
    sp.Integer(-2),
    sp.Integer(3),
    sp.pi,
    sp.E,
)


@dataclass(frozen=True)
class _Constraint:
    source: str
    left: sp.Expr
    operator: str
    right: sp.Expr


def expression_equivalent(arguments: dict[str, Any]) -> dict[str, Any]:
    left_text = string_arg(arguments, "left")
    right_text = string_arg(arguments, "right")
    raw_variables = arguments.get("variables")
    require(isinstance(raw_variables, list), "E_INPUT", "variables must be an array")
    require(all(isinstance(item, str) for item in raw_variables), "E_INPUT", "variables must contain strings")
    require(len(raw_variables) <= 16, "E_LIMIT", "variables may contain at most 16 items")
    variable_names = [item.strip() for item in raw_variables]
    symbols = make_symbols(variable_names)
    domain_name = enum_arg(arguments, "domain", ("real", "complex"), default="real")
    definedness_policy = enum_arg(
        arguments,
        "definednessPolicy",
        ("strict", "common_domain"),
        default="strict",
    )
    precision = integer_arg(arguments, "precision", default=30, minimum=2, maximum=200)

    left = parse_expression(left_text, symbols=symbols)
    right = parse_expression(right_text, symbols=symbols)
    left_restrictions = _source_domain_restrictions(left_text, symbols)
    right_restrictions = _source_domain_restrictions(right_text, symbols)
    difference = sp.simplify(left - right)
    left_domain, right_domain, definedness = _compare_definedness(
        left,
        right,
        list(symbols.values()),
        domain_name,
        left_restrictions,
        right_restrictions,
        normalize_expression_source(left_text) == normalize_expression_source(right_text),
    )
    counterexample = None
    proven = False
    warnings: list[str] = []

    if definedness_policy == "strict" and definedness == "different":
        equivalence = "not_equivalent"
        proven = True
        warnings.append("The expressions differ in where they are defined, even if their simplified values agree elsewhere.")
    elif difference == 0:
        if definedness_policy == "common_domain" or definedness == "same":
            equivalence = "equivalent"
            proven = True
        else:
            equivalence = "unknown"
            warnings.append("Value equality was proven where both expressions are defined, but multivariable definedness equality was not proven.")
    else:
        counterexample = _find_counterexample(
            left,
            right,
            list(symbols.values()),
            precision,
            domain_name,
            left_restrictions,
            right_restrictions,
        )
        if counterexample is not None:
            equivalence = "not_equivalent"
            proven = True
        else:
            equivalence = "unknown"
            warnings.append("Symbolic reduction did not prove equality and bounded deterministic probes found no valid counterexample.")

    return {
        "status": "ok",
        "operation": "expression.equivalent",
        "kind": "equivalence_verification",
        "equivalence": equivalence,
        "proven": proven,
        "domain": domain_name,
        "definednessPolicy": definedness_policy,
        "definedness": definedness,
        "leftDomain": left_domain,
        "rightDomain": right_domain,
        "difference": value_result(difference, precision),
        "counterexample": counterexample,
        "precision": precision,
        "warnings": warnings,
    }


def solution_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_constraints = arguments.get("constraints")
    if isinstance(raw_constraints, str):
        constraint_texts = [raw_constraints]
    else:
        require(
            isinstance(raw_constraints, list)
            and raw_constraints
            and all(isinstance(item, str) for item in raw_constraints),
            "E_INPUT",
            "constraints must be a string or non-empty array of strings",
        )
        constraint_texts = raw_constraints
    require(len(constraint_texts) <= 16, "E_LIMIT", "at most 16 constraints are allowed")

    variable_names = variables_arg(arguments, maximum=8)
    symbols = make_symbols(variable_names)
    constraints = [_parse_constraint(text, symbols) for text in constraint_texts]
    raw_candidates = arguments.get("candidates")
    require(isinstance(raw_candidates, list) and raw_candidates, "E_INPUT", "candidates must be a non-empty array")
    require(len(raw_candidates) <= 64, "E_LIMIT", "at most 64 candidates are allowed")
    precision = integer_arg(arguments, "precision", default=30, minimum=2, maximum=200)
    tolerance_text = string_arg(arguments, "tolerance", default="1e-12", max_length=64)
    try:
        tolerance_decimal = Decimal(tolerance_text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", "tolerance must be positive decimal text") from error
    require(tolerance_decimal.is_finite() and tolerance_decimal > 0, "E_INPUT", "tolerance must be positive and finite")
    tolerance_fraction = Fraction(tolerance_decimal)
    tolerance = sp.Rational(tolerance_fraction.numerator, tolerance_fraction.denominator)
    domain_name = enum_arg(arguments, "domain", ("real", "complex"), default="real")
    require(
        domain_name == "real" or all(constraint.operator in {"=", "!="} for constraint in constraints),
        "E_INPUT",
        "ordered inequalities require the real domain",
    )
    check_completeness = arguments.get("checkCompleteness", False)
    require(isinstance(check_completeness, bool), "E_INPUT", "checkCompleteness must be a boolean")

    candidate_rows: list[dict[str, Any]] = []
    parsed_candidates: list[dict[sp.Symbol, sp.Expr]] = []
    for index, raw_candidate in enumerate(raw_candidates):
        candidate = _parse_candidate(raw_candidate, symbols, domain_name)
        parsed_candidates.append(candidate)
        checks = [_verify_constraint(constraint, candidate, tolerance, precision) for constraint in constraints]
        valid_states = [check["satisfied"] for check in checks]
        valid: bool | None
        if any(state is False for state in valid_states):
            valid = False
        elif all(state is True for state in valid_states):
            valid = True
        else:
            valid = None
        candidate_rows.append(
            {
                "index": index,
                "values": {str(symbol): value_result(value, precision) for symbol, value in candidate.items()},
                "valid": valid,
                "checks": checks,
            }
        )

    completeness, omission_risk, omitted = _assess_completeness(
        constraints,
        list(symbols.values()),
        parsed_candidates,
        domain_name,
        tolerance,
        precision,
        check_completeness,
    )
    all_valid: bool | None
    states = [row["valid"] for row in candidate_rows]
    if any(state is False for state in states):
        all_valid = False
    elif all(state is True for state in states):
        all_valid = True
    else:
        all_valid = None
    warnings = []
    if omission_risk == "not_assessed":
        warnings.append("Candidate verification does not prove that all solutions were supplied.")
    elif omission_risk == "known_omissions":
        warnings.append("The supplied candidates omit one or more solutions from the proven finite solution set.")

    return {
        "status": "ok",
        "operation": "solution.verify",
        "kind": "solution_verification",
        "domain": domain_name,
        "tolerance": tolerance_text,
        "allValid": all_valid,
        "candidates": candidate_rows,
        "completeness": completeness,
        "omissionRisk": omission_risk,
        "omittedSolutions": [value_result(value, precision) for value in omitted],
        "precision": precision,
        "warnings": warnings,
    }


def _compare_definedness(
    left: sp.Expr,
    right: sp.Expr,
    symbols: list[sp.Symbol],
    domain_name: str,
    left_restrictions: list[tuple[str, sp.Expr]],
    right_restrictions: list[tuple[str, sp.Expr]],
    identical_source: bool,
) -> tuple[str | None, str | None, str]:
    if not symbols:
        return domain_name, domain_name, "same"
    if identical_source:
        return "identical expression domain", "identical expression domain", "same"
    if len(symbols) > 1:
        if not left_restrictions and not right_restrictions and left.is_polynomial(*symbols) and right.is_polynomial(*symbols):
            return domain_name, domain_name, "same"
        return None, None, "unknown"
    symbol = symbols[0]
    try:
        if domain_name == "real":
            left_set = continuous_domain(left, symbol, sp.S.Reals)
            right_set = continuous_domain(right, symbol, sp.S.Reals)
            left_set = _apply_real_restrictions(left_set, left_restrictions, symbol)
            right_set = _apply_real_restrictions(right_set, right_restrictions, symbol)
        else:
            left_singularities = sp.singularities(left, symbol, sp.S.Complexes)
            right_singularities = sp.singularities(right, symbol, sp.S.Complexes)
            left_singularities = _apply_complex_restrictions(left_singularities, left_restrictions, symbol)
            right_singularities = _apply_complex_restrictions(right_singularities, right_restrictions, symbol)
            left_set = sp.Complement(sp.S.Complexes, left_singularities)
            right_set = sp.Complement(sp.S.Complexes, right_singularities)
        same = left_set == right_set
        return sp.sstr(left_set), sp.sstr(right_set), "same" if same else "different"
    except (NotImplementedError, TypeError, ValueError):
        return None, None, "unknown"


def _find_counterexample(
    left: sp.Expr,
    right: sp.Expr,
    symbols: list[sp.Symbol],
    precision: int,
    domain_name: str,
    left_restrictions: list[tuple[str, sp.Expr]],
    right_restrictions: list[tuple[str, sp.Expr]],
) -> dict[str, Any] | None:
    substitutions = [{}] if not symbols else list(islice(_probe_substitutions(symbols), 24))
    # Probes evaluate numerically at guard digits rather than through
    # repeated symbolic simplification: a counterexample only needs a
    # material numeric difference at a point where both sides are defined.
    # True zeros stay below the skip threshold because the evaluation noise
    # (about 1e-(precision+10) relative) sits far underneath it.
    evaluation_precision = precision + 12
    skip_threshold = sp.Float(f"1e-{max(2, precision - 5)}")
    for substitution in substitutions:
        try:
            if not _point_in_source_domain(substitution, domain_name, left_restrictions):
                continue
            if not _point_in_source_domain(substitution, domain_name, right_restrictions):
                continue
            left_value = left.subs(substitution).evalf(evaluation_precision)
            right_value = right.subs(substitution).evalf(evaluation_precision)
            if not _is_finite_number(left_value) or not _is_finite_number(right_value):
                continue
            if domain_name == "real" and (left_value.is_real is not True or right_value.is_real is not True):
                continue
            numeric_delta = abs(sp.N(left_value - right_value, evaluation_precision))
            if not numeric_delta.is_real or numeric_delta <= skip_threshold:
                continue
            return {
                "values": {str(symbol): value_result(value, precision) for symbol, value in substitution.items()},
                "left": value_result(left_value, precision),
                "right": value_result(right_value, precision),
                "reason": "Both expressions are defined and produce different values.",
            }
        except (ArithmeticError, TypeError, ValueError):
            continue
    return None


def _probe_substitutions(symbols: list[sp.Symbol]):
    for offset in range(len(_PROBES)):
        yield {
            symbol: _PROBES[(offset + index * 3) % len(_PROBES)]
            for index, symbol in enumerate(symbols)
        }


def _parse_constraint(source: str, symbols: dict[str, sp.Symbol]) -> _Constraint:
    text = source.strip()
    require(bool(text), "E_INPUT", "constraints must not be empty")
    matches = list(_RELATION.finditer(text))
    require(len(matches) <= 1, "E_SYNTAX", "a constraint may contain at most one relation operator")
    if not matches:
        return _Constraint(text, parse_expression(text, symbols=symbols), "=", sp.Integer(0))
    match = matches[0]
    left_text, right_text = text[: match.start()], text[match.end() :]
    require(bool(left_text.strip()) and bool(right_text.strip()), "E_SYNTAX", "both sides of a constraint are required")
    return _Constraint(
        text,
        parse_expression(left_text, symbols=symbols),
        match.group(1),
        parse_expression(right_text, symbols=symbols),
    )


def _parse_candidate(
    raw_candidate: Any,
    symbols: dict[str, sp.Symbol],
    domain_name: str,
) -> dict[sp.Symbol, sp.Expr]:
    require(isinstance(raw_candidate, dict), "E_INPUT", "each candidate must be an object")
    require(set(raw_candidate) == set(symbols), "E_INPUT", "each candidate must provide exactly the declared variables")
    parsed: dict[sp.Symbol, sp.Expr] = {}
    for name, symbol in symbols.items():
        raw_value = raw_candidate[name]
        require(
            isinstance(raw_value, (int, float, str)) and not isinstance(raw_value, bool),
            "E_INPUT",
            f"candidate {name} must be a number or safe numeric expression",
        )
        value = parse_expression(str(raw_value))
        require(not value.free_symbols and _is_finite_number(value), "E_DOMAIN", f"candidate {name} must be finite")
        if domain_name == "real":
            require(value.is_real is True, "E_DOMAIN", f"candidate {name} must be real")
        parsed[symbol] = value
    return parsed


def _verify_constraint(
    constraint: _Constraint,
    candidate: dict[sp.Symbol, sp.Expr],
    tolerance: sp.Expr,
    precision: int,
) -> dict[str, Any]:
    left = sp.simplify(constraint.left.subs(candidate))
    right = sp.simplify(constraint.right.subs(candidate))
    residual = sp.simplify(left - right)
    if not _is_finite_number(left) or not _is_finite_number(right):
        return {
            "constraint": constraint.source,
            "relation": constraint.operator,
            "defined": False,
            "satisfied": False,
            "residual": {"exact": None, "approx": None},
            "residualMagnitude": None,
            "reason": "The candidate makes this constraint undefined.",
        }
    if constraint.operator == "=":
        satisfied = _zero_with_tolerance(residual, tolerance, precision)
    elif constraint.operator == "!=":
        zero = _zero_with_tolerance(residual, tolerance, precision)
        satisfied = None if zero is None else not zero
    else:
        relation = {
            "<": sp.Lt,
            "<=": sp.Le,
            ">": sp.Gt,
            ">=": sp.Ge,
        }[constraint.operator](left, right)
        satisfied = True if relation is sp.S.true else False if relation is sp.S.false else None
    magnitude = approximate(sp.Abs(residual), precision) if residual.is_number else None
    return {
        "constraint": constraint.source,
        "relation": constraint.operator,
        "defined": True,
        "satisfied": satisfied,
        "residual": value_result(residual, precision),
        "residualMagnitude": magnitude,
        "reason": None,
    }


def _zero_with_tolerance(value: sp.Expr, tolerance: sp.Expr, precision: int) -> bool | None:
    if value == 0 or value.is_zero is True:
        return True
    if value.is_zero is False and not value.atoms(sp.Float):
        return False
    try:
        numeric = sp.N(sp.Abs(value), precision)
        if numeric.is_real is True:
            return bool(numeric <= tolerance)
    except (ArithmeticError, TypeError, ValueError):
        pass
    return None


def _assess_completeness(
    constraints: list[_Constraint],
    symbols: list[sp.Symbol],
    candidates: list[dict[sp.Symbol, sp.Expr]],
    domain_name: str,
    tolerance: sp.Expr,
    precision: int,
    requested: bool,
) -> tuple[str, str, list[sp.Expr]]:
    if not requested:
        return "not_checked", "not_assessed", []
    if len(constraints) != 1 or len(symbols) != 1 or constraints[0].operator != "=":
        return "unknown", "not_assessed", []
    symbol = symbols[0]
    target = sp.S.Reals if domain_name == "real" else sp.S.Complexes
    try:
        solution_set = sp.solveset(constraints[0].left - constraints[0].right, symbol, domain=target)
    except (NotImplementedError, TypeError, ValueError):
        return "unknown", "not_assessed", []
    if not isinstance(solution_set, sp.FiniteSet) or len(solution_set) > 256:
        return "unknown", "not_assessed", []
    omitted = []
    for solution in solution_set:
        if not any(
            _zero_with_tolerance(candidate[symbol] - solution, tolerance, precision) is True
            for candidate in candidates
        ):
            omitted.append(solution)
    return (
        ("complete", "none_proven", [])
        if not omitted
        else ("incomplete", "known_omissions", omitted)
    )


def _is_finite_number(value: sp.Expr) -> bool:
    return bool(value.is_number and not value.has(sp.zoo, sp.nan, sp.oo, -sp.oo))


def _source_domain_restrictions(
    source: str,
    symbols: dict[str, sp.Symbol],
) -> list[tuple[str, sp.Expr]]:
    normalized = normalize_expression_source(source)
    try:
        parsed = ast.parse(normalized, mode="eval")
    except SyntaxError:
        return []
    restrictions: list[tuple[str, sp.Expr]] = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            segment = ast.get_source_segment(normalized, node.right)
            if segment:
                restrictions.append(("nonzero", parse_expression(segment, symbols=symbols)))
        if isinstance(node, ast.Call) or (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)):
            segment = ast.get_source_segment(normalized, node)
            if segment:
                restrictions.append(("continuous", parse_expression(segment, symbols=symbols)))
    return restrictions


def _apply_real_restrictions(
    domain: sp.Set,
    restrictions: list[tuple[str, sp.Expr]],
    symbol: sp.Symbol,
) -> sp.Set:
    result = domain
    for kind, expression in restrictions:
        if kind == "nonzero":
            excluded = sp.solveset(expression, symbol, domain=sp.S.Reals)
            result = sp.Complement(result, excluded)
        else:
            result = sp.Intersection(result, continuous_domain(expression, symbol, sp.S.Reals))
    return result


def _apply_complex_restrictions(
    singularities: sp.Set,
    restrictions: list[tuple[str, sp.Expr]],
    symbol: sp.Symbol,
) -> sp.Set:
    result = singularities
    for kind, expression in restrictions:
        if kind == "nonzero":
            result = sp.Union(result, sp.solveset(expression, symbol, domain=sp.S.Complexes))
        else:
            result = sp.Union(result, sp.singularities(expression, symbol, sp.S.Complexes))
    return result


def _point_in_source_domain(
    substitution: dict[sp.Symbol, sp.Expr],
    domain_name: str,
    restrictions: list[tuple[str, sp.Expr]],
) -> bool:
    for kind, expression in restrictions:
        value = sp.simplify(expression.subs(substitution))
        if not _is_finite_number(value):
            return False
        if kind == "nonzero" and value == 0:
            return False
        if domain_name == "real" and value.is_real is not True:
            return False
    return True
