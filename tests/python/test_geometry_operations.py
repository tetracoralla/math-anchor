from __future__ import annotations

import pytest

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_constant_six_dimensional_candidate_satisfies_both_local_conditions() -> None:
    result = execute_direct(
        "geometry.almost_complex.local_check",
        {
            "coordinates": ["x0", "x1", "x2", "x3", "x4", "x5"],
            "structure": [
                ["0", "-1", "0", "0", "0", "0"],
                ["1", "0", "0", "0", "0", "0"],
                ["0", "0", "0", "-1", "0", "0"],
                ["0", "0", "1", "0", "0", "0"],
                ["0", "0", "0", "0", "0", "-1"],
                ["0", "0", "0", "0", "1", "0"],
            ],
        },
    )

    assert result["square"] == {
        "satisfied": True,
        "nonzeroComponentCount": 0,
        "firstNonzero": None,
    }
    assert result["nijenhuis"] == {
        "vanished": True,
        "independentComponentsChecked": 90,
        "nonzeroComponentCount": 0,
        "firstNonzero": None,
    }
    assert result["localConclusion"] == "integrability_conditions_satisfied_on_supplied_chart"
    assert result["matrixConvention"] == "row_output_column_input"
    assert result["nijenhuisConvention"] == "standard_unscaled_bracket"
    assert result["scope"] == "local_coordinate_rational_polynomial_almost_complex_check"
    assert result["certificate"] is None
    assert result["checkedBy"] is None
    assert "global_smooth_extension" in result["uncheckedGlobalObligations"]


def test_polynomial_almost_complex_candidate_reports_exact_nijenhuis_witness() -> None:
    # This J is P J0 P^-1 for P = I + x0 E_02, so J^2 = -I exactly.
    # Direct coordinate-basis expansion gives N^x0_(x0,x2) = -1.
    result = execute_direct(
        "geometry.almost_complex.local_check",
        {
            "coordinates": ["x0", "x1", "x2", "x3"],
            "structure": [
                ["0", "-1", "0", "-x0"],
                ["1", "0", "-x0", "0"],
                ["0", "0", "0", "-1"],
                ["0", "0", "1", "0"],
            ],
        },
    )

    assert result["square"]["satisfied"] is True
    assert result["nijenhuis"]["vanished"] is False
    assert result["nijenhuis"]["nonzeroComponentCount"] == 5
    assert result["nijenhuis"]["firstNonzero"] == {
        "output": "x0",
        "left": "x0",
        "right": "x2",
        "exact": "-1",
    }
    assert result["localConclusion"] == "almost_complex_nonintegrable_on_supplied_chart"


def test_non_almost_complex_candidate_reports_first_square_counterexample() -> None:
    result = execute_direct(
        "geometry.almost_complex.local_check",
        {
            "coordinates": ["x", "y"],
            "structure": [["1", "0"], ["0", "1"]],
        },
    )

    assert result["square"] == {
        "satisfied": False,
        "nonzeroComponentCount": 2,
        "firstNonzero": {"row": "x", "column": "x", "exact": "2"},
    }
    assert result["localConclusion"] == "not_almost_complex"


@pytest.mark.parametrize(
    ("coordinates", "structure", "code"),
    [
        (["x", "y"], [["sin(x)", "-1"], ["1", "0"]], "E_DOMAIN"),
        (["x", "y"], [["0.5", "-1"], ["1", "0"]], "E_DOMAIN"),
        (["x", "y"], [["1/x", "-1"], ["1", "0"]], "E_DOMAIN"),
        (["x", "y", "z"], [["0", "0", "0"]] * 3, "E_DOMAIN"),
        (["x", "y", "z", "w"], [["0", "0"]] * 4, "E_INPUT"),
    ],
)
def test_local_check_rejects_inputs_outside_its_declared_exact_domain(
    coordinates: list[str],
    structure: list[list[str]],
    code: str,
) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "geometry.almost_complex.local_check",
            {"coordinates": coordinates, "structure": structure},
        )

    assert raised.value.code == code


def test_local_check_bounds_polynomial_expansion_before_symbolic_work() -> None:
    monomials = [
        f"x^{x_power}*y^{y_power}"
        for total in range(9)
        for x_power in range(total + 1)
        for y_power in [total - x_power]
    ][:33]
    oversized = "+".join(monomials)

    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "geometry.almost_complex.local_check",
            {
                "coordinates": ["x", "y"],
                "structure": [[oversized, "-1"], ["1", "0"]],
            },
        )

    assert raised.value.code == "E_LIMIT"
