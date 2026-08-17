from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import mpmath as mp

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, string_arg


def distribution(arguments: dict[str, Any]) -> dict[str, Any]:
    distribution_name = enum_arg(arguments, "distribution", ("normal", "binomial", "poisson"), default="normal")
    function = enum_arg(arguments, "function", ("pdf", "cdf", "quantile", "pmf"), default="cdf")
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)
    warnings: list[str] = []

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
        else:
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

        require(mp.isfinite(result), "E_DOMAIN", "distribution result is not finite")
        if function in {"cdf", "pmf"}:
            result = min(mp.mpf("1"), max(mp.mpf("0"), result))
        result_text = _text(result, precision)

    return {
        "status": "ok",
        "operation": "probability.distribution",
        "kind": "probability",
        "distribution": distribution_name,
        "function": function,
        "value": {"exact": None, "approx": result_text},
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
