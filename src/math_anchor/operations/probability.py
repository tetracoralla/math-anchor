from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import mpmath as mp

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, string_arg


def distribution(arguments: dict[str, Any]) -> dict[str, Any]:
    distribution_name = enum_arg(
        arguments,
        "distribution",
        ("normal", "binomial", "poisson", "beta", "gamma", "lognormal"),
        default="normal",
    )
    function = enum_arg(arguments, "function", ("pdf", "cdf", "quantile", "pmf"), default="cdf")
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)
    warnings: list[str] = []
    exact_result: str | None = None

    with mp.workdps(precision + 10):
        if distribution_name == "normal":
            require(function in {"pdf", "cdf", "quantile"}, "E_INPUT", "normal supports pdf, cdf, and quantile")
            mean = _mp_decimal(arguments, "mean", default="0")
            standard_deviation = _mp_decimal(arguments, "standardDeviation", default="1")
            require(standard_deviation > 0, "E_DOMAIN", "standardDeviation must be positive")
            if function == "quantile":
                probability = _mp_decimal(arguments, "probability")
                require(0 < probability < 1, "E_DOMAIN", "probability must be strictly between 0 and 1")
                standard = mp.sqrt(2) * mp.erfinv(2 * probability - 1)
                result = mean + standard_deviation * standard
                parameters = [
                    {"name": "probability", "value": _text(probability, precision)},
                    {"name": "mean", "value": _text(mean, precision)},
                    {"name": "standard_deviation", "value": _text(standard_deviation, precision)},
                ]
            else:
                x = _mp_decimal(arguments, "x")
                z = (x - mean) / standard_deviation
                if function == "pdf":
                    result = mp.exp(-(z**2) / 2) / (standard_deviation * mp.sqrt(2 * mp.pi))
                else:
                    result = (1 + mp.erf(z / mp.sqrt(2))) / 2
                parameters = [
                    {"name": "x", "value": _text(x, precision)},
                    {"name": "mean", "value": _text(mean, precision)},
                    {"name": "standard_deviation", "value": _text(standard_deviation, precision)},
                ]
            method = "mpmath_erf"
            support = "all real numbers"
        elif distribution_name == "binomial":
            require(function in {"pmf", "cdf"}, "E_INPUT", "binomial supports pmf and cdf")
            n = integer_arg(arguments, "n", default=1, minimum=0, maximum=100_000)
            k = integer_arg(arguments, "k", default=0, minimum=0, maximum=100_000)
            probability = _mp_decimal(arguments, "probability")
            require(0 <= probability <= 1, "E_DOMAIN", "probability must be between 0 and 1")
            if k > n:
                result = mp.mpf("0") if function == "pmf" else mp.mpf("1")
            elif function == "pmf":
                if probability == 0:
                    result = mp.mpf("1") if k == 0 else mp.mpf("0")
                elif probability == 1:
                    result = mp.mpf("1") if k == n else mp.mpf("0")
                else:
                    result = mp.binomial(n, k) * probability**k * (1 - probability) ** (n - k)
            elif k == n or probability == 0:
                result = mp.mpf("1")
            elif probability == 1:
                result = mp.mpf("0")
            else:
                result = mp.betainc(n - k, k + 1, 0, 1 - probability, regularized=True)
            parameters = [
                {"name": "n", "value": str(n)},
                {"name": "k", "value": str(k)},
                {"name": "probability", "value": _text(probability, precision)},
            ]
            method = "exact_combinatorial_pmf" if function == "pmf" else "regularized_incomplete_beta"
            support = "integers from 0 through n"
        elif distribution_name == "poisson":
            require(function in {"pmf", "cdf"}, "E_INPUT", "poisson supports pmf and cdf")
            k = integer_arg(arguments, "k", default=0, minimum=0, maximum=1_000_000)
            rate = _mp_decimal(arguments, "rate")
            require(rate >= 0, "E_DOMAIN", "rate must be nonnegative")
            if rate == 0:
                result = mp.mpf("1") if function == "cdf" or k == 0 else mp.mpf("0")
            elif function == "pmf":
                result = mp.exp(-rate + k * mp.log(rate) - mp.loggamma(k + 1))
            else:
                result = mp.gammainc(k + 1, rate, mp.inf, regularized=True)
            parameters = [
                {"name": "k", "value": str(k)},
                {"name": "rate", "value": _text(rate, precision)},
            ]
            method = "log_gamma_pmf" if function == "pmf" else "regularized_upper_incomplete_gamma"
            support = "nonnegative integers"
        elif distribution_name == "beta":
            require(function in {"pdf", "cdf", "quantile"}, "E_INPUT", "beta supports pdf, cdf, and quantile")
            alpha = _mp_decimal(arguments, "alpha")
            beta = _mp_decimal(arguments, "beta")
            require(alpha > 0 and beta > 0, "E_DOMAIN", "alpha and beta must be positive")
            if function == "quantile":
                probability = _strict_probability(arguments)
                result = _bisect_quantile(
                    lambda value: mp.betainc(alpha, beta, 0, value, regularized=True),
                    probability,
                    mp.mpf("0"),
                    mp.mpf("1"),
                    precision,
                )
                parameters = [
                    {"name": "probability", "value": _text(probability, precision)},
                    {"name": "alpha", "value": _text(alpha, precision)},
                    {"name": "beta", "value": _text(beta, precision)},
                ]
            else:
                x = _mp_decimal(arguments, "x")
                if function == "cdf":
                    result = mp.mpf("0") if x <= 0 else mp.mpf("1") if x >= 1 else mp.betainc(alpha, beta, 0, x, regularized=True)
                elif x < 0 or x > 1:
                    result = mp.mpf("0")
                elif (x == 0 and alpha < 1) or (x == 1 and beta < 1):
                    # These are valid support boundaries, not provider
                    # failures. Evaluating 0 to a negative power raises before
                    # the generic finite-result guard can classify the value.
                    result = mp.inf
                    exact_result = "oo"
                    warnings.append(
                        "The Beta density has an integrable positive-infinity singularity at this support boundary."
                    )
                else:
                    result = x ** (alpha - 1) * (1 - x) ** (beta - 1) / mp.beta(alpha, beta)
                parameters = [
                    {"name": "x", "value": _text(x, precision)},
                    {"name": "alpha", "value": _text(alpha, precision)},
                    {"name": "beta", "value": _text(beta, precision)},
                ]
            method = "regularized_incomplete_beta"
            support = "real numbers from 0 through 1"
        elif distribution_name == "gamma":
            require(function in {"pdf", "cdf", "quantile"}, "E_INPUT", "gamma supports pdf, cdf, and quantile")
            shape = _mp_decimal(arguments, "shape")
            scale = _mp_decimal(arguments, "scale", default="1")
            require(shape > 0 and scale > 0, "E_DOMAIN", "shape and scale must be positive")
            gamma_cdf = lambda value: mp.gammainc(shape, 0, value / scale, regularized=True)
            if function == "quantile":
                probability = _strict_probability(arguments)
                upper = max(scale, shape * scale)
                for _ in range(512):
                    if gamma_cdf(upper) >= probability:
                        break
                    upper *= 2
                else:
                    raise CalculatorError("E_CONVERGENCE", "gamma quantile could not be bracketed")
                result = _bisect_quantile(gamma_cdf, probability, mp.mpf("0"), upper, precision)
                parameters = [
                    {"name": "probability", "value": _text(probability, precision)},
                    {"name": "shape", "value": _text(shape, precision)},
                    {"name": "scale", "value": _text(scale, precision)},
                ]
            else:
                x = _mp_decimal(arguments, "x")
                if function == "cdf":
                    result = mp.mpf("0") if x <= 0 else gamma_cdf(x)
                elif x < 0:
                    result = mp.mpf("0")
                elif x == 0 and shape < 1:
                    result = mp.inf
                    exact_result = "oo"
                    warnings.append(
                        "The Gamma density has an integrable positive-infinity singularity at zero."
                    )
                else:
                    result = x ** (shape - 1) * mp.exp(-x / scale) / (mp.gamma(shape) * scale**shape)
                parameters = [
                    {"name": "x", "value": _text(x, precision)},
                    {"name": "shape", "value": _text(shape, precision)},
                    {"name": "scale", "value": _text(scale, precision)},
                ]
            method = "regularized_lower_incomplete_gamma"
            support = "nonnegative real numbers"
        else:
            require(function in {"pdf", "cdf", "quantile"}, "E_INPUT", "lognormal supports pdf, cdf, and quantile")
            log_mean = _mp_decimal(arguments, "logMean", default="0")
            log_standard_deviation = _mp_decimal(arguments, "logStandardDeviation", default="1")
            require(log_standard_deviation > 0, "E_DOMAIN", "logStandardDeviation must be positive")
            if function == "quantile":
                probability = _strict_probability(arguments)
                z = mp.sqrt(2) * mp.erfinv(2 * probability - 1)
                result = mp.exp(log_mean + log_standard_deviation * z)
                parameters = [
                    {"name": "probability", "value": _text(probability, precision)},
                    {"name": "log_mean", "value": _text(log_mean, precision)},
                    {"name": "log_standard_deviation", "value": _text(log_standard_deviation, precision)},
                ]
            else:
                x = _mp_decimal(arguments, "x")
                if x <= 0:
                    result = mp.mpf("0")
                else:
                    z = (mp.log(x) - log_mean) / log_standard_deviation
                    result = (
                        mp.exp(-(z**2) / 2) / (x * log_standard_deviation * mp.sqrt(2 * mp.pi))
                        if function == "pdf"
                        else (1 + mp.erf(z / mp.sqrt(2))) / 2
                    )
                parameters = [
                    {"name": "x", "value": _text(x, precision)},
                    {"name": "log_mean", "value": _text(log_mean, precision)},
                    {"name": "log_standard_deviation", "value": _text(log_standard_deviation, precision)},
                ]
            method = "log_transform_and_erf"
            support = "positive real numbers"

        require(
            mp.isfinite(result) or (exact_result == "oo" and result == mp.inf),
            "E_DOMAIN",
            "distribution result is not finite",
        )
        if function in {"cdf", "pmf"}:
            result = min(mp.mpf("1"), max(mp.mpf("0"), result))
        result_text = "Infinity" if exact_result == "oo" else _text(result, precision)

    return {
        "status": "ok",
        "operation": "probability.distribution",
        "kind": "probability",
        "distribution": distribution_name,
        "function": function,
        "value": {"exact": exact_result, "approx": result_text},
        "parameters": parameters,
        "method": method,
        "support": support,
        "precision": precision,
        "warnings": warnings,
    }


def _mp_decimal(arguments: dict[str, Any], name: str, *, default: str | None = None) -> mp.mpf:
    text = string_arg(arguments, name, default=default, max_length=256)
    try:
        decimal = Decimal(text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{name} must be decimal text") from error
    require(decimal.is_finite(), "E_DOMAIN", f"{name} must be finite")
    return mp.mpf(text)


def _text(value: mp.mpf, precision: int) -> str:
    return mp.nstr(value, precision)


def _strict_probability(arguments: dict[str, Any]) -> mp.mpf:
    probability = _mp_decimal(arguments, "probability")
    require(0 < probability < 1, "E_DOMAIN", "probability must be strictly between 0 and 1")
    return probability


def _bisect_quantile(
    cumulative: Any,
    probability: mp.mpf,
    lower: mp.mpf,
    upper: mp.mpf,
    precision: int,
) -> mp.mpf:
    iterations = min(512, int((precision + 15) * 3.5) + 16)
    for _ in range(iterations):
        midpoint = (lower + upper) / 2
        if cumulative(midpoint) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2
