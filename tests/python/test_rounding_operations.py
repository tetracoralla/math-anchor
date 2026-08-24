from __future__ import annotations

import pytest

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_decimal_places_distinguish_tie_breaking_modes_exactly() -> None:
    half_even = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "2.345", "decimalPlaces": 2, "roundingMode": "half_even"},
    )
    half_up = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "2.345", "decimalPlaces": 2, "roundingMode": "half_up"},
    )
    half_down = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "-2.345", "decimalPlaces": 2, "roundingMode": "half_down"},
    )
    assert half_even["result"] == "2.34"
    assert half_up["result"] == "2.35"
    assert half_down["result"] == "-2.34"
    assert half_even["quantum"] == "0.01"
    assert half_even["changed"] is True
    assert half_even["direction"] == "down"


def test_decimal_places_can_round_left_of_the_point_and_preserve_negative_zero() -> None:
    hundreds_even = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "1250", "decimalPlaces": -2, "roundingMode": "half_even"},
    )
    hundreds_up = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "1250", "decimalPlaces": -2, "roundingMode": "half_up"},
    )
    negative_zero = execute_direct(
        "decimal.quantize",
        {"action": "decimal_places", "value": "-0.004", "decimalPlaces": 2, "roundingMode": "half_up"},
    )
    assert hundreds_even["result"] == "1200"
    assert hundreds_up["result"] == "1300"
    assert negative_zero["result"] == "-0.00"
    assert negative_zero["negativeZero"] is True
    assert negative_zero["direction"] == "up"


def test_significant_digits_and_increment_rounding_preserve_declared_quantum() -> None:
    significant = execute_direct(
        "decimal.quantize",
        {
            "action": "significant_digits",
            "value": "12345.678",
            "significantDigits": 4,
            "roundingMode": "half_up",
        },
    )
    significant_zero = execute_direct(
        "decimal.quantize",
        {
            "action": "significant_digits",
            "value": "0",
            "significantDigits": 3,
        },
    )
    cash = execute_direct(
        "decimal.quantize",
        {
            "action": "increment",
            "value": "1.23",
            "increment": "0.05",
            "roundingMode": "half_up",
        },
    )
    negative_ceiling = execute_direct(
        "decimal.quantize",
        {
            "action": "increment",
            "value": "-1.23",
            "increment": "0.05",
            "roundingMode": "ceiling",
        },
    )
    assert significant["result"] == "12350"
    assert significant["quantum"] == "10"
    assert significant_zero["result"] == "0.00"
    assert cash["result"] == "1.25"
    assert cash["quantum"] == "0.05"
    assert negative_ceiling["result"] == "-1.20"


@pytest.mark.parametrize(
    ("rounding_mode", "expected"),
    [
        ("toward_zero", "1.2"),
        ("away_from_zero", "1.3"),
        ("ceiling", "1.3"),
        ("floor", "1.2"),
    ],
)
def test_directed_rounding_modes_are_not_collapsed(rounding_mode: str, expected: str) -> None:
    result = execute_direct(
        "decimal.quantize",
        {
            "action": "decimal_places",
            "value": "1.21",
            "decimalPlaces": 1,
            "roundingMode": rounding_mode,
        },
    )
    assert result["result"] == expected


def test_decimal_quantization_rejects_nonfinite_nonpositive_and_unbounded_inputs() -> None:
    cases = [
        ({"action": "decimal_places", "value": "NaN", "decimalPlaces": 2}, "E_INPUT"),
        ({"action": "increment", "value": "1", "increment": "0"}, "E_DOMAIN"),
        ({"action": "increment", "value": "1", "increment": "-0.05"}, "E_DOMAIN"),
        ({"action": "significant_digits", "value": "1e10001", "significantDigits": 3}, "E_LIMIT"),
        ({"action": "decimal_places", "value": "1", "decimalPlaces": 101}, "E_LIMIT"),
        ({"action": "decimal_places", "value": "1", "decimalPlaces": 2, "unexpected": True}, "E_INPUT"),
    ]
    for arguments, code in cases:
        with pytest.raises(CalculatorError) as raised:
            execute_direct("decimal.quantize", arguments)
        assert raised.value.code == code


@pytest.mark.parametrize(
    ("dividend", "divisor", "mode", "quotient", "remainder"),
    [
        ("-7", "3", "truncating", "-2", "-1"),
        ("-7", "3", "floor", "-3", "2"),
        ("-7", "3", "euclidean", "-3", "2"),
        ("7", "-3", "truncating", "-2", "1"),
        ("7", "-3", "floor", "-3", "-2"),
        ("7", "-3", "euclidean", "-2", "1"),
        ("-7", "-3", "truncating", "2", "-1"),
        ("-7", "-3", "floor", "2", "-1"),
        ("-7", "-3", "euclidean", "3", "2"),
    ],
)
def test_integer_division_conventions_preserve_identity(
    dividend: str,
    divisor: str,
    mode: str,
    quotient: str,
    remainder: str,
) -> None:
    result = execute_direct(
        "integer.divide",
        {"dividend": dividend, "divisor": divisor, "divisionMode": mode},
    )
    assert result["quotient"] == quotient
    assert result["remainder"] == remainder
    assert int(dividend) == int(divisor) * int(quotient) + int(remainder)
    assert result["remainderMagnitudeLessThanDivisor"] is True
    if mode == "euclidean":
        assert result["remainderNonnegative"] is True


def test_integer_division_rejects_zero_unicode_digits_wide_text_and_unknown_fields() -> None:
    cases = [
        ({"dividend": "1", "divisor": "0"}, "E_DOMAIN"),
        ({"dividend": "٥", "divisor": "2"}, "E_INPUT"),
        ({"dividend": 7, "divisor": "2"}, "E_INPUT"),
        ({"dividend": "1" * 1001, "divisor": "2"}, "E_LIMIT"),
        ({"dividend": "7", "divisor": "2", "unexpected": True}, "E_INPUT"),
    ]
    for arguments, code in cases:
        with pytest.raises(CalculatorError) as raised:
            execute_direct("integer.divide", arguments)
        assert raised.value.code == code
