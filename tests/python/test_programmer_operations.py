from __future__ import annotations

import random

import pytest

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_fixed_width_representation_keeps_value_and_bit_pattern_meanings_explicit() -> None:
    signed_pattern = execute_direct(
        "integer.represent",
        {
            "value": "0xFF",
            "bitWidth": 8,
            "signedness": "twos_complement",
            "inputMode": "bits",
        },
    )
    assert signed_pattern["result"] == {
        "unsignedDecimal": "255",
        "signedDecimal": "-1",
        "decimal": "-1",
        "binary": "11111111",
        "octal": "377",
        "hexadecimal": "FF",
        "character": {
            "validUnicodeScalar": True,
            "unicodeScalar": "U+00FF",
            "unicodeName": "LATIN SMALL LETTER Y WITH DIAERESIS",
            "character": "ÿ",
            "ascii": False,
            "printable": True,
        },
    }
    assert signed_pattern["overflow"] is False
    assert signed_pattern["wrapped"] is False

    negative_value = execute_direct(
        "integer.represent",
        {"value": "-1", "bitWidth": 8, "signedness": "twos_complement"},
    )
    assert negative_value["result"]["hexadecimal"] == "FF"
    assert negative_value["result"]["decimal"] == "-1"

    unicode_value = execute_direct("integer.represent", {"value": "375"})
    assert unicode_value["result"]["hexadecimal"] == "0000000000000177"
    assert unicode_value["result"]["character"]["unicodeScalar"] == "U+0177"
    assert unicode_value["result"]["character"]["character"] == "ŷ"


def test_programmer_literals_reject_ambiguous_or_out_of_range_inputs() -> None:
    cases = [
        ({"value": "FF", "bitWidth": 8}, "E_INPUT"),
        ({"value": "0x100", "bitWidth": 8, "inputMode": "bits"}, "E_LIMIT"),
        ({"value": "-1", "bitWidth": 8, "inputMode": "bits"}, "E_INPUT"),
        (
            {
                "value": "0xFF",
                "bitWidth": 8,
                "signedness": "twos_complement",
                "inputMode": "value",
            },
            "E_LIMIT",
        ),
        ({"value": "1", "bitWidth": 24}, "E_INPUT"),
    ]
    for arguments, code in cases:
        with pytest.raises(CalculatorError) as raised:
            execute_direct("integer.represent", arguments)
        assert raised.value.code == code

    with pytest.raises(CalculatorError) as unknown:
        execute_direct("integer.represent", {"value": "1", "unexpected": True})
    assert unknown.value.code == "E_INPUT"


def test_character_projection_distinguishes_ascii_printability_and_unicode_scalars() -> None:
    ascii_letter = execute_direct("integer.represent", {"value": "0x41", "bitWidth": 8, "inputMode": "bits"})
    assert ascii_letter["result"]["character"] == {
        "validUnicodeScalar": True,
        "unicodeScalar": "U+0041",
        "unicodeName": "LATIN CAPITAL LETTER A",
        "character": "A",
        "ascii": True,
        "printable": True,
    }

    control = execute_direct("integer.represent", {"value": "0", "bitWidth": 8})
    assert control["result"]["character"]["ascii"] is True
    assert control["result"]["character"]["printable"] is False
    assert control["result"]["character"]["character"] is None

    surrogate = execute_direct(
        "integer.represent",
        {"value": "0xD800", "bitWidth": 16, "inputMode": "bits"},
    )
    assert surrogate["result"]["character"] == {
        "validUnicodeScalar": False,
        "unicodeScalar": None,
        "unicodeName": None,
        "character": None,
        "ascii": False,
        "printable": False,
    }


def test_boolean_bit_operations_preserve_fixed_width_patterns() -> None:
    expected = {
        "and": "A0",
        "or": "FA",
        "xor": "5A",
        "nor": "05",
    }
    for action, hexadecimal in expected.items():
        result = execute_direct(
            "integer.bitwise",
            {
                "action": action,
                "left": "0xF0",
                "right": "0xAA",
                "bitWidth": 8,
                "inputMode": "bits",
            },
        )
        assert result["result"]["hexadecimal"] == hexadecimal
        assert len(result["operands"]) == 2
        assert result["overflow"] is False

    inverted = execute_direct(
        "integer.bitwise",
        {"action": "not", "value": "0x0F", "bitWidth": 8, "inputMode": "bits"},
    )
    assert inverted["result"]["hexadecimal"] == "F0"


def test_negation_and_left_shift_report_signed_overflow_without_hiding_wrap() -> None:
    unsigned_negation = execute_direct(
        "integer.bitwise",
        {"action": "negate", "value": "1", "bitWidth": 8},
    )
    assert unsigned_negation["result"]["hexadecimal"] == "FF"
    assert unsigned_negation["result"]["decimal"] == "255"
    assert unsigned_negation["overflow"] is True
    assert unsigned_negation["wrapped"] is True

    signed_boundary = execute_direct(
        "integer.bitwise",
        {
            "action": "negate",
            "value": "-128",
            "bitWidth": 8,
            "signedness": "twos_complement",
        },
    )
    assert signed_boundary["result"]["decimal"] == "-128"
    assert signed_boundary["overflow"] is True

    sign_change_without_discarded_one = execute_direct(
        "integer.bitwise",
        {
            "action": "shift_left",
            "value": "64",
            "count": 1,
            "bitWidth": 8,
            "signedness": "twos_complement",
        },
    )
    assert sign_change_without_discarded_one["result"]["decimal"] == "-128"
    assert sign_change_without_discarded_one["overflow"] is True
    assert sign_change_without_discarded_one["discardedBits"] == "0"
    assert sign_change_without_discarded_one["truncated"] is False


def test_shifts_report_discarded_bits_and_keep_logical_and_arithmetic_right_distinct() -> None:
    shifted_left = execute_direct(
        "integer.bitwise",
        {"action": "shift_left", "value": "0x81", "count": 1, "bitWidth": 8, "inputMode": "bits"},
    )
    assert shifted_left["result"]["hexadecimal"] == "02"
    assert shifted_left["discardedBits"] == "1"
    assert shifted_left["truncated"] is True
    assert shifted_left["overflow"] is True

    logical = execute_direct(
        "integer.bitwise",
        {
            "action": "logical_shift_right",
            "value": "0x81",
            "count": 1,
            "bitWidth": 8,
            "signedness": "twos_complement",
            "inputMode": "bits",
        },
    )
    arithmetic = execute_direct(
        "integer.bitwise",
        {
            "action": "arithmetic_shift_right",
            "value": "0x81",
            "count": 1,
            "bitWidth": 8,
            "signedness": "twos_complement",
            "inputMode": "bits",
        },
    )
    assert logical["result"]["hexadecimal"] == "40"
    assert arithmetic["result"]["hexadecimal"] == "C0"
    assert logical["discardedBits"] == arithmetic["discardedBits"] == "1"

    with pytest.raises(CalculatorError) as unsigned_arithmetic:
        execute_direct(
            "integer.bitwise",
            {"action": "arithmetic_shift_right", "value": "1", "bitWidth": 8},
        )
    assert unsigned_arithmetic.value.code == "E_INPUT"


def test_rotations_and_chunk_reversals_are_lossless_and_width_aware() -> None:
    rotated = execute_direct(
        "integer.bitwise",
        {"action": "rotate_left", "value": "0x81", "count": 9, "bitWidth": 8, "inputMode": "bits"},
    )
    assert rotated["result"]["hexadecimal"] == "03"
    assert rotated["count"] == 9
    assert rotated["effectiveCount"] == 1
    assert rotated["truncated"] is False

    rotated_default = execute_direct(
        "integer.bitwise",
        {"action": "rotate_right", "value": "0x03", "bitWidth": 8, "inputMode": "bits"},
    )
    assert rotated_default["result"]["hexadecimal"] == "81"
    assert rotated_default["count"] == 1

    byte_reversed = execute_direct(
        "integer.bitwise",
        {"action": "reverse_bytes", "value": "0xABCD", "bitWidth": 16, "inputMode": "bits"},
    )
    word_reversed = execute_direct(
        "integer.bitwise",
        {"action": "reverse_words", "value": "0xABCD1234", "bitWidth": 32, "inputMode": "bits"},
    )
    assert byte_reversed["result"]["hexadecimal"] == "CDAB"
    assert word_reversed["result"]["hexadecimal"] == "1234ABCD"

    with pytest.raises(CalculatorError) as invalid_word_width:
        execute_direct(
            "integer.bitwise",
            {"action": "reverse_words", "value": "1", "bitWidth": 8},
        )
    assert invalid_word_width.value.code == "E_INPUT"


def test_bit_measurement_fields_and_alignment_are_single_call_machine_helpers() -> None:
    cases = {
        "count_ones": "4",
        "leading_zeros": "0",
        "trailing_zeros": "4",
        "reverse_bits": "15",
    }
    for action, decimal in cases.items():
        result = execute_direct(
            "integer.bitwise",
            {"action": action, "value": "0xF0", "bitWidth": 8, "inputMode": "bits"},
        )
        assert result["result"]["decimal"] == decimal

    extracted = execute_direct(
        "integer.bitwise",
        {
            "action": "extract",
            "value": "0b11010110",
            "offset": 2,
            "fieldWidth": 3,
            "bitWidth": 8,
            "inputMode": "bits",
        },
    )
    assert extracted["result"]["binary"] == "00000101"
    assert extracted["offset"] == 2
    assert extracted["fieldWidth"] == 3

    inserted = execute_direct(
        "integer.bitwise",
        {
            "action": "insert",
            "value": "0x00",
            "field": "0b101",
            "offset": 2,
            "fieldWidth": 3,
            "bitWidth": 8,
            "inputMode": "bits",
        },
    )
    assert inserted["result"]["hexadecimal"] == "14"

    aligned = execute_direct(
        "integer.bitwise",
        {"action": "align_up", "value": "65", "alignment": "64", "bitWidth": 8},
    )
    assert aligned["result"]["decimal"] == "128"
    assert aligned["alignment"] == "64"


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "extract", "value": "1", "offset": 7, "fieldWidth": 2, "bitWidth": 8},
        {"action": "insert", "value": "0", "field": "8", "offset": 0, "fieldWidth": 3, "bitWidth": 8},
        {"action": "align_up", "value": "1", "alignment": "3", "bitWidth": 8},
        {"action": "align_down", "value": "-1", "alignment": "8", "bitWidth": 8, "signedness": "twos_complement"},
    ],
)
def test_bit_field_and_alignment_guards_reject_ambiguous_machine_semantics(arguments) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct("integer.bitwise", arguments)
    assert raised.value.code in {"E_INPUT", "E_LIMIT"}


def test_machine_arithmetic_separates_checked_wrapping_and_saturating_overflow() -> None:
    base = {
        "action": "add",
        "left": "127",
        "right": "1",
        "bitWidth": 8,
        "signedness": "twos_complement",
    }
    checked = execute_direct("integer.machine_arithmetic", base)
    assert checked["outcome"] == "overflow"
    assert checked["mathematicalResult"] == "128"
    assert checked["result"] is None
    assert checked["overflow"] is True

    wrapped = execute_direct(
        "integer.machine_arithmetic",
        {**base, "overflowBehavior": "wrapping"},
    )
    assert wrapped["result"]["decimal"] == "-128"
    assert wrapped["wrapped"] is True

    saturated = execute_direct(
        "integer.machine_arithmetic",
        {
            "action": "multiply",
            "left": "200",
            "right": "2",
            "bitWidth": 8,
            "overflowBehavior": "saturating",
        },
    )
    assert saturated["mathematicalResult"] == "400"
    assert saturated["result"]["decimal"] == "255"
    assert saturated["saturated"] is True


def test_machine_division_preserves_convention_and_minimum_overflow() -> None:
    euclidean = execute_direct(
        "integer.machine_arithmetic",
        {
            "action": "divide",
            "left": "-99",
            "right": "-10",
            "bitWidth": 16,
            "signedness": "twos_complement",
            "divisionMode": "euclidean",
        },
    )
    assert euclidean["result"]["decimal"] == "10"
    assert euclidean["remainder"]["decimal"] == "1"
    assert euclidean["mathematicalRemainder"] == "1"

    minimum_overflow = execute_direct(
        "integer.machine_arithmetic",
        {
            "action": "divide",
            "left": "-128",
            "right": "-1",
            "bitWidth": 8,
            "signedness": "twos_complement",
        },
    )
    assert minimum_overflow["outcome"] == "overflow"
    assert minimum_overflow["result"] is None

    with pytest.raises(CalculatorError) as zero:
        execute_direct(
            "integer.machine_arithmetic",
            {"action": "divide", "left": "1", "right": "0", "bitWidth": 8},
        )
    assert zero.value.code == "E_DOMAIN"


@pytest.mark.parametrize("signedness", ["unsigned", "twos_complement"])
def test_random_machine_arithmetic_matches_fixed_width_oracle(signedness: str) -> None:
    randomizer = random.Random(signedness)
    width = 8
    mask = (1 << width) - 1

    def selected(raw: int) -> int:
        return raw - (1 << width) if signedness == "twos_complement" and raw & 0x80 else raw

    minimum, maximum = (
        (0, mask) if signedness == "unsigned" else (-(1 << 7), (1 << 7) - 1)
    )
    for _ in range(200):
        left_raw = randomizer.randrange(256)
        right_raw = randomizer.randrange(256)
        left, right = selected(left_raw), selected(right_raw)
        for action, mathematical in (
            ("add", left + right),
            ("subtract", left - right),
            ("multiply", left * right),
        ):
            for behavior in ("checked", "wrapping", "saturating"):
                result = execute_direct(
                    "integer.machine_arithmetic",
                    {
                        "action": action,
                        "left": str(left_raw),
                        "right": str(right_raw),
                        "bitWidth": width,
                        "signedness": signedness,
                        "inputMode": "bits",
                        "overflowBehavior": behavior,
                    },
                )
                overflow = not minimum <= mathematical <= maximum
                assert result["mathematicalResult"] == str(mathematical)
                assert result["overflow"] is overflow
                if overflow and behavior == "checked":
                    assert result["result"] is None
                else:
                    expected = (
                        min(max(mathematical, minimum), maximum)
                        if behavior == "saturating"
                        else selected(mathematical & mask)
                    )
                    assert result["result"]["decimal"] == str(expected)


def test_random_division_modes_preserve_their_remainder_invariants() -> None:
    randomizer = random.Random(754)
    for _ in range(300):
        dividend = randomizer.randint(-32_768, 32_767)
        divisor = randomizer.choice([value for value in range(-127, 128) if value])
        for mode in ("truncating", "floor", "euclidean"):
            result = execute_direct(
                "integer.machine_arithmetic",
                {
                    "action": "divide",
                    "left": str(dividend),
                    "right": str(divisor),
                    "bitWidth": 16,
                    "signedness": "twos_complement",
                    "divisionMode": mode,
                },
            )
            quotient = int(result["mathematicalResult"])
            remainder = int(result["mathematicalRemainder"])
            assert dividend == divisor * quotient + remainder
            assert abs(remainder) < abs(divisor)
            if mode == "truncating" and remainder:
                assert (remainder > 0) == (dividend > 0)
            elif mode == "floor" and remainder:
                assert (remainder > 0) == (divisor > 0)
            elif mode == "euclidean":
                assert remainder >= 0
