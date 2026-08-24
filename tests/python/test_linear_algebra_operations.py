from __future__ import annotations

import math

import pytest

from math_anchor.catalog import search_operations
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_exact_matrix_algebra_preserves_symbolic_results() -> None:
    product = execute_direct(
        "linear_algebra.exact",
        {
            "action": "matrix_multiply",
            "left": [[1, 2], [3, 4]],
            "right": [[2], [1]],
        },
    )
    assert product["exact"] == [["4"], ["10"]]
    assert product["shape"] == [2, 1]

    transposed = execute_direct(
        "linear_algebra.exact",
        {"action": "transpose", "matrix": [[1, 2, 3], [4, 5, 6]]},
    )
    assert transposed["exact"] == [["1", "4"], ["2", "5"], ["3", "6"]]
    assert search_operations("矩阵乘法")["operations"][0]["id"] == "linear_algebra.exact"


def test_exact_vector_algebra_covers_products_norms_and_projection() -> None:
    dot = execute_direct(
        "linear_algebra.exact",
        {"action": "dot", "left": ["1/2", 2], "right": [4, "3/2"]},
    )
    assert dot["result"]["exact"] == "5"

    cross = execute_direct(
        "linear_algebra.exact",
        {"action": "cross", "left": [1, 0, 0], "right": [0, 1, 0]},
    )
    assert [value["exact"] for value in cross["result"]] == ["0", "0", "1"]

    norm = execute_direct(
        "linear_algebra.exact",
        {"action": "norm", "vector": [1, 1]},
    )
    assert norm["result"]["exact"] == "sqrt(2)"

    norm_squared = execute_direct(
        "linear_algebra.exact",
        {"action": "norm_squared", "vector": [3, 4]},
    )
    assert norm_squared["result"]["exact"] == "25"

    projection = execute_direct(
        "linear_algebra.exact",
        {"action": "projection", "left": [2, 2], "onto": [1, 0]},
    )
    assert [value["exact"] for value in projection["result"]] == ["2", "0"]


def test_numeric_least_squares_reports_rank_residual_and_binary64_provenance() -> None:
    result = execute_direct(
        "linear_algebra.numeric",
        {
            "action": "least_squares",
            "matrix": [["1", "0"], ["1", "1"], ["1", "2"]],
            "constants": ["1", "2", "2"],
        },
    )
    assert result["classification"] == "full_rank"
    assert result["solutionUnique"] is True
    assert result["solutionConvention"] == "unique_least_squares_minimizer"
    assert result["rank"] == 2
    assert result["numericFormat"] == "binary64"
    assert result["solution"][0].startswith("1.1666666666")
    assert result["solution"][1] == "0.5"
    assert math.isclose(float(result["residualNorm"]), math.sqrt(1 / 6), rel_tol=1e-12)
    assert "approximate" in result["warnings"][0]

    underdetermined = execute_direct(
        "linear_algebra.numeric",
        {
            "action": "least_squares",
            "matrix": [["1", "0"]],
            "constants": ["1"],
        },
    )
    assert underdetermined["classification"] == "full_rank"
    assert underdetermined["solutionUnique"] is False
    assert underdetermined["solutionConvention"] == "minimum_euclidean_norm"
    assert underdetermined["solution"] == ["1", "0"]
    assert "not unique" in underdetermined["warnings"][-1]


def test_qr_svd_and_pseudoinverse_return_diagnostics() -> None:
    qr = execute_direct(
        "linear_algebra.numeric",
        {"action": "qr", "matrix": [["1", "2"], ["3", "4"], ["5", "6"]]},
    )
    assert qr["mode"] == "reduced"
    assert len(qr["q"]) == 3 and len(qr["q"][0]) == 2
    assert float(qr["reconstructionError"]) < 1e-12
    assert float(qr["orthogonalityError"]) < 1e-12

    svd = execute_direct(
        "linear_algebra.numeric",
        {"action": "svd", "matrix": [["3", "0"], ["0", "2"]]},
    )
    assert svd["singularValues"] == ["3", "2"]
    assert svd["rank"] == 2
    assert svd["conditionNumber"] == "1.5"
    assert svd["reconstructionError"] == "0"

    pseudoinverse = execute_direct(
        "linear_algebra.numeric",
        {"action": "pseudoinverse", "matrix": [["2", "0"], ["0", "0"]]},
    )
    assert pseudoinverse["pseudoinverse"] == [["0.5", "0"], ["0", "0"]]
    assert pseudoinverse["rank"] == 1
    assert pseudoinverse["conditionNumber"] == "inf"
    assert set(pseudoinverse["penroseResiduals"].values()) == {"0"}
    assert "rank-deficient" in pseudoinverse["warnings"][1]


@pytest.mark.parametrize(
    ("operation", "arguments", "code"),
    [
        (
            "linear_algebra.exact",
            {"action": "dot", "left": [1, 2], "right": [1]},
            "E_INPUT",
        ),
        (
            "linear_algebra.exact",
            {"action": "cross", "left": [1, 2], "right": [3, 4]},
            "E_INPUT",
        ),
        (
            "linear_algebra.exact",
            {"action": "projection", "left": [1, 2], "onto": [0, 0]},
            "E_DOMAIN",
        ),
        (
            "linear_algebra.exact",
            {"action": "norm", "vector": [0.1, 2]},
            "E_INPUT",
        ),
        (
            "linear_algebra.exact",
            {"action": "norm", "vector": ["I"]},
            "E_INPUT",
        ),
        (
            "linear_algebra.numeric",
            {"action": "svd", "matrix": [[1, "0"], ["0", "1"]]},
            "E_INPUT",
        ),
        (
            "linear_algebra.numeric",
            {"action": "svd", "matrix": [["1"], ["1", "2"]]},
            "E_INPUT",
        ),
        (
            "linear_algebra.numeric",
            {"action": "svd", "matrix": [["1"]], "tolerance": "0"},
            "E_INPUT",
        ),
        (
            "linear_algebra.numeric",
            {"action": "svd", "matrix": [["1"]], "extra": True},
            "E_INPUT",
        ),
    ],
)
def test_linear_algebra_rejects_ambiguous_or_invalid_inputs(
    operation: str,
    arguments: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(operation, arguments)
    assert raised.value.code == code
