"""Representative deterministic workloads for ``script/load_check.py``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkloadCase:
    id: str
    operation: str
    arguments: dict[str, Any]
    expected_path: tuple[str | int, ...]
    expected: Any
    absolute_tolerance: float = 0.0


CODING_AGENT_CASES = (
    WorkloadCase(
        "machine-wrapping-add",
        "integer.machine_arithmetic",
        {
            "action": "add",
            "left": "250",
            "right": "20",
            "bitWidth": 8,
            "signedness": "unsigned",
            "inputMode": "value",
            "overflowBehavior": "wrapping",
        },
        ("result", "decimal"),
        "14",
    ),
    WorkloadCase(
        "rotate-left-u8",
        "integer.bitwise",
        {"action": "rotate_left", "value": "0x81", "count": 1, "bitWidth": 8, "inputMode": "bits"},
        ("result", "unsignedDecimal"),
        "3",
    ),
    WorkloadCase(
        "binary64-ulp-distance",
        "float.ieee754",
        {"action": "compare", "left": "1.0", "right": "1.0000000000000002", "format": "binary64"},
        ("ulpDistance",),
        "1",
    ),
    WorkloadCase(
        "decimal-half-even",
        "decimal.quantize",
        {"action": "decimal_places", "value": "2.675", "decimalPlaces": 2, "roundingMode": "half_even"},
        ("result",),
        "2.68",
    ),
    WorkloadCase(
        "binomial-100-50",
        "combinatorics.count",
        {"action": "binomial", "n": 100, "k": 50},
        ("exact",),
        "100891344545564193334812497256",
    ),
    WorkloadCase(
        "determinant-4x4",
        "matrix.determinant",
        {"matrix": [[17, 23, 5, 11], [31, 47, 13, 19], [2, 3, 7, 29], [37, 41, 43, 53]]},
        ("exact",),
        "-78848",
    ),
    WorkloadCase(
        "gibibyte-to-bits",
        "units.convert",
        {"value": "1", "fromUnit": "gibibyte", "toUnit": "bit"},
        ("exact",),
        "8589934592",
    ),
    WorkloadCase(
        "force-expression",
        "quantity.evaluate",
        {"expression": "80 * kg * 9.81 * m / s^2", "toUnit": "newton"},
        ("exact",),
        "3924/5",
    ),
    WorkloadCase(
        "correlated-uncertainty",
        "measurement.propagate",
        {
            "expression": "x + y",
            "inputs": {
                "x": {"value": "10", "standardUncertainty": "3"},
                "y": {"value": "20", "standardUncertainty": "4"},
            },
            "correlations": [{"left": "x", "right": "y", "coefficient": "1"}],
        },
        ("combinedStandardUncertainty", "exact"),
        "7",
    ),
    WorkloadCase(
        "normal-quantile",
        "probability.distribution",
        {"distribution": "normal", "function": "quantile", "probability": "0.975"},
        ("value", "approx"),
        1.959963984540054,
        1e-14,
    ),
    WorkloadCase(
        "integral-sine",
        "numeric.integrate",
        {
            "expression": "sin(x)",
            "variable": "x",
            "lower": "0",
            "upper": "3.14159265358979323846",
            "featureScale": "0.1",
        },
        ("approx",),
        2.0,
        1e-12,
    ),
    WorkloadCase(
        "compound-future-value",
        "finance.calculate",
        {
            "action": "compound_value",
            "principal": "1000",
            "annualRate": "0.05",
            "periodsPerYear": 1,
            "numberOfPeriods": 10,
            "decimalPlaces": 12,
        },
        ("results", 0, "approx"),
        "1628.894626777441",
    ),
    WorkloadCase(
        "energy-dimension",
        "dimension.check",
        {
            "left": "E",
            "right": "m * c^2",
            "symbols": {"E": "joule", "m": "kilogram", "c": "meter / second"},
        },
        ("dimensionallyConsistent",),
        True,
    ),
)


EXPECTED_FAILURES = (
    ("expression.evaluate", {"expression": "missing_symbol + 1"}, "E_NAME"),
    (
        "integer.machine_arithmetic",
        {
            "action": "divide",
            "left": "1",
            "right": "0",
            "bitWidth": 8,
            "signedness": "unsigned",
            "inputMode": "value",
            "overflowBehavior": "checked",
        },
        "E_DOMAIN",
    ),
    ("units.convert", {"value": "1", "fromUnit": "meter", "toUnit": "second"}, "E_UNIT"),
    ("float.ieee754", {"action": "inspect", "value": "not-a-number", "format": "binary64"}, "E_INPUT"),
)


def case_for_index(index: int) -> WorkloadCase:
    return CODING_AGENT_CASES[index % len(CODING_AGENT_CASES)]


def _value_at_path(value: Any, path: tuple[str | int, ...]) -> Any:
    current = value
    for component in path:
        current = current[component]
    return current


def verify_case(case: WorkloadCase, result: dict[str, Any]) -> None:
    if result.get("status") != "ok":
        raise AssertionError(f"{case.id} failed: {result}")
    try:
        actual = _value_at_path(result, case.expected_path)
    except (KeyError, IndexError, TypeError) as error:
        raise AssertionError(f"{case.id} omitted {case.expected_path}: {result}") from error
    if case.absolute_tolerance:
        try:
            difference = abs(float(actual) - float(case.expected))
        except (TypeError, ValueError) as error:
            raise AssertionError(f"{case.id} returned nonnumeric {actual!r}") from error
        if difference > case.absolute_tolerance:
            raise AssertionError(
                f"{case.id} differed by {difference}, tolerance={case.absolute_tolerance}: {actual!r}"
            )
    elif actual != case.expected:
        raise AssertionError(f"{case.id} expected {case.expected!r}, got {actual!r}")
