from __future__ import annotations

from decimal import Decimal

import pytest

from math_anchor.catalog import search_operations
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_beta_gamma_and_lognormal_distributions_cover_density_cdf_and_quantile() -> None:
    beta_pdf = execute_direct(
        "probability.distribution",
        {"distribution": "beta", "function": "pdf", "x": "0.5", "alpha": "2", "beta": "2"},
    )
    assert beta_pdf["value"]["approx"] == "1.5"

    beta_quantile = execute_direct(
        "probability.distribution",
        {"distribution": "beta", "function": "quantile", "probability": "0.5", "alpha": "2", "beta": "2"},
    )
    assert Decimal(beta_quantile["value"]["approx"]) == Decimal("0.5")

    gamma_cdf = execute_direct(
        "probability.distribution",
        {"distribution": "gamma", "function": "cdf", "x": "2", "shape": "2", "scale": "1"},
    )
    assert gamma_cdf["value"]["approx"].startswith("0.593994150290")

    gamma_quantile = execute_direct(
        "probability.distribution",
        {"distribution": "gamma", "function": "quantile", "probability": "0.5", "shape": "2"},
    )
    assert gamma_quantile["value"]["approx"].startswith("1.678346990016")

    lognormal = execute_direct(
        "probability.distribution",
        {"distribution": "lognormal", "function": "quantile", "probability": "0.5"},
    )
    assert lognormal["value"]["approx"] == "1.0"


@pytest.mark.parametrize(
    "arguments",
    [
        {"distribution": "beta", "function": "pdf", "x": "0", "alpha": "0.5", "beta": "2"},
        {"distribution": "beta", "function": "pdf", "x": "1", "alpha": "2", "beta": "0.5"},
        {"distribution": "gamma", "function": "pdf", "x": "0", "shape": "0.5", "scale": "1"},
    ],
)
def test_valid_infinite_density_boundaries_do_not_become_runtime_failures(
    arguments: dict[str, str],
) -> None:
    result = execute_direct("probability.distribution", arguments)
    assert result["status"] == "ok"
    assert result["value"] == {"exact": "oo", "approx": "Infinity"}
    assert "singularity" in result["warnings"][0]


def test_paired_two_sample_and_chi_square_inference_are_explicit() -> None:
    paired = execute_direct(
        "statistics.infer",
        {
            "action": "paired_t_test",
            "sampleA": ["10", "12", "9", "11", "13"],
            "sampleB": ["8", "11", "8", "9", "10"],
        },
    )
    assert paired["method"] == "paired_student_t_test"
    assert paired["test"]["degreesOfFreedom"] == 4
    assert paired["test"]["pValue"]["approx"].startswith("0.0085809187")

    welch = execute_direct(
        "statistics.infer",
        {
            "action": "two_sample_t_test",
            "sampleA": ["10", "12", "9", "11", "13"],
            "sampleB": ["7", "8", "9", "8", "10"],
        },
    )
    assert welch["method"] == "welch_two_sample_t_test"
    assert isinstance(welch["test"]["degreesOfFreedom"], str)
    assert welch["test"]["pValue"]["approx"].startswith("0.0195498343")

    chi_square = execute_direct(
        "statistics.infer",
        {
            "action": "chi_square_goodness_of_fit",
            "observed": [20, 30, 50],
            "expectedProbabilities": ["0.25", "0.25", "0.5"],
        },
    )
    assert chi_square["test"]["statistic"]["approx"] == "2.0"
    assert chi_square["test"]["degreesOfFreedom"] == 2
    assert chi_square["test"]["pValue"]["approx"].startswith("0.36787944117")


def test_first_order_uncertainty_propagation_separates_standard_and_expanded_values() -> None:
    independent = execute_direct(
        "measurement.propagate",
        {
            "expression": "x + y",
            "inputs": {
                "x": {"value": "10", "standardUncertainty": "0.5"},
                "y": {"value": "20", "standardUncertainty": "1"},
            },
        },
    )
    assert independent["nominal"]["exact"] == "30"
    assert independent["combinedStandardUncertainty"]["exact"] == "sqrt(5)/2"
    assert independent["expandedUncertainty"]["exact"] == "sqrt(5)"
    assert independent["coverageFactor"] == "2"
    assert independent["linearModel"] is True
    assert independent["coordinateSystem"] == "coherent_input_units"

    correlated = execute_direct(
        "measurement.propagate",
        {
            "expression": "x * y",
            "inputs": {
                "x": {"value": "2", "standardUncertainty": "0.1"},
                "y": {"value": "3", "standardUncertainty": "0.2"},
            },
            "correlations": [{"left": "x", "right": "y", "coefficient": "0.5"}],
        },
    )
    assert correlated["combinedStandardUncertainty"]["exact"] == "sqrt(37)/10"
    assert correlated["expandedUncertainty"]["exact"] == "sqrt(37)/5"
    assert correlated["covarianceMatrix"] == [["1/100", "1/100"], ["1/100", "1/25"]]
    assert correlated["linearModel"] is False
    assert "higher-order" in correlated["warnings"][-1]
    assert search_operations("不确定度传播")["operations"][0]["id"] == "measurement.propagate"


@pytest.mark.parametrize(
    ("operation", "arguments", "code"),
    [
        (
            "probability.distribution",
            {"distribution": "beta", "function": "cdf", "x": "0.5", "probability": "0.5", "alpha": "2", "beta": "2"},
            "E_INPUT",
        ),
        (
            "probability.distribution",
            {"distribution": "gamma", "function": "cdf", "x": "1", "shape": "0"},
            "E_DOMAIN",
        ),
        (
            "statistics.infer",
            {"action": "paired_t_test", "sampleA": ["1", "2"], "sampleB": ["1", "2", "3"]},
            "E_INPUT",
        ),
        (
            "statistics.infer",
            {"action": "chi_square_goodness_of_fit", "observed": [1, 2], "expectedProbabilities": ["0.4", "0.5"]},
            "E_DOMAIN",
        ),
        (
            "measurement.propagate",
            {
                "expression": "x + y + z",
                "inputs": {
                    "x": {"value": "1", "standardUncertainty": "1"},
                    "y": {"value": "1", "standardUncertainty": "1"},
                    "z": {"value": "1", "standardUncertainty": "1"},
                },
                "correlations": [
                    {"left": "x", "right": "y", "coefficient": "1"},
                    {"left": "x", "right": "z", "coefficient": "1"},
                    {"left": "y", "right": "z", "coefficient": "-1"},
                ],
            },
            "E_DOMAIN",
        ),
        (
            "measurement.propagate",
            {
                "expression": "x",
                "inputs": {"x": {"value": "1", "standardUncertainty": "-0.1"}},
            },
            "E_DOMAIN",
        ),
        (
            "measurement.propagate",
            {
                "expression": "x",
                "inputs": {"x": {"value": "1", "standardUncertainty": "0.1"}},
                "coverageFactor": "0",
            },
            "E_DOMAIN",
        ),
        (
            "measurement.propagate",
            {
                "expression": "x",
                "inputs": {
                    "x": {"value": "1", "standardUncertainty": "0.1"},
                    "unused": {"value": "2", "standardUncertainty": "0.1"},
                },
            },
            "E_INPUT",
        ),
    ],
)
def test_probability_inference_and_uncertainty_reject_invalid_semantics(
    operation: str,
    arguments: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(operation, arguments)
    assert raised.value.code == code
