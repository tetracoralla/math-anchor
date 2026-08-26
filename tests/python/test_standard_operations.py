from __future__ import annotations

import pytest

from math_anchor.catalog import OPERATIONS, search_operations
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_catalog_contains_the_explicit_standard_operation_set() -> None:
    assert len(OPERATIONS) == 44
    assert {
        "expression.equivalent",
        "solution.verify",
        "quantity.evaluate",
        "dimension.check",
        "dimension.infer",
        "dimension.pi_groups",
        "finance.calculate",
        "matrix.solve_approximate",
        "probability.distribution",
        "statistics.infer",
        "numeric.integrate",
        "numeric.minimize",
        "function.sample",
        "integer.represent",
        "integer.bitwise",
        "integer.machine_arithmetic",
        "float.ieee754",
        "decimal.quantize",
        "integer.divide",
        "units.search",
        "linear_algebra.exact",
        "linear_algebra.numeric",
        "measurement.propagate",
    } <= set(OPERATIONS)
    assert search_operations("因式分解")["operations"][0]["id"] == "algebra.transform"
    assert search_operations("质因数分解")["operations"][0]["id"] == "integer.factorization"
    assert search_operations("线性方程组")["operations"][0]["id"] == "matrix.solve"
    assert search_operations("泰勒展开")["operations"][0]["id"] == "calculus.series"
    assert search_operations("旋度")["operations"][0]["id"] == "calculus.multivariate"
    assert search_operations("特征空间")["operations"][0]["id"] == "matrix.reduce"
    assert search_operations("Airy special function")["operations"][0]["id"] == "expression.evaluate"


def test_algebra_transform_has_explicit_semantics() -> None:
    factored = execute_direct(
        "algebra.transform",
        {"action": "factor", "expression": "x^2 - 1", "variables": ["x"]},
    )
    assert factored["kind"] == "transformation"
    assert factored["action"] == "factor"
    assert factored["exact"] == "(x - 1)*(x + 1)"

    expanded = execute_direct(
        "algebra.transform",
        {"action": "expand", "expression": "(x + 1)^3", "variables": ["x"]},
    )
    assert expanded["exact"] == "x**3 + 3*x**2 + 3*x + 1"

    partial = execute_direct(
        "algebra.transform",
        {"action": "apart", "expression": "1/(x*(x+1))", "variable": "x"},
    )
    assert partial["exact"] == "-1/(x + 1) + 1/x"


def test_integer_number_theory_is_exact_and_bounded() -> None:
    factorization = execute_direct("integer.factorization", {"value": -360})
    assert factorization["sign"] == -1
    assert factorization["isPrime"] is False
    assert factorization["factors"] == [
        {"prime": "2", "exponent": 3},
        {"prime": "3", "exponent": 2},
        {"prime": "5", "exponent": 1},
    ]

    pair = execute_direct("integer.gcd_lcm", {"values": [12, "18", 30]})
    assert pair["gcd"] == "6"
    assert pair["lcm"] == "180"

    power = execute_direct(
        "integer.modular",
        {"action": "power", "value": 7, "exponent": 128, "modulus": 13},
    )
    assert power["exact"] == str(pow(7, 128, 13))
    inverse = execute_direct(
        "integer.modular",
        {"action": "inverse", "value": 3, "modulus": 11},
    )
    assert inverse["exact"] == "4"

    with pytest.raises(CalculatorError) as zero:
        execute_direct("integer.factorization", {"value": 0})
    assert zero.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as noninvertible:
        execute_direct("integer.modular", {"action": "inverse", "value": 6, "modulus": 9})
    assert noninvertible.value.code == "E_DOMAIN"


def test_combinatorics_uses_explicit_counting_conventions() -> None:
    binomial = execute_direct("combinatorics.count", {"action": "binomial", "n": 52, "k": 5})
    assert binomial["exact"] == "2598960"
    assert binomial["action"] == "binomial"

    permutations = execute_direct("combinatorics.count", {"action": "permutations", "n": 5, "k": 3})
    assert permutations["exact"] == "60"

    multinomial = execute_direct("combinatorics.count", {"action": "multinomial", "counts": [2, 3, 1]})
    assert multinomial["exact"] == "60"

    with pytest.raises(CalculatorError) as invalid:
        execute_direct("combinatorics.count", {"action": "binomial", "n": 3, "k": 4})
    assert invalid.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as oversized:
        execute_direct("combinatorics.count", {"action": "binomial", "n": 5_001, "k": 1})
    assert oversized.value.code == "E_LIMIT"
    assert oversized.value.details == {"path": ["n"], "rule": "maximum"}


def test_matrix_solve_classifies_all_solution_states() -> None:
    unique = execute_direct(
        "matrix.solve",
        {"matrix": [[1, 1], [1, -1]], "constants": [7, 1], "variables": ["x", "y"]},
    )
    assert unique["classification"] == "unique"
    assert [value["exact"] for value in unique["particular"]] == ["4", "3"]
    assert unique["nullspace"] == []

    infinite = execute_direct(
        "matrix.solve",
        {"matrix": [[1, 2], [2, 4]], "constants": [3, 6]},
    )
    assert infinite["classification"] == "infinite"
    assert [value["exact"] for value in infinite["particular"]] == ["3", "0"]
    assert [[value["exact"] for value in vector] for vector in infinite["nullspace"]] == [["-2", "1"]]

    inconsistent = execute_direct(
        "matrix.solve",
        {"matrix": [[1, 2], [2, 4]], "constants": [3, 7]},
    )
    assert inconsistent["classification"] == "inconsistent"
    assert inconsistent["particular"] is None


def test_matrix_reduction_is_exact_and_rejects_implicit_float_tolerance() -> None:
    reduced = execute_direct(
        "matrix.reduce",
        {"action": "rref", "matrix": [[1, 2, 3], [2, 4, 6]]},
    )
    assert reduced["exact"] == [["1", "2", "3"], ["0", "0", "0"]]
    assert reduced["pivots"] == [0]

    nullspace = execute_direct(
        "matrix.reduce",
        {"action": "nullspace", "matrix": [[1, 2], [2, 4]]},
    )
    assert nullspace["dimension"] == 1
    assert [[value["exact"] for value in vector] for vector in nullspace["basis"]] == [["-2", "1"]]

    with pytest.raises(CalculatorError) as approximate:
        execute_direct("matrix.reduce", {"action": "rank", "matrix": [[0.1, 0.2], [0.2, 0.4]]})
    assert approximate.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as decimal_text:
        execute_direct("matrix.reduce", {"action": "rank", "matrix": [["0.1", "0.2"]]})
    assert decimal_text.value.code == "E_INPUT"


def test_exact_eigenspaces_report_multiplicity_and_diagonalizability() -> None:
    diagonal = execute_direct(
        "matrix.reduce",
        {"action": "eigenspaces", "matrix": [[2, 0], [0, 3]]},
    )
    assert diagonal["kind"] == "exact_eigenspaces"
    assert diagonal["diagonalizable"] is True
    assert [space["eigenvalue"]["exact"] for space in diagonal["eigenspaces"]] == ["2", "3"]
    assert [space["algebraicMultiplicity"] for space in diagonal["eigenspaces"]] == [1, 1]
    assert [space["geometricMultiplicity"] for space in diagonal["eigenspaces"]] == [1, 1]

    defective = execute_direct(
        "matrix.reduce",
        {"action": "eigenspaces", "matrix": [[2, 1], [0, 2]]},
    )
    assert defective["diagonalizable"] is False
    assert defective["eigenspaces"][0]["algebraicMultiplicity"] == 2
    assert defective["eigenspaces"][0]["geometricMultiplicity"] == 1
    assert defective["warnings"]

    with pytest.raises(CalculatorError) as nonsquare:
        execute_direct("matrix.reduce", {"action": "eigenspaces", "matrix": [[1, 2, 3]]})
    assert nonsquare.value.code == "E_INPUT"


def test_exact_lu_and_cholesky_return_explicit_factor_relations() -> None:
    lu = execute_direct(
        "matrix.reduce",
        {"action": "lu", "matrix": [[0, 1], [2, 3]]},
    )
    assert lu["kind"] == "exact_matrix_decomposition"
    assert lu["relation"] == "P*A = L*U"
    assert lu["pivotSwaps"] == [[0, 1]]
    assert lu["permutation"]["exact"] == [["0", "1"], ["1", "0"]]
    assert lu["factors"][0]["name"] == "L"
    assert lu["factors"][1]["exact"] == [["2", "3"], ["0", "1"]]

    cholesky = execute_direct(
        "matrix.reduce",
        {"action": "cholesky", "matrix": [[4, 2], [2, 3]]},
    )
    assert cholesky["relation"] == "A = L*L.H"
    assert cholesky["factors"][0]["exact"] == [["2", "0"], ["1", "sqrt(2)"]]
    assert cholesky["permutation"] is None

    with pytest.raises(CalculatorError) as nonsymmetric:
        execute_direct("matrix.reduce", {"action": "cholesky", "matrix": [[1, 2], [0, 1]]})
    assert nonsymmetric.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as indefinite:
        execute_direct("matrix.reduce", {"action": "cholesky", "matrix": [[1, 2], [2, 1]]})
    assert indefinite.value.code == "E_DOMAIN"


def test_series_and_multivariate_derivatives_preserve_symbolic_results() -> None:
    series = execute_direct(
        "calculus.series",
        {"expression": "exp(x)", "variable": "x", "point": 0, "order": 4},
    )
    assert series["exact"] == "1 + x + x**2/2 + x**3/6 + O(x**4)"
    assert series["order"] == 4

    gradient = execute_direct(
        "calculus.multivariate",
        {"action": "gradient", "expression": "x^2 + x*y + y^2", "variables": ["x", "y"]},
    )
    assert gradient["exact"] == [["2*x + y"], ["x + 2*y"]]

    jacobian = execute_direct(
        "calculus.multivariate",
        {"action": "jacobian", "expressions": ["x*y", "x+y"], "variables": ["x", "y"]},
    )
    assert jacobian["exact"] == [["y", "x"], ["1", "1"]]

    hessian = execute_direct(
        "calculus.multivariate",
        {"action": "hessian", "expression": "x^2 + x*y + y^2", "variables": ["x", "y"]},
    )
    assert hessian["exact"] == [["2", "1"], ["1", "2"]]

    directional = execute_direct(
        "calculus.multivariate",
        {
            "action": "directional_derivative",
            "expression": "x^2 + y^2",
            "variables": ["x", "y"],
            "direction": [3, 4],
        },
    )
    assert directional["exact"] == [["6*x + 8*y"]]

    divergence = execute_direct(
        "calculus.multivariate",
        {
            "action": "divergence",
            "expressions": ["x^2", "x*y", "z^2"],
            "variables": ["x", "y", "z"],
        },
    )
    assert divergence["exact"] == [["3*x + 2*z"]]

    curl = execute_direct(
        "calculus.multivariate",
        {
            "action": "curl",
            "expressions": ["y*z", "x*z", "x*y"],
            "variables": ["x", "y", "z"],
        },
    )
    assert curl["exact"] == [["0"], ["0"], ["0"]]

    laplacian = execute_direct(
        "calculus.multivariate",
        {"action": "laplacian", "expression": "x^2 + y^2 + z^2", "variables": ["x", "y", "z"]},
    )
    assert laplacian["exact"] == [["6"]]


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        (
            {
                "action": "directional_derivative",
                "expression": "x^2 + y^2",
                "variables": ["x", "y"],
                "direction": [1],
            },
            "E_INPUT",
        ),
        (
            {
                "action": "directional_derivative",
                "expression": "x^2 + y^2",
                "variables": ["x", "y"],
                "direction": [0, 0],
            },
            "E_DOMAIN",
        ),
        (
            {
                "action": "directional_derivative",
                "expression": "x^2 + y^2",
                "variables": ["x", "y"],
                "direction": [0.5, 1],
            },
            "E_INPUT",
        ),
        (
            {"action": "divergence", "expressions": ["x", "y"], "variables": ["x", "y", "z"]},
            "E_INPUT",
        ),
        (
            {"action": "curl", "expressions": ["y", "x"], "variables": ["x", "y"]},
            "E_INPUT",
        ),
    ],
)
def test_multivariate_vector_calculus_rejects_ambiguous_shapes(
    arguments: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct("calculus.multivariate", arguments)
    assert raised.value.code == code


def test_statistics_contract_now_returns_the_advertised_range() -> None:
    described = execute_direct("statistics.describe", {"values": [1, 2, 5, 9]})
    assert described["range"]["exact"] == "8"

    with pytest.raises(CalculatorError) as overflow:
        execute_direct("statistics.describe", {"values": [1e308, -1e308]})
    assert overflow.value.code == "E_DOMAIN"
