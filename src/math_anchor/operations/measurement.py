from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import value_result
from ..safe_expression import make_symbols, parse_expression
from ..validation import integer_arg, string_arg


def propagate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression", max_length=4096)
    raw_inputs = arguments.get("inputs")
    require(isinstance(raw_inputs, dict), "E_INPUT", "inputs must be an object")
    require(1 <= len(raw_inputs) <= 16, "E_LIMIT", "inputs must contain 1 to 16 variables")
    variable_order = sorted(raw_inputs)
    symbols = make_symbols(variable_order)
    expression = parse_expression(expression_text, symbols=symbols)
    require(
        expression.free_symbols == set(symbols.values()),
        "E_INPUT",
        "expression must use every declared input and no undeclared variables",
    )
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)
    coverage_factor = _decimal_rational(arguments.get("coverageFactor", "2"), "coverageFactor")
    require(coverage_factor > 0, "E_DOMAIN", "coverageFactor must be positive")

    values: dict[str, sp.Rational] = {}
    uncertainties: dict[str, sp.Rational] = {}
    for name in variable_order:
        raw = raw_inputs[name]
        require(isinstance(raw, dict), "E_INPUT", f"inputs.{name} must be an object")
        values[name] = _decimal_rational(raw.get("value"), f"inputs.{name}.value")
        uncertainty = _decimal_rational(
            raw.get("standardUncertainty"),
            f"inputs.{name}.standardUncertainty",
        )
        require(uncertainty >= 0, "E_DOMAIN", "standard uncertainties must be nonnegative")
        uncertainties[name] = uncertainty

    correlation_matrix = sp.eye(len(variable_order))
    correlations = arguments.get("correlations", [])
    require(isinstance(correlations, list), "E_INPUT", "correlations must be an array")
    require(len(correlations) <= 120, "E_LIMIT", "correlations may contain at most 120 pairs")
    index_by_name = {name: index for index, name in enumerate(variable_order)}
    seen_pairs: set[tuple[str, str]] = set()
    for index, correlation in enumerate(correlations):
        require(isinstance(correlation, dict), "E_INPUT", f"correlations[{index}] must be an object")
        left = correlation.get("left")
        right = correlation.get("right")
        require(isinstance(left, str) and left in index_by_name, "E_INPUT", f"correlations[{index}].left is unknown")
        require(isinstance(right, str) and right in index_by_name, "E_INPUT", f"correlations[{index}].right is unknown")
        require(left != right, "E_INPUT", "correlation pairs must name two different variables")
        pair = tuple(sorted((left, right)))
        require(pair not in seen_pairs, "E_INPUT", "each correlation pair may be supplied only once")
        seen_pairs.add(pair)
        coefficient = _decimal_rational(correlation.get("coefficient"), f"correlations[{index}].coefficient")
        require(-1 <= coefficient <= 1, "E_DOMAIN", "correlation coefficients must be between -1 and 1")
        left_index = index_by_name[left]
        right_index = index_by_name[right]
        correlation_matrix[left_index, right_index] = coefficient
        correlation_matrix[right_index, left_index] = coefficient

    require(
        correlation_matrix.is_positive_semidefinite is True,
        "E_DOMAIN",
        "the supplied correlations do not form a positive-semidefinite matrix",
    )

    substitutions = {symbols[name]: values[name] for name in variable_order}
    nominal = sp.simplify(expression.subs(substitutions))
    require(nominal.is_number and nominal.is_finite is True, "E_DOMAIN", "nominal result is not finite")
    sensitivities = [
        sp.simplify(sp.diff(expression, symbols[name]).subs(substitutions))
        for name in variable_order
    ]
    require(
        all(value.is_number and value.is_finite is True for value in sensitivities),
        "E_DOMAIN",
        "a sensitivity coefficient is not finite at the supplied values",
    )

    covariance_matrix = sp.zeros(len(variable_order))
    for row, row_name in enumerate(variable_order):
        for column, column_name in enumerate(variable_order):
            covariance_matrix[row, column] = sp.simplify(
                correlation_matrix[row, column]
                * uncertainties[row_name]
                * uncertainties[column_name]
            )
    sensitivity_vector = sp.Matrix(sensitivities)
    variance = sp.simplify((sensitivity_vector.T * covariance_matrix * sensitivity_vector)[0])
    require(variance.is_nonnegative is True, "E_DOMAIN", "combined variance is not nonnegative")
    combined_uncertainty = sp.sqrt(variance)
    expanded_uncertainty = sp.simplify(coverage_factor * combined_uncertainty)
    linear_model = all(
        sp.diff(expression, left, right) == 0
        for left in symbols.values()
        for right in symbols.values()
    )

    warnings = [
        "Inputs must already use one coherent numerical unit system; this operation does not infer or convert units.",
        "Exact fields are exact within the stated first-order covariance model, not proof that higher-order uncertainty is zero.",
    ]
    if not linear_model:
        warnings.append("The model is nonlinear; first-order Taylor propagation may omit material higher-order effects.")

    return {
        "status": "ok",
        "operation": "measurement.propagate",
        "kind": "uncertainty_propagation",
        "expression": expression_text,
        "variableOrder": variable_order,
        "nominal": value_result(nominal, precision),
        "combinedStandardUncertainty": value_result(combined_uncertainty, precision),
        "expandedUncertainty": value_result(expanded_uncertainty, precision),
        "coverageFactor": sp.sstr(coverage_factor),
        "sensitivityCoefficients": [
            {"variable": name, "value": value_result(value, precision)}
            for name, value in zip(variable_order, sensitivities, strict=True)
        ],
        "covarianceMatrix": [
            [sp.sstr(covariance_matrix[row, column]) for column in range(covariance_matrix.cols)]
            for row in range(covariance_matrix.rows)
        ],
        "correlationsApplied": len(correlations),
        "linearModel": linear_model,
        "method": "first_order_taylor_covariance",
        "coordinateSystem": "coherent_input_units",
        "precision": precision,
        "warnings": warnings,
    }


def _decimal_rational(value: Any, label: str) -> sp.Rational:
    require(isinstance(value, str), "E_INPUT", f"{label} must be decimal text")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{label} must be decimal text") from error
    require(decimal.is_finite(), "E_DOMAIN", f"{label} must be finite")
    numerator, denominator = decimal.as_integer_ratio()
    return sp.Rational(numerator, denominator)
