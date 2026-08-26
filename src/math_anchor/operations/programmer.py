from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, string_arg


_LITERAL = re.compile(
    r"^[+-]?(?:0[bB][01]+|0[oO][0-7]+|0[xX][0-9A-Fa-f]+|[0-9]+)$"
)
_BIT_WIDTHS = (8, 16, 32, 64, 128, 256)
_SIGNEDNESS = ("unsigned", "twos_complement")
_INPUT_MODES = ("value", "bits")
_BINARY_ACTIONS = ("and", "or", "xor", "nor")
_UNARY_ACTIONS = (
    "not",
    "negate",
    "count_ones",
    "leading_zeros",
    "trailing_zeros",
    "reverse_bits",
)
_SHIFT_ACTIONS = (
    "shift_left",
    "logical_shift_right",
    "arithmetic_shift_right",
    "rotate_left",
    "rotate_right",
)
_REVERSAL_ACTIONS = ("reverse_bytes", "reverse_words")
_BIT_FIELD_ACTIONS = ("extract", "insert")
_ALIGN_ACTIONS = ("align_up", "align_down")
_ARITHMETIC_ACTIONS = ("add", "subtract", "multiply", "divide", "remainder")
_OVERFLOW_BEHAVIORS = ("checked", "wrapping", "saturating")
_DIVISION_MODES = ("truncating", "floor", "euclidean")


def represent(arguments: dict[str, Any]) -> dict[str, Any]:
    bit_width, signedness, input_mode = _common(arguments)
    raw = _decode_literal(
        arguments,
        "value",
        bit_width=bit_width,
        signedness=signedness,
        input_mode=input_mode,
    )
    representation = _representation(raw, bit_width, signedness)
    return _result(
        operation="integer.represent",
        action="represent",
        bit_width=bit_width,
        signedness=signedness,
        input_mode=input_mode,
        operands=[representation],
        result=representation,
    )


def bitwise(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        (
            *_BINARY_ACTIONS,
            *_UNARY_ACTIONS,
            *_SHIFT_ACTIONS,
            *_REVERSAL_ACTIONS,
            *_BIT_FIELD_ACTIONS,
            *_ALIGN_ACTIONS,
        ),
        default="and",
    )
    bit_width, signedness, input_mode = _common(arguments)
    mask = (1 << bit_width) - 1
    overflow = False
    discarded_bits: str | None = None
    count: int | None = None
    effective_count: int | None = None
    metadata: dict[str, Any] = {}

    if action in _BINARY_ACTIONS:
        left = _decode_literal(
            arguments,
            "left",
            bit_width=bit_width,
            signedness=signedness,
            input_mode=input_mode,
        )
        right = _decode_literal(
            arguments,
            "right",
            bit_width=bit_width,
            signedness=signedness,
            input_mode=input_mode,
        )
        operands = [
            _representation(left, bit_width, signedness),
            _representation(right, bit_width, signedness),
        ]
        if action == "and":
            raw_result = left & right
        elif action == "or":
            raw_result = left | right
        elif action == "xor":
            raw_result = left ^ right
        else:
            raw_result = ~(left | right) & mask
    else:
        raw = _decode_literal(
            arguments,
            "value",
            bit_width=bit_width,
            signedness=signedness,
            input_mode=input_mode,
        )
        operands = [_representation(raw, bit_width, signedness)]
        selected = _selected_value(raw, bit_width, signedness)

        if action == "not":
            raw_result = ~raw & mask
        elif action == "negate":
            mathematical = -selected
            overflow = not _selected_range_contains(mathematical, bit_width, signedness)
            raw_result = -raw & mask
        elif action == "count_ones":
            raw_result = raw.bit_count()
        elif action == "leading_zeros":
            raw_result = bit_width - raw.bit_length()
        elif action == "trailing_zeros":
            raw_result = bit_width if raw == 0 else (raw & -raw).bit_length() - 1
        elif action == "reverse_bits":
            raw_result = int(f"{raw:0{bit_width}b}"[::-1], 2)
        elif action in _SHIFT_ACTIONS:
            count = integer_arg(
                arguments,
                "count",
                default=1,
                minimum=0,
                maximum=max(_BIT_WIDTHS),
            )
            bits = f"{raw:0{bit_width}b}"
            discarded_count = min(count, bit_width)
            if action == "shift_left":
                discarded_bits = bits[:discarded_count] if discarded_count else None
                mathematical = selected * (1 << count)
                overflow = not _selected_range_contains(mathematical, bit_width, signedness)
                raw_result = 0 if count >= bit_width else (raw << count) & mask
                effective_count = min(count, bit_width)
            elif action == "logical_shift_right":
                discarded_bits = bits[-discarded_count:] if discarded_count else None
                raw_result = 0 if count >= bit_width else raw >> count
                effective_count = min(count, bit_width)
            elif action == "arithmetic_shift_right":
                require(
                    signedness == "twos_complement",
                    "E_INPUT",
                    "arithmetic_shift_right requires twos_complement signedness",
                )
                discarded_bits = bits[-discarded_count:] if discarded_count else None
                raw_result = (_signed_value(raw, bit_width) >> count) & mask
                effective_count = min(count, bit_width)
            elif action == "rotate_left":
                effective_count = count % bit_width
                raw_result = (
                    ((raw << effective_count) | (raw >> (bit_width - effective_count))) & mask
                    if effective_count
                    else raw
                )
            else:
                effective_count = count % bit_width
                raw_result = (
                    ((raw >> effective_count) | (raw << (bit_width - effective_count))) & mask
                    if effective_count
                    else raw
                )
        elif action == "reverse_bytes":
            raw_result = _reverse_chunks(raw, bit_width, 8)
        elif action == "reverse_words":
            require(bit_width % 16 == 0, "E_INPUT", "reverse_words requires a bitWidth divisible by 16")
            raw_result = _reverse_chunks(raw, bit_width, 16)
        elif action in _BIT_FIELD_ACTIONS:
            offset = integer_arg(arguments, "offset", default=0, minimum=0, maximum=255)
            field_width = integer_arg(arguments, "fieldWidth", default=1, minimum=1, maximum=256)
            require(offset + field_width <= bit_width, "E_INPUT", "offset + fieldWidth must not exceed bitWidth")
            field_mask = (1 << field_width) - 1
            metadata = {"offset": offset, "fieldWidth": field_width}
            if action == "extract":
                raw_result = (raw >> offset) & field_mask
            else:
                field = _decode_field_literal(arguments, "field", field_width)
                operands.append(_representation(field, field_width, "unsigned"))
                raw_result = (raw & ~(field_mask << offset)) | (field << offset)
        else:
            require(signedness == "unsigned", "E_INPUT", f"{action} requires unsigned signedness")
            require(input_mode == "value", "E_INPUT", f"{action} requires inputMode=value")
            alignment = _decode_unbounded_literal(arguments, "alignment")
            require(alignment > 0 and alignment & (alignment - 1) == 0, "E_INPUT", "alignment must be a positive power of two")
            metadata = {"alignment": str(alignment)}
            if action == "align_up":
                mathematical = (selected + alignment - 1) & -alignment
                overflow = not _selected_range_contains(mathematical, bit_width, signedness)
                raw_result = mathematical & mask
            else:
                raw_result = selected & -alignment

    truncated = discarded_bits is not None and "1" in discarded_bits
    warnings: list[str] = []
    if overflow:
        warnings.append("The mathematical result overflowed and wrapped to the selected fixed width.")
    if truncated:
        warnings.append("The shift discarded one or more nonzero bits.")
    return _result(
        operation="integer.bitwise",
        action=action,
        bit_width=bit_width,
        signedness=signedness,
        input_mode=input_mode,
        operands=operands,
        result=_representation(raw_result, bit_width, signedness),
        overflow=overflow,
        wrapped=overflow,
        truncated=truncated,
        discarded_bits=discarded_bits,
        count=count,
        effective_count=effective_count,
        warnings=warnings,
        metadata=metadata,
    )


def machine_arithmetic(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", _ARITHMETIC_ACTIONS, default="add")
    bit_width, signedness, input_mode = _common(arguments)
    overflow_behavior = enum_arg(
        arguments,
        "overflowBehavior",
        _OVERFLOW_BEHAVIORS,
        default="checked",
    )
    left_raw = _decode_literal(
        arguments,
        "left",
        bit_width=bit_width,
        signedness=signedness,
        input_mode=input_mode,
    )
    right_raw = _decode_literal(
        arguments,
        "right",
        bit_width=bit_width,
        signedness=signedness,
        input_mode=input_mode,
    )
    left = _selected_value(left_raw, bit_width, signedness)
    right = _selected_value(right_raw, bit_width, signedness)
    division_mode: str | None = None
    mathematical_remainder: int | None = None

    if action == "add":
        mathematical = left + right
    elif action == "subtract":
        mathematical = left - right
    elif action == "multiply":
        mathematical = left * right
    else:
        require(right != 0, "E_DOMAIN", "integer division by zero is undefined")
        division_mode = enum_arg(
            arguments,
            "divisionMode",
            _DIVISION_MODES,
            default="truncating",
        )
        quotient, remainder = _divide(left, right, division_mode)
        if action == "divide":
            mathematical = quotient
            mathematical_remainder = remainder
        else:
            mathematical = remainder

    overflow = not _selected_range_contains(mathematical, bit_width, signedness)
    mask = (1 << bit_width) - 1
    minimum, maximum = _selected_range(bit_width, signedness)
    wrapped = overflow and overflow_behavior == "wrapping"
    saturated = overflow and overflow_behavior == "saturating"
    if overflow and overflow_behavior == "checked":
        result = None
        outcome = "overflow"
    else:
        selected_result = min(max(mathematical, minimum), maximum) if saturated else mathematical
        result = _representation(selected_result & mask, bit_width, signedness)
        outcome = "value"

    remainder_result = (
        _representation(mathematical_remainder & mask, bit_width, signedness)
        if mathematical_remainder is not None
        else None
    )
    warnings: list[str] = []
    if overflow:
        warnings.append(
            {
                "checked": "The mathematical result does not fit the selected width; checked arithmetic produced no machine value.",
                "wrapping": "The mathematical result overflowed and wrapped to the selected fixed width.",
                "saturating": "The mathematical result overflowed and was clamped to the selected fixed-width boundary.",
            }[overflow_behavior]
        )
    return {
        "status": "ok",
        "operation": "integer.machine_arithmetic",
        "kind": "machine_integer_arithmetic",
        "action": action,
        "bitWidth": bit_width,
        "signedness": signedness,
        "inputMode": input_mode,
        "overflowBehavior": overflow_behavior,
        "divisionMode": division_mode,
        "operands": [
            _representation(left_raw, bit_width, signedness),
            _representation(right_raw, bit_width, signedness),
        ],
        "mathematicalResult": str(mathematical),
        "mathematicalRemainder": (
            str(mathematical_remainder) if mathematical_remainder is not None else None
        ),
        "outcome": outcome,
        "overflow": overflow,
        "wrapped": wrapped,
        "saturated": saturated,
        "result": result,
        "remainder": remainder_result,
        "warnings": warnings,
    }


def _common(arguments: dict[str, Any]) -> tuple[int, str, str]:
    bit_width = integer_arg(arguments, "bitWidth", default=64, minimum=8, maximum=256)
    require(bit_width in _BIT_WIDTHS, "E_INPUT", "bitWidth must be one of: 8, 16, 32, 64, 128, 256")
    signedness = enum_arg(arguments, "signedness", _SIGNEDNESS, default="unsigned")
    input_mode = enum_arg(arguments, "inputMode", _INPUT_MODES, default="value")
    return bit_width, signedness, input_mode


def _decode_literal(
    arguments: dict[str, Any],
    name: str,
    *,
    bit_width: int,
    signedness: str,
    input_mode: str,
) -> int:
    literal = string_arg(arguments, name, max_length=260)
    require(_LITERAL.fullmatch(literal) is not None, "E_INPUT", f"{name} must be decimal text or use a 0b, 0o, or 0x prefix")
    negative = literal.startswith("-")
    unsigned_literal = literal[1:] if literal[:1] in "+-" else literal
    if unsigned_literal.lower().startswith("0b"):
        base, digits = 2, unsigned_literal[2:]
    elif unsigned_literal.lower().startswith("0o"):
        base, digits = 8, unsigned_literal[2:]
    elif unsigned_literal.lower().startswith("0x"):
        base, digits = 16, unsigned_literal[2:]
    else:
        base, digits = 10, unsigned_literal
    parsed = int(digits, base)
    value = -parsed if negative else parsed
    mask = (1 << bit_width) - 1

    if input_mode == "bits":
        require(not negative, "E_INPUT", f"{name} must be nonnegative when inputMode is bits")
        require(parsed <= mask, "E_LIMIT", f"{name} does not fit in {bit_width} bits")
        return parsed

    if signedness == "unsigned":
        require(0 <= value <= mask, "E_LIMIT", f"{name} does not fit the selected unsigned width")
    else:
        minimum = -(1 << (bit_width - 1))
        maximum = (1 << (bit_width - 1)) - 1
        require(minimum <= value <= maximum, "E_LIMIT", f"{name} does not fit the selected two's-complement width")
    return value & mask


def _decode_field_literal(arguments: dict[str, Any], name: str, field_width: int) -> int:
    value = _decode_unbounded_literal(arguments, name)
    require(value >= 0, "E_INPUT", f"{name} must be nonnegative")
    require(value < 1 << field_width, "E_LIMIT", f"{name} does not fit fieldWidth")
    return value


def _decode_unbounded_literal(arguments: dict[str, Any], name: str) -> int:
    literal = string_arg(arguments, name, max_length=260)
    require(_LITERAL.fullmatch(literal) is not None, "E_INPUT", f"{name} must be decimal text or use a 0b, 0o, or 0x prefix")
    negative = literal.startswith("-")
    unsigned_literal = literal[1:] if literal[:1] in "+-" else literal
    if unsigned_literal.lower().startswith("0b"):
        base, digits = 2, unsigned_literal[2:]
    elif unsigned_literal.lower().startswith("0o"):
        base, digits = 8, unsigned_literal[2:]
    elif unsigned_literal.lower().startswith("0x"):
        base, digits = 16, unsigned_literal[2:]
    else:
        base, digits = 10, unsigned_literal
    value = int(digits, base)
    return -value if negative else value


def _selected_range_contains(value: int, bit_width: int, signedness: str) -> bool:
    if signedness == "unsigned":
        return 0 <= value <= (1 << bit_width) - 1
    return -(1 << (bit_width - 1)) <= value <= (1 << (bit_width - 1)) - 1


def _selected_range(bit_width: int, signedness: str) -> tuple[int, int]:
    if signedness == "unsigned":
        return 0, (1 << bit_width) - 1
    return -(1 << (bit_width - 1)), (1 << (bit_width - 1)) - 1


def _divide(dividend: int, divisor: int, mode: str) -> tuple[int, int]:
    if mode == "floor":
        quotient = dividend // divisor
    elif mode == "euclidean":
        quotient = dividend // divisor if divisor > 0 else -(dividend // -divisor)
    else:
        quotient = abs(dividend) // abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
    remainder = dividend - divisor * quotient
    return quotient, remainder


def _selected_value(raw: int, bit_width: int, signedness: str) -> int:
    return _signed_value(raw, bit_width) if signedness == "twos_complement" else raw


def _signed_value(raw: int, bit_width: int) -> int:
    sign_bit = 1 << (bit_width - 1)
    return raw - (1 << bit_width) if raw & sign_bit else raw


def _reverse_chunks(raw: int, bit_width: int, chunk_width: int) -> int:
    chunk_mask = (1 << chunk_width) - 1
    result = 0
    for index in range(bit_width // chunk_width):
        chunk = (raw >> (index * chunk_width)) & chunk_mask
        result |= chunk << (bit_width - (index + 1) * chunk_width)
    return result


def _representation(raw: int, bit_width: int, signedness: str) -> dict[str, Any]:
    signed = _signed_value(raw, bit_width)
    selected = signed if signedness == "twos_complement" else raw
    return {
        "unsignedDecimal": str(raw),
        "signedDecimal": str(signed),
        "decimal": str(selected),
        "binary": f"{raw:0{bit_width}b}",
        "octal": f"{raw:0{(bit_width + 2) // 3}o}",
        "hexadecimal": f"{raw:0{bit_width // 4}X}",
        "character": _character(raw),
    }


def _character(raw: int) -> dict[str, Any]:
    valid_scalar = raw <= 0x10FFFF and not 0xD800 <= raw <= 0xDFFF
    if not valid_scalar:
        return {
            "validUnicodeScalar": False,
            "unicodeScalar": None,
            "unicodeName": None,
            "character": None,
            "ascii": False,
            "printable": False,
        }
    character = chr(raw)
    printable = character.isprintable()
    return {
        "validUnicodeScalar": True,
        "unicodeScalar": f"U+{raw:04X}",
        "unicodeName": unicodedata.name(character, None),
        "character": character if printable else None,
        "ascii": raw <= 0x7F,
        "printable": printable,
    }


def _result(
    *,
    operation: str,
    action: str,
    bit_width: int,
    signedness: str,
    input_mode: str,
    operands: list[dict[str, Any]],
    result: dict[str, Any],
    overflow: bool = False,
    wrapped: bool = False,
    truncated: bool = False,
    discarded_bits: str | None = None,
    count: int | None = None,
    effective_count: int | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "operation": operation,
        "kind": "programmer_integer",
        "action": action,
        "bitWidth": bit_width,
        "signedness": signedness,
        "inputMode": input_mode,
        "operands": operands,
        "result": result,
        "overflow": overflow,
        "wrapped": wrapped,
        "truncated": truncated,
        "discardedBits": discarded_bits,
        "count": count,
        "effectiveCount": effective_count,
        "warnings": warnings or [],
        **(metadata or {}),
    }
