from __future__ import annotations

from decimal import (
    Decimal,
    DecimalException,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    localcontext,
)
import re
from typing import Any

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, string_arg


_ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
    "half_down": ROUND_HALF_DOWN,
    "toward_zero": ROUND_DOWN,
    "away_from_zero": ROUND_UP,
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
}
_INTEGER_TEXT = re.compile(r"^[+-]?[0-9]+$")
_MAX_DECIMAL_ADJUSTED_EXPONENT = 10_000
_DECIMAL_CONTEXT_PRECISION = 25_000


def quantize(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        ("decimal_places", "significant_digits", "increment"),
        default="decimal_places",
    )
    source_text = string_arg(arguments, "value", max_length=256)
    value = _finite_decimal(source_text, "value")
    rounding_mode = enum_arg(
        arguments,
        "roundingMode",
        tuple(_ROUNDING_MODES),
        default="half_even",
    )
    decimal_places: int | None = None
    significant_digits: int | None = None
    increment_text: str | None = None

    if action == "decimal_places":
        decimal_places = integer_arg(
            arguments,
            "decimalPlaces",
            default=2,
            minimum=-100,
            maximum=100,
        )
        quantum = Decimal(1).scaleb(-decimal_places)
    elif action == "significant_digits":
        significant_digits = integer_arg(
            arguments,
            "significantDigits",
            default=6,
            minimum=1,
            maximum=100,
        )
        exponent = -significant_digits + 1 if value.is_zero() else value.adjusted() - significant_digits + 1
        quantum = Decimal(1).scaleb(exponent)
    else:
        increment_text = string_arg(arguments, "increment", max_length=256)
        quantum = _finite_decimal(increment_text, "increment")
        require(quantum > 0, "E_DOMAIN", "increment must be positive")

    try:
        with localcontext() as context:
            context.prec = _DECIMAL_CONTEXT_PRECISION
            context.rounding = _ROUNDING_MODES[rounding_mode]
            if action == "increment":
                multiple = (value / quantum).quantize(Decimal(1))
                rounded = (multiple * quantum).quantize(quantum)
            else:
                rounded = value.quantize(quantum)
    except InvalidOperation as error:
        raise CalculatorError("E_LIMIT", "decimal quantization exceeded the supported precision range") from error
    except DecimalException as error:
        raise CalculatorError("E_DOMAIN", f"decimal quantization failed: {error}") from error

    changed = rounded != value
    if rounded > value:
        direction = "up"
    elif rounded < value:
        direction = "down"
    else:
        direction = "unchanged"
    return {
        "status": "ok",
        "operation": "decimal.quantize",
        "kind": "decimal_quantization",
        "action": action,
        "input": source_text,
        "result": format(rounded, "f"),
        "quantum": format(quantum, "f"),
        "roundingMode": rounding_mode,
        "changed": changed,
        "direction": direction,
        "negativeZero": rounded.is_zero() and rounded.is_signed(),
        "decimalPlaces": decimal_places,
        "significantDigits": significant_digits,
        "increment": increment_text,
        "warnings": [],
    }


def divide_integer(arguments: dict[str, Any]) -> dict[str, Any]:
    dividend = _integer_text(arguments, "dividend")
    divisor = _integer_text(arguments, "divisor")
    require(divisor != 0, "E_DOMAIN", "divisor must not be zero")
    mode = enum_arg(
        arguments,
        "divisionMode",
        ("truncating", "floor", "euclidean"),
        default="truncating",
    )

    if mode == "truncating":
        quotient = abs(dividend) // abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
        remainder = dividend - divisor * quotient
    elif mode == "floor":
        quotient, remainder = divmod(dividend, divisor)
    else:
        quotient, remainder = divmod(dividend, abs(divisor))
        if divisor < 0:
            quotient = -quotient

    if dividend != divisor * quotient + remainder:
        # Unreachable for correct mode arithmetic; guarded rather than
        # asserted so `python -O` cannot silently disable the invariant.
        raise CalculatorError("E_RUNTIME", "integer division invariant violated")
    return {
        "status": "ok",
        "operation": "integer.divide",
        "kind": "integer_division",
        "divisionMode": mode,
        "dividend": str(dividend),
        "divisor": str(divisor),
        "quotient": str(quotient),
        "remainder": str(remainder),
        "remainderNonnegative": remainder >= 0,
        "remainderMagnitudeLessThanDivisor": abs(remainder) < abs(divisor),
        "warnings": [],
    }


def _finite_decimal(text: str, name: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{name} must be decimal text") from error
    require(value.is_finite(), "E_DOMAIN", f"{name} must be finite")
    require(
        abs(value.adjusted()) <= _MAX_DECIMAL_ADJUSTED_EXPONENT,
        "E_LIMIT",
        f"{name} exponent magnitude must not exceed {_MAX_DECIMAL_ADJUSTED_EXPONENT}",
    )
    return value


def _integer_text(arguments: dict[str, Any], name: str) -> int:
    text = string_arg(arguments, name, max_length=1_000)
    require(_INTEGER_TEXT.fullmatch(text) is not None, "E_INPUT", f"{name} must be ASCII integer text")
    return int(text)
