from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _EXPRESSION,
    _object,
    measurement,
)


SPECS = (
    OperationSpec(
        id="measurement.propagate",
        category="measurement",
        summary="Propagate standard uncertainties through an explicit mathematical model.",
        description="Apply first-order Taylor covariance propagation to coherent-unit decimal inputs, validate the correlation matrix, and report nominal, combined standard, and coverage-factor-expanded uncertainty separately.",
        input_schema=_object(
            {
                "expression": _EXPRESSION,
                "inputs": {
                    "type": "object",
                    "propertyNames": {"pattern": r"^[A-Za-z_][A-Za-z0-9_]*$", "maxLength": 64},
                    "additionalProperties": _object(
                        {
                            "value": _DECIMAL_TEXT,
                            "standardUncertainty": _DECIMAL_TEXT,
                        },
                        ("value", "standardUncertainty"),
                    ),
                    "minProperties": 1,
                    "maxProperties": 16,
                },
                "correlations": {
                    "type": "array",
                    "maxItems": 120,
                    "items": _object(
                        {
                            "left": {"type": "string", "maxLength": 64},
                            "right": {"type": "string", "maxLength": 64},
                            "coefficient": _DECIMAL_TEXT,
                        },
                        ("left", "right", "coefficient"),
                    ),
                    "default": [],
                },
                "coverageFactor": {**_DECIMAL_TEXT, "default": "2"},
                "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 30},
            },
            ("expression", "inputs"),
        ),
        examples=(
            {
                "expression": "x + y",
                "inputs": {
                    "x": {"value": "10", "standardUncertainty": "0.5"},
                    "y": {"value": "20", "standardUncertainty": "1"},
                },
            },
            {
                "expression": "x * y",
                "inputs": {
                    "x": {"value": "2", "standardUncertainty": "0.1"},
                    "y": {"value": "3", "standardUncertainty": "0.2"},
                },
                "correlations": [{"left": "x", "right": "y", "coefficient": "0.5"}],
            },
        ),
        handler=measurement.propagate,
        keywords=("measurement uncertainty", "error propagation", "covariance", "correlation", "coverage factor", "GUM", "不确定度传播", "误差传播", "协方差", "相关系数", "扩展不确定度"),
        assurance="diagnostic",
        assurance_scope="first_order_covariance_model_in_coherent_units",
        backends=("sympy",),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
