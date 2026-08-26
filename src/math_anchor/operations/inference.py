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
        (
            "mean_confidence_interval",
            "one_sample_t_test",
            "linear_regression",
            "paired_t_test",
            "two_sample_t_test",
            "chi_square_goodness_of_fit",
        ),
        default="mean_confidence_interval",
    )
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)

    if action == "paired_t_test":
        return _paired_t_test(arguments, precision)
    if action == "two_sample_t_test":
        return _two_sample_t_test(arguments, precision)
    if action == "chi_square_goodness_of_fit":
        return _chi_square_goodness_of_fit(arguments, precision)

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


def _student_t_cdf(value: mp.mpf, degrees_of_freedom: int | mp.mpf) -> mp.mpf:
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


def _paired_t_test(arguments: dict[str, Any], precision: int) -> dict[str, Any]:
    with mp.workdps(precision + 12):
        sample_a = _sample(arguments, "sampleA", minimum=2)
        sample_b = _sample(arguments, "sampleB", minimum=2)
        require(len(sample_a) == len(sample_b), "E_INPUT", "paired samples must have the same length")
        differences = [left - right for left, right in zip(sample_a, sample_b, strict=True)]
        null_difference = _mp_decimal(arguments, "nullDifference", default="0")
        mean, standard_deviation = _mean_and_sample_standard_deviation(differences)
        require(standard_deviation > 0, "E_DOMAIN", "paired t test requires variation in paired differences")
        standard_error = standard_deviation / mp.sqrt(len(differences))
        statistic = (mean - null_difference) / standard_error
        alternative = enum_arg(arguments, "alternative", ("two_sided", "less", "greater"), default="two_sided")
        test = _student_t_test_payload(statistic, len(differences) - 1, alternative, precision)
        estimates = [
            _estimate("mean_difference", mean, precision),
            _estimate("sample_standard_deviation_of_differences", standard_deviation, precision),
            _estimate("standard_error", standard_error, precision),
        ]
    return _inference_result(
        "paired_t_test",
        len(differences),
        estimates,
        test,
        "paired_student_t_test",
        [
            "pairs are meaningfully matched and independent of other pairs",
            "the paired differences have an approximately normal sampling distribution",
        ],
        precision,
    )


def _two_sample_t_test(arguments: dict[str, Any], precision: int) -> dict[str, Any]:
    with mp.workdps(precision + 12):
        sample_a = _sample(arguments, "sampleA", minimum=2)
        sample_b = _sample(arguments, "sampleB", minimum=2)
        mean_a, standard_deviation_a = _mean_and_sample_standard_deviation(sample_a)
        mean_b, standard_deviation_b = _mean_and_sample_standard_deviation(sample_b)
        variance_a = standard_deviation_a**2
        variance_b = standard_deviation_b**2
        variance_model = enum_arg(arguments, "varianceModel", ("welch", "equal"), default="welch")
        null_difference = _mp_decimal(arguments, "nullDifference", default="0")
        if variance_model == "welch":
            term_a = variance_a / len(sample_a)
            term_b = variance_b / len(sample_b)
            standard_error = mp.sqrt(term_a + term_b)
            require(standard_error > 0, "E_DOMAIN", "two-sample t test requires variation in at least one sample")
            degrees_of_freedom = (term_a + term_b) ** 2 / (
                term_a**2 / (len(sample_a) - 1) + term_b**2 / (len(sample_b) - 1)
            )
            method = "welch_two_sample_t_test"
            assumptions = [
                "the two samples are independent",
                "Welch's test does not assume equal population variances",
                "each sample mean has an approximately normal sampling distribution",
            ]
        else:
            degrees_of_freedom = len(sample_a) + len(sample_b) - 2
            pooled_variance = (
                (len(sample_a) - 1) * variance_a + (len(sample_b) - 1) * variance_b
            ) / degrees_of_freedom
            standard_error = mp.sqrt(pooled_variance * (1 / mp.mpf(len(sample_a)) + 1 / mp.mpf(len(sample_b))))
            require(standard_error > 0, "E_DOMAIN", "two-sample t test requires nonzero pooled variation")
            method = "pooled_equal_variance_two_sample_t_test"
            assumptions = [
                "the two samples are independent",
                "the two populations have equal variances",
                "each sample mean has an approximately normal sampling distribution",
            ]
        statistic = ((mean_a - mean_b) - null_difference) / standard_error
        alternative = enum_arg(arguments, "alternative", ("two_sided", "less", "greater"), default="two_sided")
        test = _student_t_test_payload(statistic, degrees_of_freedom, alternative, precision)
        estimates = [
            _estimate("sample_a_size", mp.mpf(len(sample_a)), precision),
            _estimate("sample_b_size", mp.mpf(len(sample_b)), precision),
            _estimate("sample_a_mean", mean_a, precision),
            _estimate("sample_b_mean", mean_b, precision),
            _estimate("mean_difference", mean_a - mean_b, precision),
            _estimate("standard_error", standard_error, precision),
        ]
    return _inference_result(
        "two_sample_t_test",
        len(sample_a) + len(sample_b),
        estimates,
        test,
        method,
        assumptions,
        precision,
    )


def _chi_square_goodness_of_fit(arguments: dict[str, Any], precision: int) -> dict[str, Any]:
    observed = list_arg(arguments, "observed", minimum=2, maximum=1_000)
    require(
        all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in observed),
        "E_INPUT",
        "observed must contain nonnegative integer counts",
    )
    total = sum(observed)
    require(total >= 2, "E_DOMAIN", "observed counts must have a total of at least 2")
    raw_probabilities = list_arg(arguments, "expectedProbabilities", minimum=2, maximum=1_000)
    require(len(raw_probabilities) == len(observed), "E_INPUT", "expectedProbabilities must match observed")
    decimal_probabilities: list[Decimal] = []
    for index, value in enumerate(raw_probabilities):
        require(isinstance(value, str), "E_INPUT", f"expectedProbabilities[{index}] must be decimal text")
        try:
            decimal = Decimal(value)
        except InvalidOperation as error:
            raise CalculatorError("E_INPUT", f"expectedProbabilities[{index}] must be decimal text") from error
        require(decimal.is_finite() and decimal > 0, "E_DOMAIN", "expected probabilities must be positive")
        decimal_probabilities.append(decimal)
    require(sum(decimal_probabilities, Decimal(0)) == Decimal(1), "E_DOMAIN", "expected probabilities must sum exactly to 1")

    with mp.workdps(precision + 12):
        expected = [mp.mpf(total) * mp.mpf(str(value)) for value in decimal_probabilities]
        statistic = mp.fsum(
            (mp.mpf(observed_value) - expected_value) ** 2 / expected_value
            for observed_value, expected_value in zip(observed, expected, strict=True)
        )
        degrees_of_freedom = len(observed) - 1
        p_value = mp.gammainc(degrees_of_freedom / 2, statistic / 2, mp.inf, regularized=True)
        estimates = [
            _estimate("chi_square_statistic", statistic, precision),
            _estimate("minimum_expected_count", min(expected), precision),
        ]
        test = {
            "statistic": _value(statistic, precision),
            "degreesOfFreedom": degrees_of_freedom,
            "pValue": _value(p_value, precision),
            "alternative": "greater",
        }
    warnings = ["Inferential results are approximate and depend on the stated sampling assumptions."]
    if min(expected) < 5:
        warnings.append("At least one expected count is below 5; the chi-square approximation may be unreliable.")
    return _inference_result(
        "chi_square_goodness_of_fit",
        total,
        estimates,
        test,
        "pearson_chi_square_goodness_of_fit",
        [
            "observations are independent counts in mutually exclusive categories",
            "expected probabilities were fixed before observing these counts",
        ],
        precision,
        warnings=warnings,
    )


def _student_t_test_payload(
    statistic: mp.mpf,
    degrees_of_freedom: int | mp.mpf,
    alternative: str,
    precision: int,
) -> dict[str, Any]:
    cumulative = _student_t_cdf(statistic, degrees_of_freedom)
    if alternative == "less":
        p_value = cumulative
    elif alternative == "greater":
        p_value = 1 - cumulative
    else:
        p_value = 2 * min(cumulative, 1 - cumulative)
    p_value = min(mp.mpf("1"), max(mp.mpf("0"), p_value))
    return {
        "statistic": _value(statistic, precision),
        "degreesOfFreedom": (
            int(degrees_of_freedom)
            if isinstance(degrees_of_freedom, int)
            else _text(degrees_of_freedom, precision)
        ),
        "pValue": _value(p_value, precision),
        "alternative": alternative,
    }


def _inference_result(
    action: str,
    sample_size: int,
    estimates: list[dict[str, Any]],
    test: dict[str, Any],
    method: str,
    assumptions: list[str],
    precision: int,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "operation": "statistics.infer",
        "kind": "inference",
        "action": action,
        "sampleSize": sample_size,
        "estimates": estimates,
        "interval": None,
        "test": test,
        "method": method,
        "assumptions": assumptions,
        "precision": precision,
        "warnings": warnings or [
            "Inferential results are approximate and depend on the stated sampling assumptions."
        ],
    }
