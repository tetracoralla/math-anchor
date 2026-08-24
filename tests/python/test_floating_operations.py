from __future__ import annotations

import math
import random
import struct

import pytest

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_binary64_inspection_exposes_the_exact_value_and_rounding_direction() -> None:
    result = execute_direct(
        "float.ieee754",
        {"action": "inspect", "value": "0.1", "format": "binary64"},
    )
    value = result["value"]
    assert value["rawHex"] == "3FB999999999999A"
    assert value["classification"] == "normal"
    assert value["fractionBits"] == "1001100110011001100110011001100110011001100110011010"
    assert value["exactValue"]["rational"] == "3602879701896397/36028797018963968"
    assert value["roundTripDecimal"] == "0.1"
    assert value["inputRounded"] is True
    assert value["roundingDirection"] == "up"
    assert value["previous"]["rawHex"] == "3FB9999999999999"
    assert value["next"]["rawHex"] == "3FB999999999999B"
    assert result["warnings"]


def test_binary32_bits_negative_zero_and_subnormal_stay_distinct() -> None:
    one = execute_direct(
        "float.ieee754",
        {
            "action": "inspect",
            "value": "0x3F800000",
            "format": "binary32",
            "inputMode": "bits",
        },
    )
    assert one["value"]["roundTripDecimal"] == "1"
    assert one["value"]["exactValue"] == {"rational": "1", "decimal": "1"}

    negative_zero = execute_direct(
        "float.ieee754",
        {"action": "inspect", "value": "0x80000000", "format": "binary32", "inputMode": "bits"},
    )
    assert negative_zero["value"]["classification"] == "zero"
    assert negative_zero["value"]["negativeZero"] is True
    # Signed zeros are adjacent in the total order, matching the ULP-distance
    # convention: the next value after -0 is +0 itself, not 0x00000001.
    assert negative_zero["value"]["next"]["rawHex"] == "00000000"

    positive_zero = execute_direct(
        "float.ieee754",
        {"action": "inspect", "value": "0x00000000", "format": "binary32", "inputMode": "bits"},
    )
    assert positive_zero["value"]["classification"] == "zero"
    assert positive_zero["value"]["previous"]["rawHex"] == "80000000"
    assert positive_zero["value"]["next"]["rawHex"] == "00000001"

    subnormal = execute_direct(
        "float.ieee754",
        {"action": "inspect", "value": "1", "format": "binary32", "inputMode": "bits"},
    )
    assert subnormal["value"]["classification"] == "subnormal"
    assert subnormal["value"]["ulp"]["rational"] == "1/713623846352979940529142984724747568191373312"


def test_ieee_comparison_separates_numeric_bitwise_and_ulp_equality() -> None:
    rounded_same = execute_direct(
        "float.ieee754",
        {
            "action": "compare",
            "left": "0.1",
            "right": "0.10000000000000001",
            "format": "binary64",
        },
    )
    assert rounded_same["comparison"] == "equal"
    assert rounded_same["numericEqual"] is True
    assert rounded_same["bitsEqual"] is True
    assert rounded_same["ulpDistance"] == "0"

    adjacent = execute_direct(
        "float.ieee754",
        {
            "action": "compare",
            "left": "0x3FF0000000000000",
            "right": "0x3FF0000000000001",
            "format": "binary64",
            "inputMode": "bits",
        },
    )
    assert adjacent["comparison"] == "less"
    assert adjacent["ulpDistance"] == "1"
    assert adjacent["absoluteDifference"]["rational"] == "1/4503599627370496"


def test_ieee_special_values_and_invalid_bit_patterns_are_bounded() -> None:
    nan = execute_direct(
        "float.ieee754",
        {"action": "compare", "left": "NaN", "right": "1", "format": "binary64"},
    )
    assert nan["comparison"] == "unordered"
    assert nan["ulpDistance"] is None

    infinity = execute_direct(
        "float.ieee754",
        {"action": "inspect", "value": "Infinity", "format": "binary32"},
    )
    assert infinity["value"]["classification"] == "infinity"
    assert infinity["value"]["next"] is None

    for value in ("-1", "0x100000000"):
        with pytest.raises(CalculatorError) as raised:
            execute_direct(
                "float.ieee754",
                {"action": "inspect", "value": value, "format": "binary32", "inputMode": "bits"},
            )
        assert raised.value.code in {"E_INPUT", "E_LIMIT"}


@pytest.mark.parametrize(
    ("format_name", "width", "pack", "samples"),
    [("binary32", 32, "f", 500), ("binary64", 64, "d", 500)],
)
def test_random_ieee_bit_patterns_round_trip_without_changing_finite_bits(
    format_name: str,
    width: int,
    pack: str,
    samples: int,
) -> None:
    randomizer = random.Random(width)
    for _ in range(samples):
        bits = randomizer.getrandbits(width)
        result = execute_direct(
            "float.ieee754",
            {
                "action": "inspect",
                "value": hex(bits),
                "format": format_name,
                "inputMode": "bits",
            },
        )["value"]
        assert int(result["rawHex"], 16) == bits
        value = struct.unpack(">" + pack, bits.to_bytes(width // 8, "big"))[0]
        if not math.isfinite(value):
            continue
        decimal = float(result["roundTripDecimal"])
        repacked = int.from_bytes(struct.pack(">" + pack, decimal), "big")
        assert repacked == bits
