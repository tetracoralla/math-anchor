from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _DECIMAL_TEXT_VECTOR,
    _PRECISION,
    _object,
    data,
    inference,
)


SPECS = (
    OperationSpec(
        id="statistics.describe",
        category="statistics",
        summary="Compute descriptive statistics for numeric values.",
        description="Return count, mean, median, standard deviation, range, and quartiles; decimal text stays on an exact rational path and approximate inputs use NumPy.",
        input_schema=_object(
            {
                "values": {
                    "type": "array",
                    "items": {"oneOf": [{"type": "number"}, _DECIMAL_TEXT]},
                    "minItems": 1,
                    "maxItems": 100000,
                    "description": "Numbers are approximate when sent as JSON decimals; decimal strings preserve exact decimal provenance.",
                },
                "ddof": {"type": "integer", "minimum": 0, "default": 0},
                "quartileMethod": {"type": "string", "enum": ["linear"], "default": "linear"},
                "precision": _PRECISION,
            },
            ("values",),
        ),
        examples=({"values": [12, 15, 18, 21, 24], "ddof": 1},),
        handler=data.statistics_describe,
        keywords=("mean", "median", "standard deviation", "quartile", "summary", "统计", "平均数", "中位数", "标准差", "四分位数"),
        assurance_scope="declared_sample_and_quartile_convention",
        backends=("numpy", "sympy"),
    ),
    OperationSpec(
        id="statistics.infer",
        category="statistics",
        summary="Compute confidence intervals, regression, comparative t tests, or chi-square goodness-of-fit.",
        description="Use bounded decimal-text samples and explicit variance/test methods to return approximate inferential results, degrees of freedom, sample constraints, and interpretation assumptions.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "mean_confidence_interval"},
                        "sample": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "confidenceLevel": {**_DECIMAL_TEXT, "default": "0.95"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sample"),
                ),
                _object(
                    {
                        "action": {"const": "one_sample_t_test"},
                        "sample": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "nullMean": _DECIMAL_TEXT,
                        "alternative": {"type": "string", "enum": ["two_sided", "less", "greater"], "default": "two_sided"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sample", "nullMean"),
                ),
                _object(
                    {
                        "action": {"const": "linear_regression"},
                        "x": {**_DECIMAL_TEXT_VECTOR, "minItems": 3},
                        "y": {**_DECIMAL_TEXT_VECTOR, "minItems": 3},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "x", "y"),
                ),
                _object(
                    {
                        "action": {"const": "paired_t_test"},
                        "sampleA": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "sampleB": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "nullDifference": {**_DECIMAL_TEXT, "default": "0"},
                        "alternative": {"type": "string", "enum": ["two_sided", "less", "greater"], "default": "two_sided"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sampleA", "sampleB"),
                ),
                _object(
                    {
                        "action": {"const": "two_sample_t_test"},
                        "sampleA": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "sampleB": {**_DECIMAL_TEXT_VECTOR, "minItems": 2},
                        "nullDifference": {**_DECIMAL_TEXT, "default": "0"},
                        "varianceModel": {"type": "string", "enum": ["welch", "equal"], "default": "welch"},
                        "alternative": {"type": "string", "enum": ["two_sided", "less", "greater"], "default": "two_sided"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "sampleA", "sampleB"),
                ),
                _object(
                    {
                        "action": {"const": "chi_square_goodness_of_fit"},
                        "observed": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
                            "minItems": 2,
                            "maxItems": 1_000,
                        },
                        "expectedProbabilities": {**_DECIMAL_TEXT_VECTOR, "minItems": 2, "maxItems": 1_000},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
                    },
                    ("action", "observed", "expectedProbabilities"),
                ),
            ]
        },
        examples=(
            {"action": "mean_confidence_interval", "sample": ["10", "12", "9", "11", "13"], "confidenceLevel": "0.95"},
            {"action": "one_sample_t_test", "sample": ["10", "12", "9", "11", "13"], "nullMean": "10"},
            {"action": "linear_regression", "x": ["1", "2", "3"], "y": ["2", "4.1", "5.9"]},
            {"action": "paired_t_test", "sampleA": ["10", "12", "9", "11"], "sampleB": ["8", "11", "8", "9"]},
            {"action": "two_sample_t_test", "sampleA": ["10", "12", "9"], "sampleB": ["7", "8", "9"], "varianceModel": "welch"},
            {"action": "chi_square_goodness_of_fit", "observed": [20, 30, 50], "expectedProbabilities": ["0.25", "0.25", "0.5"]},
        ),
        handler=inference.infer,
        keywords=("confidence interval", "one sample t test", "paired t test", "Welch t test", "two sample t test", "chi square goodness of fit", "regression", "hypothesis test", "置信区间", "配对t检验", "双样本t检验", "卡方拟合优度", "回归", "假设检验"),
        assurance="diagnostic",
        assurance_scope="declared_samples_model_and_test_assumptions",
        backends=("mpmath",),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
