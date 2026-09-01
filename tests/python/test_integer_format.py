from __future__ import annotations

import math
import sys

from math_anchor.integer_format import approximate_integer, exact_integer_result


def test_python_integer_approximation_preserves_the_existing_significant_digit_contract() -> None:
    assert approximate_integer(0, 16) == "0"
    assert approximate_integer(3, 16) == "3.000000000000000"
    assert approximate_integer(2_598_960, 16) == "2598960.000000000"
    assert approximate_integer(10**15, 16) == "1000000000000000."
    assert approximate_integer(12_345_678_901_234_567, 16) == "1.234567890123457e+16"
    assert approximate_integer(-12_345_678_901_234_567, 16) == "-1.234567890123457e+16"


def test_exact_integer_result_remains_typed_and_bounded() -> None:
    result = exact_integer_result(
        "combinatorics.count",
        "integer_count",
        2_598_960,
        action="binomial",
    )
    assert result == {
        "status": "ok",
        "operation": "combinatorics.count",
        "kind": "integer_count",
        "exact": "2598960",
        "approx": "2598960.000000000",
        "precision": 16,
        "warnings": [],
        "action": "binomial",
    }


def test_large_integer_output_does_not_weaken_the_process_string_limit() -> None:
    get_limit = getattr(sys, "get_int_max_str_digits", None)
    if get_limit is None:
        return
    before = get_limit()

    result = exact_integer_result(
        "combinatorics.count",
        "integer_count",
        math.factorial(5_000),
        action="permutations",
    )

    assert len(result["exact"]) == 16_326
    assert get_limit() == before
