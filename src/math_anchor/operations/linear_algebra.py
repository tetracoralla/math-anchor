from __future__ import annotations

from typing import Any

import numpy as np
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import matrix_value, value_result
from ..safe_expression import parse_matrix
from ..validation import enum_arg, integer_arg, list_arg, string_arg
from .matrix import _require_exact
from .numerical import _binary64, _positive_float


def exact(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        ("matrix_multiply", "transpose", "dot", "cross", "norm", "norm_squared", "projection"),
        default="dot",
    )
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)

    if action in {"matrix_multiply", "transpose"}:
        left = _exact_matrix(arguments, "matrix" if action == "transpose" else "left")
        if action == "transpose":
            result = left.T
        else:
            right = _exact_matrix(arguments, "right")
            require(left.cols == right.rows, "E_INPUT", "left columns must match right rows")
            result = left * right
        return {
            "status": "ok",
            "operation": "linear_algebra.exact",
            "kind": "exact_matrix_algebra",
            "action": action,
            **matrix_value(result, precision),
            "warnings": [],
        }

    left = _exact_vector(arguments, "vector" if action in {"norm", "norm_squared"} else "left")
    dimension = len(left)
    if action == "norm_squared":
        result_scalar = left.dot(left)
    elif action == "norm":
        result_scalar = sp.sqrt(left.dot(left))
    else:
        right_name = "onto" if action == "projection" else "right"
        right = _exact_vector(arguments, right_name)
        require(len(right) == dimension, "E_INPUT", f"left and {right_name} vectors must have equal dimensions")
        if action == "dot":
            result_scalar = left.dot(right)
        elif action == "cross":
            require(dimension == 3, "E_INPUT", "cross product requires two three-dimensional vectors")
            return _vector_result(action, left.cross(right), precision)
        else:
            denominator = right.dot(right)
            require(denominator != 0, "E_DOMAIN", "projection target vector must be nonzero")
            return _vector_result(action, right * (left.dot(right) / denominator), precision)

    return {
        "status": "ok",
        "operation": "linear_algebra.exact",
        "kind": "exact_vector_algebra",
        "action": action,
        "dimension": dimension,
        "result": value_result(result_scalar, precision),
        "precision": precision,
        "warnings": [],
    }


def numeric(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        ("least_squares", "qr", "svd", "pseudoinverse"),
        default="least_squares",
    )
    matrix = _numeric_matrix(arguments, "matrix")
    tolerance_text = string_arg(arguments, "tolerance", default="1e-12", max_length=64)
    tolerance = _positive_float(tolerance_text, "tolerance")
    require(tolerance <= 1, "E_INPUT", "tolerance must not exceed 1")
    precision = integer_arg(arguments, "precision", default=15, minimum=2, maximum=15)
    warnings = [
        "Decimal text is converted to IEEE 754 binary64; all decomposition results and diagnostics are approximate."
    ]

    singular_values, rank, condition = _rank_diagnostics(matrix, tolerance)
    if rank < min(matrix.shape):
        warnings.append("The matrix is rank-deficient at the supplied relative singular-value tolerance.")

    try:
        if action == "least_squares":
            constants = _numeric_vector(arguments, "constants")
            require(len(constants) == matrix.shape[0], "E_INPUT", "constants length must match matrix row count")
            solution, _, _, _ = np.linalg.lstsq(matrix, constants, rcond=tolerance)
            residual = matrix @ solution - constants
            residual_norm = float(np.linalg.norm(residual, ord=2))
            constants_norm = float(np.linalg.norm(constants, ord=2))
            relative_residual = residual_norm / constants_norm if constants_norm else residual_norm
            solution_unique = rank == matrix.shape[1]
            solution_convention = (
                "unique_least_squares_minimizer"
                if solution_unique
                else "minimum_euclidean_norm"
            )
            if not solution_unique:
                warnings.append(
                    "The least-squares minimizer is not unique at the supplied tolerance; the returned solution is the minimum-Euclidean-norm minimizer."
                )
            _require_finite_array(solution, "least-squares solution")
            _require_finite_diagnostic(residual_norm, "least-squares residual")
            _require_finite_diagnostic(relative_residual, "relative least-squares residual")
            return _numeric_base(
                action,
                matrix,
                tolerance_text,
                precision,
                rank,
                condition,
                singular_values,
                warnings,
                classification="full_rank" if rank == min(matrix.shape) else "rank_deficient",
                solutionUnique=solution_unique,
                solutionConvention=solution_convention,
                solution=_vector_text(solution, precision),
                residualNorm=_diagnostic_text(residual_norm, precision),
                relativeResidualNorm=_diagnostic_text(relative_residual, precision),
            )

        if action == "qr":
            mode = enum_arg(arguments, "mode", ("reduced", "complete"), default="reduced")
            q, r = np.linalg.qr(matrix, mode=mode)
            reconstruction_error = float(np.linalg.norm(q @ r - matrix, ord="fro"))
            identity = np.eye(q.shape[1], dtype=np.float64)
            orthogonality_error = float(np.linalg.norm(q.T @ q - identity, ord="fro"))
            _require_finite_array(q, "Q factor")
            _require_finite_array(r, "R factor")
            _require_finite_diagnostic(reconstruction_error, "QR reconstruction error")
            _require_finite_diagnostic(orthogonality_error, "QR orthogonality error")
            return _numeric_base(
                action,
                matrix,
                tolerance_text,
                precision,
                rank,
                condition,
                singular_values,
                warnings,
                mode=mode,
                q=_matrix_text(q, precision),
                r=_matrix_text(r, precision),
                reconstructionError=_diagnostic_text(reconstruction_error, precision),
                orthogonalityError=_diagnostic_text(orthogonality_error, precision),
            )

        if action == "svd":
            full_matrices = arguments.get("fullMatrices", False)
            require(isinstance(full_matrices, bool), "E_INPUT", "fullMatrices must be a boolean")
            u, decomposition_values, v_transpose = np.linalg.svd(matrix, full_matrices=full_matrices)
            width = len(decomposition_values)
            reconstruction = (u[:, :width] * decomposition_values) @ v_transpose[:width, :]
            reconstruction_error = float(np.linalg.norm(reconstruction - matrix, ord="fro"))
            _require_finite_array(u, "left singular vectors")
            _require_finite_array(v_transpose, "right singular vectors")
            _require_finite_diagnostic(reconstruction_error, "SVD reconstruction error")
            return _numeric_base(
                action,
                matrix,
                tolerance_text,
                precision,
                rank,
                condition,
                singular_values,
                warnings,
                fullMatrices=full_matrices,
                u=_matrix_text(u, precision),
                vTranspose=_matrix_text(v_transpose, precision),
                reconstructionError=_diagnostic_text(reconstruction_error, precision),
            )

        pseudoinverse = np.linalg.pinv(matrix, rcond=tolerance)
        _require_finite_array(pseudoinverse, "pseudoinverse")
        aa_plus = matrix @ pseudoinverse
        a_plus_a = pseudoinverse @ matrix
        residuals = {
            "aAaMinusA": float(np.linalg.norm(aa_plus @ matrix - matrix, ord="fro")),
            "aPlusAaPlusMinusAPlus": float(
                np.linalg.norm(a_plus_a @ pseudoinverse - pseudoinverse, ord="fro")
            ),
            "aAaSymmetry": float(np.linalg.norm(aa_plus.T - aa_plus, ord="fro")),
            "aPlusASymmetry": float(np.linalg.norm(a_plus_a.T - a_plus_a, ord="fro")),
        }
        for name, value in residuals.items():
            _require_finite_diagnostic(value, f"Penrose residual {name}")
        return _numeric_base(
            action,
            matrix,
            tolerance_text,
            precision,
            rank,
            condition,
            singular_values,
            warnings,
            pseudoinverse=_matrix_text(pseudoinverse, precision),
            penroseResiduals={name: _diagnostic_text(value, precision) for name, value in residuals.items()},
        )
    except np.linalg.LinAlgError as error:
        raise CalculatorError("E_DOMAIN", f"numerical linear algebra failed: {error}") from error


def _exact_matrix(arguments: dict[str, Any], name: str) -> sp.MatrixBase:
    matrix = parse_matrix(arguments.get(name))
    _require_exact(matrix, "linear_algebra.exact")
    return matrix


def _exact_vector(arguments: dict[str, Any], name: str) -> sp.MatrixBase:
    raw = list_arg(arguments, name, maximum=50)
    matrix = parse_matrix([raw])
    _require_exact(matrix, "linear_algebra.exact")
    require(
        all(value.is_real is True for value in matrix),
        "E_INPUT",
        "linear_algebra.exact vector actions require provably real entries",
    )
    return matrix.T


def _vector_result(action: str, vector: sp.MatrixBase, precision: int) -> dict[str, Any]:
    return {
        "status": "ok",
        "operation": "linear_algebra.exact",
        "kind": "exact_vector_algebra",
        "action": action,
        "dimension": len(vector),
        "result": [value_result(value, precision) for value in vector],
        "precision": precision,
        "warnings": [],
    }


def _numeric_matrix(arguments: dict[str, Any], name: str) -> np.ndarray:
    raw = list_arg(arguments, name, maximum=32)
    require(all(isinstance(row, list) and row for row in raw), "E_INPUT", f"{name} rows must be non-empty arrays")
    width = len(raw[0])
    require(width <= 32, "E_LIMIT", f"{name} may contain at most 32 columns")
    require(all(len(row) == width for row in raw), "E_INPUT", f"{name} rows must have equal length")
    matrix = np.asarray(
        [
            [_binary64(value, f"{name}[{row_index}][{column_index}]") for column_index, value in enumerate(row)]
            for row_index, row in enumerate(raw)
        ],
        dtype=np.float64,
    )
    _require_finite_array(matrix, name)
    return matrix


def _numeric_vector(arguments: dict[str, Any], name: str) -> np.ndarray:
    raw = list_arg(arguments, name, maximum=32)
    vector = np.asarray([_binary64(value, f"{name}[{index}]") for index, value in enumerate(raw)], dtype=np.float64)
    _require_finite_array(vector, name)
    return vector


def _rank_diagnostics(matrix: np.ndarray, tolerance: float) -> tuple[np.ndarray, int, float]:
    try:
        singular_values = np.linalg.svd(matrix, compute_uv=False)
    except np.linalg.LinAlgError as error:
        raise CalculatorError("E_DOMAIN", f"singular-value analysis failed: {error}") from error
    _require_finite_array(singular_values, "singular values")
    maximum = float(singular_values[0]) if len(singular_values) else 0.0
    threshold = tolerance * maximum
    rank = int(np.count_nonzero(singular_values > threshold))
    minimum = float(singular_values[-1]) if len(singular_values) else 0.0
    condition = float("inf") if rank < min(matrix.shape) or minimum == 0 else maximum / minimum
    return singular_values, rank, condition


def _numeric_base(
    action: str,
    matrix: np.ndarray,
    tolerance: str,
    precision: int,
    rank: int,
    condition: float,
    singular_values: np.ndarray,
    warnings: list[str],
    **results: Any,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "operation": "linear_algebra.numeric",
        "kind": "numeric_linear_algebra",
        "action": action,
        "inputShape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "rank": rank,
        "conditionNumber": _diagnostic_text(condition, precision),
        "singularValues": _vector_text(singular_values, precision),
        "tolerance": tolerance,
        "precision": precision,
        "numericFormat": "binary64",
        **results,
        "warnings": list(warnings),
    }


def _matrix_text(matrix: np.ndarray, precision: int) -> list[list[str]]:
    return [[_value_text(value, precision) for value in row] for row in matrix]


def _vector_text(vector: np.ndarray, precision: int) -> list[str]:
    return [_value_text(value, precision) for value in vector]


def _value_text(value: float, precision: int) -> str:
    if value == 0:
        return "0"
    return format(float(value), f".{precision}g")


def _diagnostic_text(value: float, precision: int) -> str:
    return "inf" if not np.isfinite(value) else _value_text(value, precision)


def _require_finite_array(value: np.ndarray, label: str) -> None:
    require(bool(np.all(np.isfinite(value))), "E_DOMAIN", f"{label} overflowed binary64")


def _require_finite_diagnostic(value: float, label: str) -> None:
    require(np.isfinite(value), "E_DOMAIN", f"{label} overflowed binary64")
