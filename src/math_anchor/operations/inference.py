from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import mpmath as mp

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, list_arg, string_arg


def infer(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        ("mean_confidence_interval", "one_sample_t_test", "linear_regression"),
        default="mean_confidence_interval",
    )
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)

    with mp.workdps(precision + 12):
        if action in {"mean_confidence_interval", "one_sample_t_test"}:
            sample = _sample(arguments, "sample", minimum=2)
            count = len(sample)
            mean, standard_deviation = _mean_and_sample_standard_deviation(sample)
            require(standard_deviation > 0, "E_DOMAIN", "Student t inference requires nonzero sample variation")
            standard_error = standard_deviation / mp.sqrt(count)
            estimates = [
                _estimate("mean", mean, precision),
                _estimate("sample_standard_deviation", standard_deviation, precision),
                _estimate("standard_error", standard_error, precision),
            ]
            assumptions = [
                "observations are independent",
                "the sample is representative of the target population",
                "Student t inference assumes an approximately normal sampling distribution of the mean",
            ]
            if action == "mean_confidence_interval":
                confidence = _mp_decimal(arguments, "confidenceLevel", default="0.95")
                require(0 < confidence < 1, "E_DOMAIN", "confidenceLevel must be strictly between 0 and 1")
                critical = _student_t_quantile((1 + confidence) / 2, count - 1)
                margin = critical * standard_error
                interval = {
                    "level": _text(confidence, precision),
                    "degreesOfFreedom": count - 1,
                    "lower": _value(mean - margin, precision),
                    "upper": _value(mean + margin, precision),
                }
                test = None
                method = "two_sided_student_t_interval"
            else:
                null_mean = _mp_decimal(arguments, "nullMean")
                alternative = enum_arg(arguments, "alternative", ("two_sided", "less", "greater"), default="two_sided")
                statistic = (mean - null_mean) / standard_error
                cumulative = _student_t_cdf(statistic, count - 1)
                if alternative == "less":
                    p_value = cumulative
                elif alternative == "greater":
                    p_value = 1 - cumulative
                else:
                    p_value = 2 * min(cumulative, 1 - cumulative)
                p_value = min(mp.mpf("1"), max(mp.mpf("0"), p_value))
                interval = None
                test = {
                    "statistic": _value(statistic, precision),
                    "degreesOfFreedom": count - 1,
                    "pValue": _value(p_value, precision),
                    "alternative": alternative,
                }
                method = "one_sample_student_t_test"
        else:
            x_values = _sample(arguments, "x", minimum=3)
            y_values = _sample(arguments, "y", minimum=3)
            require(len(x_values) == len(y_values), "E_INPUT", "x and y must have the same length")
            count = len(x_values)
            mean_x = mp.fsum(x_values) / count
            mean_y = mp.fsum(y_values) / count
            centered_x = [value - mean_x for value in x_values]
            centered_y = [value - mean_y for value in y_values]
            sum_xx = mp.fsum(value * value for value in centered_x)
            sum_yy = mp.fsum(value * value for value in centered_y)
            require(sum_xx > 0, "E_DOMAIN", "linear regression requires variation in x")
            require(sum_yy > 0, "E_DOMAIN", "rSquared is undefined when y has no variation")
            sum_xy = mp.fsum(left * right for left, right in zip(centered_x, centered_y, strict=True))
            slope = sum_xy / sum_xx
            intercept = mean_y - slope * mean_x
            residuals = [
                y - (intercept + slope * x)
                for x, y in zip(x_values, y_values, strict=True)
            ]
            sum_squared_error = mp.fsum(value * value for value in residuals)
            r_squared = 1 - sum_squared_error / sum_yy
            residual_standard_error = mp.sqrt(sum_squared_error / (count - 2))
            estimates = [
                _estimate("slope", slope, precision),
                _estimate("intercept", intercept, precision),
                _estimate("r_squared", r_squared, precision),
                _estimate("residual_standard_error", residual_standard_error, precision),
            ]
            interval = None
            test = None
            method = "ordinary_least_squares_centered_two_pass"
            assumptions = [
                "the relationship is modeled as linear with an intercept",
                "observations are independent and residual variance is constant for inferential interpretation",
                "reported regression coefficients are descriptive unless a separate inferential model is requested",
            ]

    return {
        "status": "ok",
        "operation": "statistics.infer",
        "kind": "inference",
        "action": action,
        "sampleSize": count,
        "estimates": estimates,
        "interval": interval,
        "test": test,
        "method": method,
        "assumptions": assumptions,
        "precision": precision,
        "warnings": ["Inferential results are approximate and depend on the stated sampling assumptions."],
    }


def _sample(arguments: dict[str, Any], name: str, *, minimum: int) -> list[mp.mpf]:
    raw_values = list_arg(arguments, name, minimum=minimum, maximum=100_000)
    values = []
    for index, raw_value in enumerate(raw_values):
        require(isinstance(raw_value, str), "E_INPUT", f"{name}[{index}] must be decimal text")
        try:
            decimal = Decimal(raw_value)
        except InvalidOperation as error:
            raise CalculatorError("E_INPUT", f"{name}[{index}] must be decimal text") from error
        require(decimal.is_finite(), "E_DOMAIN", f"{name}[{index}] must be finite")
        values.append(mp.mpf(raw_value))
    return values


def _mean_and_sample_standard_deviation(values: list[mp.mpf]) -> tuple[mp.mpf, mp.mpf]:
    mean = mp.fsum(values) / len(values)
    variance = mp.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, mp.sqrt(variance)


def _student_t_cdf(value: mp.mpf, degrees_of_freedom: int) -> mp.mpf:
    if value == 0:
        return mp.mpf("0.5")
    ratio = degrees_of_freedom / (degrees_of_freedom + value**2)
    tail = mp.betainc(degrees_of_freedom / 2, mp.mpf("0.5"), 0, ratio, regularized=True) / 2
    return 1 - tail if value > 0 else tail


def _student_t_quantile(probability: mp.mpf, degrees_of_freedom: int) -> mp.mpf:
    require(0 < probability < 1, "E_DOMAIN", "Student t probability must be strictly between 0 and 1")
    if probability == mp.mpf("0.5"):
        return mp.mpf("0")
    if probability < mp.mpf("0.5"):
        return -_student_t_quantile(1 - probability, degrees_of_freedom)
    lower = mp.mpf("0")
    upper = mp.mpf("1")
    while _student_t_cdf(upper, degrees_of_freedom) < probability:
        upper *= 2
        require(upper < mp.mpf("1e12"), "E_CONVERGENCE", "Student t quantile could not be bracketed")
    tolerance = mp.power(10, -(mp.mp.dps - 5))
    for _ in range(512):
        midpoint = (lower + upper) / 2
        if _student_t_cdf(midpoint, degrees_of_freedom) < probability:
            lower = midpoint
        else:
            upper = midpoint
        if upper - lower <= tolerance:
            return (lower + upper) / 2
    raise CalculatorError("E_CONVERGENCE", "Student t quantile did not converge")


def _mp_decimal(arguments: dict[str, Any], name: str, *, default: str | None = None) -> mp.mpf:
    text = string_arg(arguments, name, default=default, max_length=256)
    try:
        decimal = Decimal(text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{name} must be decimal text") from error
    require(decimal.is_finite(), "E_DOMAIN", f"{name} must be finite")
    return mp.mpf(text)


def _estimate(name: str, value: mp.mpf, precision: int) -> dict[str, Any]:
    return {"name": name, "value": _value(value, precision)}


def _value(value: mp.mpf, precision: int) -> dict[str, str | None]:
    return {"exact": None, "approx": _text(value, precision)}


def _text(value: mp.mpf, precision: int) -> str:
    return mp.nstr(value, precision)
