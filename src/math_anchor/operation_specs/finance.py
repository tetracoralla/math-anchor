from __future__ import annotations

from .shared import (
    OperationSpec,
    _DECIMAL_TEXT,
    _object,
    finance,
)


SPECS = (
    OperationSpec(
        id="finance.calculate",
        category="finance",
        summary="Calculate compound value, effective annual rate, loan payment, NPV, or bracketed IRR.",
        description="Use decimal arithmetic with explicit nominal-rate, compounding, period, cash-flow timing, root-bracket, and output-rounding conventions.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"const": "compound_value"},
                        "principal": _DECIMAL_TEXT,
                        "annualRate": _DECIMAL_TEXT,
                        "periodsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "numberOfPeriods": {"type": "integer", "minimum": 0, "maximum": 10_000_000},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "principal", "annualRate", "periodsPerYear", "numberOfPeriods"),
                ),
                _object(
                    {
                        "action": {"const": "effective_annual_rate"},
                        "nominalAnnualRate": _DECIMAL_TEXT,
                        "compoundsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 12},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "nominalAnnualRate", "compoundsPerYear"),
                ),
                _object(
                    {
                        "action": {"const": "loan_payment"},
                        "principal": _DECIMAL_TEXT,
                        "annualRate": _DECIMAL_TEXT,
                        "paymentsPerYear": {"type": "integer", "minimum": 1, "maximum": 100_000, "default": 12},
                        "numberOfPayments": {"type": "integer", "minimum": 1, "maximum": 10_000_000},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "principal", "annualRate", "paymentsPerYear", "numberOfPayments"),
                ),
                _object(
                    {
                        "action": {"const": "npv"},
                        "cashFlows": {"type": "array", "items": _DECIMAL_TEXT, "minItems": 2, "maxItems": 10_000},
                        "ratePerPeriod": _DECIMAL_TEXT,
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 2},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "cashFlows", "ratePerPeriod"),
                ),
                _object(
                    {
                        "action": {"const": "irr"},
                        "cashFlows": {"type": "array", "items": _DECIMAL_TEXT, "minItems": 2, "maxItems": 10_000},
                        "lowerRate": _DECIMAL_TEXT,
                        "upperRate": _DECIMAL_TEXT,
                        "tolerance": {**_DECIMAL_TEXT, "default": "1e-18"},
                        "maxIterations": {"type": "integer", "minimum": 1, "maximum": 2_000, "default": 256},
                        "decimalPlaces": {"type": "integer", "minimum": 0, "maximum": 24, "default": 12},
                        "roundingMode": {"type": "string", "enum": ["half_even", "half_up"], "default": "half_even"},
                        "precision": {"type": "integer", "minimum": 16, "maximum": 100, "default": 40},
                    },
                    ("action", "cashFlows", "lowerRate", "upperRate"),
                ),
            ]
        },
        examples=(
            {"action": "compound_value", "principal": "10000", "annualRate": "0.05", "periodsPerYear": 12, "numberOfPeriods": 120},
            {"action": "effective_annual_rate", "nominalAnnualRate": "0.12", "compoundsPerYear": 12},
            {"action": "loan_payment", "principal": "300000", "annualRate": "0.045", "paymentsPerYear": 12, "numberOfPayments": 360},
            {"action": "npv", "cashFlows": ["-1000", "400", "400", "400"], "ratePerPeriod": "0.1"},
            {"action": "irr", "cashFlows": ["-1000", "400", "400", "400"], "lowerRate": "0", "upperRate": "1"},
        ),
        handler=finance.calculate,
        keywords=("compound interest", "APR", "effective annual rate", "loan payment", "NPV", "IRR", "cash flow", "复利", "年化率", "贷款", "净现值", "内部收益率", "现金流"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
