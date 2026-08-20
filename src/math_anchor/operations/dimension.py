from __future__ import annotations

from fractions import Fraction
from math import gcd, lcm
import re
from typing import Any

import pint
import sympy as sp

from ..dimension_expression import (
    DIMENSION_SYMBOL_PATTERN,
    DimensionExpressionAnalyzer,
    DimensionFormula,
    DimensionVector,
    normalize_dimension_source,
)
from ..errors import CalculatorError, require
from ..validation import list_arg, string_arg
from .data import _exact_unit_registry, _sympy_fraction


_IDENTIFIER = re.compile(DIMENSION_SYMBOL_PATTERN, re.ASCII)
_PI_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$", re.ASCII)
_MAX_SYMBOLS = 64
_MAX_UNKNOWNS = 16
_MAX_EQUATIONS = 32
_MAX_PI_VARIABLES = 16


def check(arguments: dict[str, Any]) -> dict[str, Any]:
    left_expression = string_arg(arguments, "left", max_length=2048)
    right_expression = string_arg(arguments, "right", max_length=2048)
    dimensions = _dimension_declarations(arguments, "symbols", maximum=_MAX_SYMBOLS)
    bindings = {
        symbol: DimensionFormula.known(dimension)
        for symbol, dimension in dimensions.items()
    }
    analyzer = DimensionExpressionAnalyzer(bindings, max_total_nodes=512)
    left_constraint_start = len(analyzer.constraints)
    left = analyzer.analyze(left_expression)
    left_issues = analyzer.concrete_issues(
        analyzer.constraints[left_constraint_start:]
    )
    right_constraint_start = len(analyzer.constraints)
    right = analyzer.analyze(right_expression)
    right_issues = analyzer.concrete_issues(
        analyzer.constraints[right_constraint_start:]
    )
    equation_issues: list[dict[str, Any]] = []
    if not left_issues and not right_issues:
        equation_constraint_start = len(analyzer.constraints)
        analyzer.add_equation(
            left,
            right,
            f"{normalize_dimension_source(left_expression)} = {normalize_dimension_source(right_expression)}",
        )
        equation_issues = analyzer.concrete_issues(
            analyzer.constraints[equation_constraint_start:]
        )
    issues = [*left_issues, *right_issues, *equation_issues]
    left_dimension = None if left_issues else left.constant
    right_dimension = None if right_issues else right.constant

    return {
        "status": "ok",
        "operation": "dimension.check",
        "kind": "dimensional_analysis",
        "scope": "dimensional_consistency_only",
        "dimensionallyConsistent": not issues,
        "leftExpression": left_expression,
        "rightExpression": right_expression,
        "leftDimension": left_dimension.to_json() if left_dimension is not None else None,
        "rightDimension": right_dimension.to_json() if right_dimension is not None else None,
        "leftDisplay": left_dimension.display() if left_dimension is not None else None,
        "rightDisplay": right_dimension.display() if right_dimension is not None else None,
        "issues": issues,
        "warnings": [],
    }


def infer(arguments: dict[str, Any]) -> dict[str, Any]:
    equations = list_arg(arguments, "equations", minimum=1, maximum=_MAX_EQUATIONS)
    known = _dimension_declarations(arguments, "known", maximum=_MAX_SYMBOLS, default={})
    unknowns = _unknown_symbols(arguments)
    overlap = sorted(set(known) & set(unknowns))
    require(not overlap, "E_INPUT", "known and unknown symbols must not overlap")

    bindings = {
        **{
            symbol: DimensionFormula.known(dimension)
            for symbol, dimension in known.items()
        },
        **{symbol: DimensionFormula.unknown(symbol) for symbol in unknowns},
    }
    analyzer = DimensionExpressionAnalyzer(bindings, max_total_nodes=2048)
    for index, equation in enumerate(equations):
        require(isinstance(equation, dict), "E_INPUT", f"equations[{index}] must be an object")
        left_expression = _bounded_expression_field(equation, "left", index)
        right_expression = _bounded_expression_field(equation, "right", index)
        left = analyzer.analyze(left_expression)
        right = analyzer.analyze(right_expression)
        analyzer.add_equation(
            left,
            right,
            f"{normalize_dimension_source(left_expression)} = {normalize_dimension_source(right_expression)}",
        )

    constraints = analyzer.constraints
    differences = [constraint.difference for constraint in constraints]
    coefficient_rows = [difference.coefficient_dict() for difference in differences]
    constants = [difference.constant.as_dict() for difference in differences]
    matrix = sp.Matrix(
        [
            [
                _sympy_fraction(coefficients.get(symbol, Fraction()))
                for symbol in unknowns
            ]
            for coefficients in coefficient_rows
        ]
    )
    rank = int(matrix.rank())
    base_dimensions = sorted({name for constant in constants for name in constant})
    right_sides = {
        name: sp.Matrix(
            [
                -_sympy_fraction(constant.get(name, Fraction()))
                for constant in constants
            ]
        )
        for name in base_dimensions
    }
    conflicting_dimensions = [
        name
        for name, right_side in right_sides.items()
        if int(matrix.row_join(right_side).rank()) > rank
    ]

    if conflicting_dimensions:
        classification = "inconsistent"
        resolved_indexes = []
        unresolved = unknowns
    else:
        nullspace = matrix.nullspace()
        resolved_indexes = [
            index
            for index in range(len(unknowns))
            if all(vector[index, 0] == 0 for vector in nullspace)
        ]
        unresolved = [
            symbol
            for index, symbol in enumerate(unknowns)
            if index not in resolved_indexes
        ]
        classification = "unique" if not unresolved else "underdetermined"

    inferred: dict[str, dict[str, Any]] = {}
    if classification != "inconsistent":
        inferred_components: dict[str, dict[str, Fraction]] = {
            unknowns[index]: {} for index in resolved_indexes
        }
        for name, right_side in right_sides.items():
            solution_set = sp.linsolve((matrix, right_side))
            require(solution_set is not sp.EmptySet, "E_RUNTIME", "dimension solver lost a consistent solution")
            solution = next(iter(solution_set))
            require(len(solution) == len(unknowns), "E_RUNTIME", "dimension solver returned the wrong shape")
            for index in resolved_indexes:
                symbol = unknowns[index]
                value = solution[index]
                require(
                    not value.free_symbols,
                    "E_RUNTIME",
                    "dimension solver left a resolved symbol dependent on a free parameter",
                )
                fraction = _fraction_from_sympy(value)
                if fraction:
                    inferred_components[symbol][name] = fraction
        for index in resolved_indexes:
            symbol = unknowns[index]
            dimension = DimensionVector._from_derived_mapping(inferred_components[symbol])
            inferred[symbol] = {
                "dimension": dimension.to_json(),
                "display": dimension.display(),
            }

    return {
        "status": "ok",
        "operation": "dimension.infer",
        "kind": "dimensional_inference",
        "scope": "dimensional_consistency_only",
        "classification": classification,
        "unknowns": unknowns,
        "inferred": inferred,
        "unresolved": unresolved,
        "rank": rank,
        "constraintCount": len(constraints),
        "degreesOfFreedom": max(0, len(unknowns) - rank),
        "conflictingDimensions": conflicting_dimensions,
        "warnings": [],
    }


def pi_groups(arguments: dict[str, Any]) -> dict[str, Any]:
    declarations = _pi_unit_declarations(arguments)

    variables = sorted(declarations)
    dimensions = sorted(
        {
            name
            for dimension in declarations.values()
            for name, _ in dimension.components
        }
    )
    matrix = (
        sp.Matrix(
            [
                [
                    _sympy_fraction(declarations[variable].exponent(dimension))
                    for variable in variables
                ]
                for dimension in dimensions
            ]
        )
        if dimensions
        else sp.zeros(0, len(variables))
    )
    rank = int(matrix.rank())
    basis = matrix.nullspace()
    groups = []
    for index, vector in enumerate(basis, start=1):
        integer_exponents = _primitive_integer_exponents(vector)
        exponents = {
            variable: str(exponent)
            for variable, exponent in zip(variables, integer_exponents)
            if exponent
        }
        groups.append(
            {
                "index": index,
                "exponents": exponents,
                "expression": _render_pi_group(exponents),
            }
        )

    return {
        "status": "ok",
        "operation": "dimension.pi_groups",
        "kind": "dimensionless_groups",
        "scope": "dimensionless_basis_only",
        "basisConvention": "primitive_integer_exponents",
        "variables": variables,
        "rank": rank,
        "nullity": len(groups),
        "groups": groups,
        "warnings": (
            [
                "A dimensionless basis is not unique; equivalent products or powers span the same space."
            ]
            if groups
            else []
        ),
    }


def _pi_unit_declarations(arguments: dict[str, Any]) -> dict[str, DimensionVector]:
    value = arguments.get("variables")
    require(isinstance(value, dict), "E_INPUT", "variables must be an object")
    require(bool(value), "E_INPUT", "variables must contain at least one symbol")
    require(
        len(value) <= _MAX_PI_VARIABLES,
        "E_LIMIT",
        f"variables may contain at most {_MAX_PI_VARIABLES} symbols",
    )
    result: dict[str, DimensionVector] = {}
    for symbol, declaration in value.items():
        require(
            isinstance(symbol, str)
            and symbol == symbol.strip()
            and bool(_PI_IDENTIFIER.fullmatch(symbol)),
            "E_INPUT",
            "Pi-group variable names must be ASCII identifiers",
        )
        require(len(symbol) <= 64, "E_LIMIT", "Pi-group variable names may not exceed 64 characters")
        require(
            isinstance(declaration, str),
            "E_INPUT",
            f"variables.{symbol} must be a unit-expression string",
        )
        result[symbol] = _dimension_declaration(
            declaration,
            label=f"variables.{symbol}",
        )
    return result


def _dimension_declarations(
    arguments: dict[str, Any],
    name: str,
    *,
    maximum: int,
    default: dict[str, Any] | None = None,
) -> dict[str, DimensionVector]:
    value = arguments.get(name, default)
    require(isinstance(value, dict), "E_INPUT", f"{name} must be an object")
    require(len(value) <= maximum, "E_LIMIT", f"{name} may contain at most {maximum} symbols")
    result: dict[str, DimensionVector] = {}
    for symbol, declaration in value.items():
        _validate_identifier(symbol, label=f"{name} symbol")
        require(symbol not in result, "E_INPUT", f"duplicate {name} symbol: {symbol}")
        result[symbol] = _dimension_declaration(declaration, label=f"{name}.{symbol}")
    return result


def _dimension_declaration(value: Any, *, label: str) -> DimensionVector:
    if isinstance(value, str):
        unit_expression = value.strip()
        require(bool(unit_expression), "E_INPUT", f"{label} must not be empty")
        require(len(unit_expression) <= 128, "E_LIMIT", f"{label} is too long")
        try:
            unit = _exact_unit_registry().parse_units(normalize_dimension_source(unit_expression))
            return DimensionVector.from_mapping(unit.dimensionality)
        except (pint.PintError, TypeError, ValueError) as error:
            raise CalculatorError("E_UNIT", f"invalid unit declaration for {label}: {error}") from error
    if isinstance(value, dict):
        return DimensionVector.from_mapping(value)
    raise CalculatorError(
        "E_INPUT",
        f"{label} must be a unit-expression string or a dimension-vector object",
    )


def _unknown_symbols(arguments: dict[str, Any]) -> list[str]:
    values = list_arg(arguments, "unknown", minimum=1, maximum=_MAX_UNKNOWNS)
    normalized: list[str] = []
    for index, value in enumerate(values):
        _validate_identifier(value, label=f"unknown[{index}]")
        normalized.append(value)
    require(len(set(normalized)) == len(normalized), "E_INPUT", "unknown symbols must not contain duplicates")
    return normalized


def _validate_identifier(value: Any, *, label: str) -> None:
    require(
        isinstance(value, str)
        and value == value.strip()
        and bool(_IDENTIFIER.fullmatch(value)),
        "E_INPUT",
        f"{label} must be a valid identifier",
    )
    require(len(value) <= 64, "E_LIMIT", f"{label} may not exceed 64 characters")


def _bounded_expression_field(equation: dict[str, Any], name: str, index: int) -> str:
    value = equation.get(name)
    require(isinstance(value, str), "E_INPUT", f"equations[{index}].{name} must be a string")
    normalized = value.strip()
    require(bool(normalized), "E_INPUT", f"equations[{index}].{name} must not be empty")
    require(len(normalized) <= 2048, "E_LIMIT", f"equations[{index}].{name} is too long")
    return normalized


def _fraction_from_sympy(value: sp.Expr) -> Fraction:
    require(value.is_Rational is True, "E_RUNTIME", "dimension solver returned a non-rational exponent")
    rational = sp.Rational(value)
    return Fraction(int(rational.p), int(rational.q))


def _primitive_integer_exponents(vector: sp.Matrix) -> list[int]:
    fractions = [_fraction_from_sympy(value) for value in vector]
    denominator_lcm = 1
    for value in fractions:
        denominator_lcm = lcm(denominator_lcm, value.denominator)
    integers = [
        value.numerator * (denominator_lcm // value.denominator)
        for value in fractions
    ]
    common_divisor = 0
    for value in integers:
        common_divisor = gcd(common_divisor, abs(value))
    require(common_divisor > 0, "E_RUNTIME", "dimension solver returned an empty basis vector")
    integers = [value // common_divisor for value in integers]

    positive_count = sum(value > 0 for value in integers)
    negative_count = sum(value < 0 for value in integers)
    first_nonzero = next(value for value in integers if value)
    if negative_count > positive_count or (
        negative_count == positive_count and first_nonzero < 0
    ):
        integers = [-value for value in integers]

    require(
        all(len(str(abs(value))) <= 2048 for value in integers),
        "E_LIMIT",
        "dimensionless group exponents are too complex",
    )
    return integers


def _render_pi_group(exponents: dict[str, str]) -> str:
    positive: list[str] = []
    negative: list[str] = []
    for variable, text in exponents.items():
        exponent = int(text)
        target = positive if exponent > 0 else negative
        absolute = abs(exponent)
        target.append(variable if absolute == 1 else f"{variable}^{absolute}")
    numerator = " * ".join(positive) if positive else "1"
    if not negative:
        return numerator
    denominator = " * ".join(negative)
    if len(negative) > 1:
        denominator = f"({denominator})"
    return f"{numerator} / {denominator}"
