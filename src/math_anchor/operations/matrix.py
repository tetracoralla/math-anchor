from __future__ import annotations

from typing import Any

import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import effective_precision, matrix_result, matrix_value, scalar_result, value_result, values_result
from ..safe_expression import parse_matrix
from ..validation import enum_arg, integer_arg, variables_arg


def determinant(arguments: dict[str, Any]) -> dict[str, Any]:
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    matrix = parse_matrix(arguments.get("matrix"))
    require(matrix.rows == matrix.cols, "E_INPUT", "determinant requires a square matrix")
    return scalar_result("matrix.determinant", matrix.det(), precision)


def inverse(arguments: dict[str, Any]) -> dict[str, Any]:
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    matrix = parse_matrix(arguments.get("matrix"))
    require(matrix.rows == matrix.cols, "E_INPUT", "inverse requires a square matrix")
    try:
        result = matrix.inv()
    except Exception as error:
        raise CalculatorError("E_DOMAIN", "matrix is singular and has no inverse") from error
    return matrix_result("matrix.inverse", result, precision)


def eigenvalues(arguments: dict[str, Any]) -> dict[str, Any]:
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    matrix = parse_matrix(arguments.get("matrix"))
    require(matrix.rows == matrix.cols, "E_INPUT", "eigenvalues require a square matrix")
    values = matrix.eigenvals()
    expanded: list[sp.Expr] = []
    for value, multiplicity in values.items():
        expanded.extend([value] * multiplicity)
    return values_result("matrix.eigenvalues", expanded, precision)


def solve(arguments: dict[str, Any]) -> dict[str, Any]:
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    coefficients = parse_matrix(arguments.get("matrix"))
    constants = arguments.get("constants")
    require(isinstance(constants, list) and constants, "E_INPUT", "constants must be a non-empty array")
    require(len(constants) == coefficients.rows, "E_INPUT", "constants must match the matrix row count")
    right_hand_side = parse_matrix([[value] for value in constants])
    _require_exact(coefficients, "matrix.solve")
    _require_exact(right_hand_side, "matrix.solve")

    if "variables" in arguments:
        variables = variables_arg(arguments, maximum=50)
        require(len(variables) == coefficients.cols, "E_INPUT", "variables must match the matrix column count")
    else:
        variables = [f"x{index + 1}" for index in range(coefficients.cols)]

    rank = int(coefficients.rank())
    augmented_rank = int(coefficients.row_join(right_hand_side).rank())
    if rank < augmented_rank:
        classification = "inconsistent"
        particular = None
        basis: list[sp.Matrix] = []
    else:
        classification = "unique" if rank == coefficients.cols else "infinite"
        solution, parameters, _ = coefficients.gauss_jordan_solve(right_hand_side, freevar=True)
        substitutions = {parameter: sp.Integer(0) for parameter in list(parameters)}
        particular = solution.subs(substitutions)
        basis = [] if classification == "unique" else coefficients.nullspace()

    values = ([] if particular is None else list(particular)) + [value for vector in basis for value in vector]
    reported_precision = effective_precision(values, precision)
    return {
        "status": "ok",
        "operation": "matrix.solve",
        "kind": "linear_system",
        "classification": classification,
        "variables": variables,
        "rank": rank,
        "augmentedRank": augmented_rank,
        "particular": None
        if particular is None
        else [value_result(value, reported_precision) for value in particular],
        "nullspace": [
            [value_result(value, reported_precision) for value in vector]
            for vector in basis
        ],
        "precision": reported_precision,
        "warnings": [],
    }


def reduce(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", ("rank", "rref", "nullspace", "columnspace"), default="rank")
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    matrix = parse_matrix(arguments.get("matrix"))
    _require_exact(matrix, "matrix.reduce")
    if action == "rank":
        return {
            "status": "ok",
            "operation": "matrix.reduce",
            "kind": "matrix_reduction",
            "action": action,
            "rank": int(matrix.rank()),
            "precision": precision,
            "warnings": [],
        }
    if action == "rref":
        reduced, pivots = matrix.rref()
        return {
            "status": "ok",
            "operation": "matrix.reduce",
            "kind": "matrix_reduction",
            "action": action,
            **matrix_value(reduced, precision),
            "pivots": list(pivots),
            "warnings": [],
        }
    basis = matrix.nullspace() if action == "nullspace" else matrix.columnspace()
    values = [value for vector in basis for value in vector]
    reported_precision = effective_precision(values, precision)
    vector_size = matrix.cols if action == "nullspace" else matrix.rows
    return {
        "status": "ok",
        "operation": "matrix.reduce",
        "kind": "matrix_reduction",
        "action": action,
        "basis": [
            [value_result(value, reported_precision) for value in vector]
            for vector in basis
        ],
        "dimension": len(basis),
        "vectorSize": vector_size,
        "precision": reported_precision,
        "warnings": [],
    }


def _require_exact(matrix: sp.MatrixBase, operation: str) -> None:
    require(
        not any(value.atoms(sp.Float) for value in matrix),
        "E_INPUT",
        f"{operation} requires exact entries; use integers or rational text such as 1/10",
    )
