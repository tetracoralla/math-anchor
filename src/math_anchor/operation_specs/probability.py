from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _continuous_distribution_object,
    _object,
    probability,
)


SPECS = (
    OperationSpec(
        id="probability.distribution",
        category="probability",
        summary="Evaluate common probability distributions.",
        description="Evaluate normal, Beta, Gamma, and lognormal PDF/CDF/quantiles plus binomial and Poisson PMF/CDF with explicit parameters and arbitrary-precision numerical methods.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "distribution": {"const": "normal"},
                        "function": {"type": "string", "enum": ["pdf", "cdf"]},
                        "x": _DECIMAL_TEXT,
                        "mean": {**_DECIMAL_TEXT, "default": "0"},
                        "standardDeviation": {**_DECIMAL_TEXT, "default": "1"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "x"),
                ),
                _object(
                    {
                        "distribution": {"const": "normal"},
                        "function": {"const": "quantile"},
                        "probability": _DECIMAL_TEXT,
                        "mean": {**_DECIMAL_TEXT, "default": "0"},
                        "standardDeviation": {**_DECIMAL_TEXT, "default": "1"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "probability"),
                ),
                _object(
                    {
                        "distribution": {"const": "binomial"},
                        "function": {"type": "string", "enum": ["pmf", "cdf"]},
                        "n": {"type": "integer", "minimum": 0, "maximum": 100_000},
                        "k": {"type": "integer", "minimum": 0, "maximum": 100_000},
                        "probability": _DECIMAL_TEXT,
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "n", "k", "probability"),
                ),
                _object(
                    {
                        "distribution": {"const": "poisson"},
                        "function": {"type": "string", "enum": ["pmf", "cdf"]},
                        "k": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
                        "rate": _DECIMAL_TEXT,
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("distribution", "function", "k", "rate"),
                ),
                _continuous_distribution_object(
                    "beta",
                    {"alpha": _DECIMAL_TEXT, "beta": _DECIMAL_TEXT},
                    ("alpha", "beta"),
                ),
                _continuous_distribution_object(
                    "gamma",
                    {"shape": _DECIMAL_TEXT, "scale": {**_DECIMAL_TEXT, "default": "1"}},
                    ("shape",),
                ),
                _continuous_distribution_object(
                    "lognormal",
                    {
                        "logMean": {**_DECIMAL_TEXT, "default": "0"},
                        "logStandardDeviation": {**_DECIMAL_TEXT, "default": "1"},
                    },
                    (),
                ),
            ]
        },
        examples=(
            {"distribution": "normal", "function": "cdf", "x": "1.96"},
            {"distribution": "binomial", "function": "cdf", "n": 20, "k": 4, "probability": "0.1"},
            {"distribution": "poisson", "function": "pmf", "k": 3, "rate": "2.5"},
            {"distribution": "beta", "function": "quantile", "probability": "0.95", "alpha": "2", "beta": "5"},
            {"distribution": "gamma", "function": "cdf", "x": "4", "shape": "2", "scale": "3"},
            {"distribution": "lognormal", "function": "pdf", "x": "2", "logMean": "0", "logStandardDeviation": "1"},
        ),
        handler=probability.distribution,
        keywords=("normal distribution", "binomial", "Poisson", "beta distribution", "gamma distribution", "lognormal", "cdf", "pmf", "quantile", "概率分布", "正态分布", "二项分布", "泊松分布", "贝塔分布", "伽马分布", "对数正态分布"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
