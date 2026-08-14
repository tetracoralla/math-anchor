from __future__ import annotations

import pytest

from zibetha.catalog import OPERATIONS, search_operations
from zibetha.errors import CalculatorError
from zibetha.runtime import execute_direct


def test_catalog_contains_the_explicit_standard_operation_set() -> None:
    assert len(OPERATIONS) == 29
    assert {
        "expression.equivalent",
        "solution.verify",
        "quantity.evaluate",
        "finance.calculate",
        "matrix.solve_approximate",
        "probability.distribution",
        "statistics.infer",
        "numeric.integrate",
    } <= set(OPERATIONS)
    assert search_operations("因式分解")["operations"][0]["id"] == "algebra.transform"
    assert search_operations("质因数分解")["operations"][0]["id"] == "integer.factorization"
    assert search_operations("线性方程组")["operations"][0]["id"] == "matrix.solve"
    assert search_operations("泰勒展开")["operations"][0]["id"] == "calculus.series"


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


def test_statistics_contract_now_returns_the_advertised_range() -> None:
    described = execute_direct("statistics.describe", {"values": [1, 2, 5, 9]})
    assert described["range"]["exact"] == "8"

    with pytest.raises(CalculatorError) as overflow:
        execute_direct("statistics.describe", {"values": [1e308, -1e308]})
    assert overflow.value.code == "E_DOMAIN"
