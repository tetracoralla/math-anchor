from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import math
import re
import struct
from typing import Any

from ..errors import CalculatorError, require
from ..validation import enum_arg, string_arg


_FORMATS = {
    "binary32": {"bits": 32, "exponent": 8, "fraction": 23, "pack": "f"},
    "binary64": {"bits": 64, "exponent": 11, "fraction": 52, "pack": "d"},
}
_INPUT_MODES = ("decimal", "bits")
_BIT_LITERAL = re.compile(r"^(?:0[bB][01]+|0[oO][0-7]+|0[xX][0-9A-Fa-f]+|[0-9]+)$")
_SPECIAL_DECIMALS = {
    "nan": math.nan,
    "+nan": math.nan,
    "-nan": -math.nan,
    "infinity": math.inf,
    "+infinity": math.inf,
    "inf": math.inf,
    "+inf": math.inf,
    "-infinity": -math.inf,
    "-inf": -math.inf,
}


def ieee754(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", ("inspect", "compare"), default="inspect")
    format_name = enum_arg(arguments, "format", tuple(_FORMATS), default="binary64")
    input_mode = enum_arg(arguments, "inputMode", _INPUT_MODES, default="decimal")
    if action == "inspect":
        decoded = _decode(arguments, "value", format_name, input_mode)
        return {
            "status": "ok",
            "operation": "float.ieee754",
            "kind": "ieee754",
            "action": action,
            "format": format_name,
            "inputMode": input_mode,
            "value": decoded["projection"],
            "right": None,
            "comparison": None,
            "numericEqual": None,
            "bitsEqual": None,
            "ulpDistance": None,
            "absoluteDifference": None,
            "warnings": decoded["warnings"],
        }

    left = _decode(arguments, "left", format_name, input_mode)
    right = _decode(arguments, "right", format_name, input_mode)
    left_value = left["value"]
    right_value = right["value"]
    if math.isnan(left_value) or math.isnan(right_value):
        comparison = "unordered"
        numeric_equal = False
        ulp_distance = None
        absolute_difference = None
    else:
        numeric_equal = left_value == right_value
        if numeric_equal:
            comparison = "equal"
        elif left_value < right_value:
            comparison = "less"
        else:
            comparison = "greater"
        ulp_distance = str(_ulp_distance(left["bits"], right["bits"], format_name))
        absolute_difference = (
            _fraction_value(abs(Fraction.from_float(left_value) - Fraction.from_float(right_value)))
            if math.isfinite(left_value) and math.isfinite(right_value)
            else None
        )
    return {
        "status": "ok",
        "operation": "float.ieee754",
        "kind": "ieee754",
        "action": action,
        "format": format_name,
        "inputMode": input_mode,
        "value": left["projection"],
        "right": right["projection"],
        "comparison": comparison,
        "numericEqual": numeric_equal,
        "bitsEqual": left["bits"] == right["bits"],
        "ulpDistance": ulp_distance,
        "absoluteDifference": absolute_difference,
        "warnings": [*left["warnings"], *right["warnings"]],
    }


def _decode(
    arguments: dict[str, Any],
    name: str,
    format_name: str,
    input_mode: str,
) -> dict[str, Any]:
    text = string_arg(arguments, name, max_length=256)
    specification = _FORMATS[format_name]
    bit_count = specification["bits"]
    if input_mode == "bits":
        require(_BIT_LITERAL.fullmatch(text) is not None, "E_INPUT", f"{name} must be a nonnegative integer bit pattern")
        bits = int(text, 0) if text.lower().startswith(("0b", "0o", "0x")) else int(text, 10)
        require(bits < 1 << bit_count, "E_LIMIT", f"{name} does not fit {format_name}")
        source_decimal: Decimal | None = None
    else:
        source_decimal, source_float = _decimal_input(text, name)
        bits = _float_to_bits(source_float, format_name, name)
    value = _bits_to_float(bits, format_name)
    projection = _projection(bits, value, format_name)
    warnings: list[str] = []
    if input_mode == "bits":
        projection["inputRounded"] = False
        projection["roundingDirection"] = "exact"
    else:
        rounded, direction = _rounding_metadata(source_decimal, value)
        projection["inputRounded"] = rounded
        projection["roundingDirection"] = direction
        if rounded:
            warnings.append(f"{name} was rounded to the nearest representable {format_name} value using ties-to-even.")
    return {"bits": bits, "value": value, "projection": projection, "warnings": warnings}


def _decimal_input(text: str, name: str) -> tuple[Decimal | None, float]:
    special = _SPECIAL_DECIMALS.get(text.strip().lower())
    if special is not None:
        return None, special
    try:
        decimal = Decimal(text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{name} must be decimal text, Infinity, -Infinity, or NaN") from error
    require(decimal.is_finite(), "E_INPUT", f"{name} is not a supported IEEE 754 decimal input")
    try:
        return decimal, float(decimal)
    except (OverflowError, ValueError) as error:
        raise CalculatorError("E_DOMAIN", f"{name} is outside the supported decimal conversion range") from error


def _float_to_bits(value: float, format_name: str, name: str) -> int:
    specification = _FORMATS[format_name]
    try:
        packed = struct.pack(">" + specification["pack"], value)
    except OverflowError:
        packed = struct.pack(">" + specification["pack"], math.copysign(math.inf, value))
    except struct.error as error:
        raise CalculatorError("E_DOMAIN", f"{name} cannot be represented as {format_name}") from error
    return int.from_bytes(packed, "big")


def _bits_to_float(bits: int, format_name: str) -> float:
    specification = _FORMATS[format_name]
    return struct.unpack(">" + specification["pack"], bits.to_bytes(specification["bits"] // 8, "big"))[0]


def _projection(bits: int, value: float, format_name: str) -> dict[str, Any]:
    specification = _FORMATS[format_name]
    total_bits = specification["bits"]
    exponent_width = specification["exponent"]
    fraction_width = specification["fraction"]
    sign = bits >> (total_bits - 1)
    fraction_mask = (1 << fraction_width) - 1
    exponent_mask = (1 << exponent_width) - 1
    fraction_bits = bits & fraction_mask
    exponent_bits = (bits >> fraction_width) & exponent_mask
    if exponent_bits == exponent_mask:
        classification = "infinity" if fraction_bits == 0 else "nan"
    elif exponent_bits == 0:
        classification = "zero" if fraction_bits == 0 else "subnormal"
    else:
        classification = "normal"
    bias = (1 << (exponent_width - 1)) - 1
    unbiased_exponent = exponent_bits - bias if classification == "normal" else None
    exact_value = _fraction_value(Fraction.from_float(value)) if math.isfinite(value) else None
    ulp = None
    if classification in {"zero", "subnormal", "normal"}:
        ulp_exponent = (
            1 - bias - fraction_width
            if exponent_bits == 0
            else exponent_bits - bias - fraction_width
        )
        ulp = _fraction_value(_power_of_two(ulp_exponent))
    previous_bits = _adjacent_bits(bits, format_name, -1, classification)
    next_bits = _adjacent_bits(bits, format_name, 1, classification)
    return {
        "classification": classification,
        "sign": sign,
        "negativeZero": classification == "zero" and sign == 1,
        "rawHex": f"{bits:0{total_bits // 4}X}",
        "exponentBits": f"{exponent_bits:0{exponent_width}b}",
        # IEEE 754 calls this stored field the trailing significand field (or
        # fraction). Calling it the complete significand would hide the normal
        # number's implicit leading 1, so expose the unambiguous field name.
        "fractionBits": f"{fraction_bits:0{fraction_width}b}",
        "unbiasedExponent": unbiased_exponent,
        "exactValue": exact_value,
        "roundTripDecimal": _round_trip_decimal(value, format_name),
        "ulp": ulp,
        "previous": _neighbor(previous_bits, format_name),
        "next": _neighbor(next_bits, format_name),
        "inputRounded": False,
        "roundingDirection": "exact",
    }


def _fraction_value(value: Fraction) -> dict[str, str]:
    with localcontext() as context:
        context.prec = 1200
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    rational = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return {"rational": rational, "decimal": format(decimal, "f")}


def _power_of_two(exponent: int) -> Fraction:
    return Fraction(1 << exponent, 1) if exponent >= 0 else Fraction(1, 1 << -exponent)


def _round_trip_decimal(value: float, format_name: str) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "-Infinity" if value < 0 else "Infinity"
    if format_name == "binary64":
        # CPython's repr is the shortest decimal that round-trips to the same
        # binary64 value, including a sign-preserving spelling for -0.0.
        return repr(value)
    original_bits = _float_to_bits(value, "binary32", "value")
    for precision in range(1, 10):
        candidate = format(value, f".{precision}g")
        if _float_to_bits(float(candidate), "binary32", "value") == original_bits:
            return candidate
    return format(value, ".9g")  # defensive; nine digits always suffice


def _rounding_metadata(source: Decimal | None, value: float) -> tuple[bool, str]:
    if source is None:
        return False, "exact"
    if math.isinf(value):
        return True, "overflow"
    numerator, denominator = value.as_integer_ratio()
    with localcontext() as context:
        context.prec = 1200
        represented = Decimal(numerator) / Decimal(denominator)
    if represented == source:
        return False, "exact"
    return True, "up" if represented > source else "down"


def _neighbor(bits: int | None, format_name: str) -> dict[str, str] | None:
    if bits is None:
        return None
    value = _bits_to_float(bits, format_name)
    width = _FORMATS[format_name]["bits"]
    return {
        "rawHex": f"{bits:0{width // 4}X}",
        "roundTripDecimal": _round_trip_decimal(value, format_name),
    }


def _adjacent_bits(
    bits: int,
    format_name: str,
    direction: int,
    classification: str,
) -> int | None:
    if classification == "nan":
        return None
    width = _FORMATS[format_name]["bits"]
    sign_bit = 1 << (width - 1)
    exponent_mask = (1 << _FORMATS[format_name]["exponent"]) - 1
    positive_infinity = exponent_mask << _FORMATS[format_name]["fraction"]
    negative_infinity = sign_bit | positive_infinity
    if direction > 0:
        if bits == positive_infinity:
            return None
        if bits == negative_infinity:
            return negative_infinity - 1
        if bits == sign_bit:
            # Total order counts -0 and +0 as adjacent (they are one ULP
            # apart in _ulp_distance); the next value after -0 is +0.
            return 0
        return bits - 1 if bits & sign_bit else bits + 1
    if bits == negative_infinity:
        return None
    if bits == positive_infinity:
        return positive_infinity - 1
    if bits == 0:
        return sign_bit
    candidate = bits + 1 if bits & sign_bit else bits - 1
    return candidate & ((1 << width) - 1)


def _ulp_distance(left: int, right: int, format_name: str) -> int:
    width = _FORMATS[format_name]["bits"]
    sign_bit = 1 << (width - 1)
    mask = (1 << width) - 1

    def ordered(bits: int) -> int:
        return (~bits & mask) if bits & sign_bit else bits | sign_bit

    return abs(ordered(left) - ordered(right))
