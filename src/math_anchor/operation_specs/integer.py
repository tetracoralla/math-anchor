from __future__ import annotations

from .shared import (
    OperationSpec,
    _EXACT_INTEGER,
    _LARGE_INTEGER_TEXT,
    _POSITIVE_MODULUS,
    _PROGRAMMER_BIT_WIDTH,
    _PROGRAMMER_COUNT,
    _PROGRAMMER_FIELD_WIDTH,
    _PROGRAMMER_INPUT_MODE,
    _PROGRAMMER_LITERAL,
    _PROGRAMMER_OFFSET,
    _PROGRAMMER_SIGNEDNESS,
    _object,
    number_theory,
    programmer,
    rounding,
)


SPECS = (
    OperationSpec(
        id="integer.factorization",
        category="integer",
        summary="Test primality and return an exact prime factorization.",
        description="Factor one bounded nonzero integer into ordered prime powers and report its sign and primality.",
        input_schema=_object({"value": _EXACT_INTEGER}, ("value",)),
        examples=({"value": 360}, {"value": "9007199254740991"}),
        handler=number_theory.factorization,
        keywords=("prime factors", "is prime", "factor integer", "质因数分解", "素数判断", "整数分解"),
    ),
    OperationSpec(
        id="integer.gcd_lcm",
        category="integer",
        summary="Compute the exact GCD and LCM of integers.",
        description="Return the nonnegative greatest common divisor and least common multiple for one bounded integer list.",
        input_schema=_object(
            {
                "values": {
                    "type": "array",
                    "items": _EXACT_INTEGER,
                    "minItems": 1,
                    "maxItems": 128,
                }
            },
            ("values",),
        ),
        examples=({"values": [12, 18, 30]},),
        handler=number_theory.gcd_lcm,
        keywords=("greatest common divisor", "least common multiple", "gcd", "lcm", "最大公约数", "最小公倍数"),
    ),
    OperationSpec(
        id="integer.modular",
        category="integer",
        summary="Compute a modular remainder, power, or inverse.",
        description="Perform one explicit bounded modular arithmetic operation and return an exact canonical residue.",
        input_schema={
            "oneOf": [
                _object(
                    {"action": {"const": "remainder"}, "value": _EXACT_INTEGER, "modulus": _POSITIVE_MODULUS},
                    ("action", "value", "modulus"),
                ),
                _object(
                    {
                        "action": {"const": "power"},
                        "value": _EXACT_INTEGER,
                        "exponent": {"type": "integer", "minimum": 0, "maximum": 1_000_000_000},
                        "modulus": _POSITIVE_MODULUS,
                    },
                    ("action", "value", "exponent", "modulus"),
                ),
                _object(
                    {"action": {"const": "inverse"}, "value": _EXACT_INTEGER, "modulus": _POSITIVE_MODULUS},
                    ("action", "value", "modulus"),
                ),
            ]
        },
        examples=(
            {"action": "power", "value": 7, "exponent": 128, "modulus": 13},
            {"action": "inverse", "value": 3, "modulus": 11},
        ),
        handler=number_theory.modular,
        keywords=("modulo", "modular inverse", "modular exponent", "模运算", "模逆", "模幂"),
    ),
    OperationSpec(
        id="integer.divide",
        category="integer",
        summary="Divide exact integers using truncating, floor, or Euclidean quotient-and-remainder semantics.",
        description="Return an exact quotient and remainder under one explicit sign convention, preserving dividend = divisor * quotient + remainder.",
        input_schema=_object(
            {
                "dividend": _LARGE_INTEGER_TEXT,
                "divisor": _LARGE_INTEGER_TEXT,
                "divisionMode": {
                    "type": "string",
                    "enum": ["truncating", "floor", "euclidean"],
                    "default": "truncating",
                },
            },
            ("dividend", "divisor"),
        ),
        examples=(
            {"dividend": "-99", "divisor": "10", "divisionMode": "truncating"},
            {"dividend": "-99", "divisor": "10", "divisionMode": "floor"},
            {"dividend": "-99", "divisor": "-10", "divisionMode": "euclidean"},
        ),
        handler=rounding.divide_integer,
        keywords=("integer division", "quotient", "remainder", "truncate division", "floor division", "Euclidean division", "整除", "商和余数", "截断除法", "欧几里得除法"),
    ),
    OperationSpec(
        id="integer.represent",
        category="integer",
        summary="Render one fixed-width integer in binary, octal, decimal, hexadecimal, and character forms.",
        description="Interpret explicit integer text as a bounded mathematical value or raw bit pattern, then expose unsigned and two's-complement meanings without silent wrapping.",
        input_schema=_object(
            {
                "value": _PROGRAMMER_LITERAL,
                "bitWidth": _PROGRAMMER_BIT_WIDTH,
                "signedness": _PROGRAMMER_SIGNEDNESS,
                "inputMode": _PROGRAMMER_INPUT_MODE,
            },
            ("value",),
        ),
        examples=(
            {"value": "0xFF", "bitWidth": 8, "signedness": "twos_complement", "inputMode": "bits"},
            {"value": "375", "bitWidth": 64},
        ),
        handler=programmer.represent,
        keywords=("binary", "octal", "hexadecimal", "base conversion", "two's complement", "ASCII", "Unicode", "进制转换", "二进制", "十六进制", "补码", "字符编码"),
    ),
    OperationSpec(
        id="integer.bitwise",
        category="integer",
        summary="Run one explicit fixed-width bitwise, shift, rotate, negate, or chunk-reversal operation.",
        description="Apply machine-integer semantics with an explicit width and signed interpretation, returning every overflow, wrap, truncation, discarded bit, base rendering, and character interpretation.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["and", "or", "xor", "nor"]},
                        "left": _PROGRAMMER_LITERAL,
                        "right": _PROGRAMMER_LITERAL,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "left", "right"),
                ),
                _object(
                    {
                        "action": {
                            "type": "string",
                            "enum": [
                                "not",
                                "negate",
                                "count_ones",
                                "leading_zeros",
                                "trailing_zeros",
                                "reverse_bits",
                                "reverse_bytes",
                                "reverse_words",
                            ],
                        },
                        "value": _PROGRAMMER_LITERAL,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "value"),
                ),
                _object(
                    {
                        "action": {"const": "extract"},
                        "value": _PROGRAMMER_LITERAL,
                        "offset": _PROGRAMMER_OFFSET,
                        "fieldWidth": _PROGRAMMER_FIELD_WIDTH,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "value", "offset", "fieldWidth"),
                ),
                _object(
                    {
                        "action": {"const": "insert"},
                        "value": _PROGRAMMER_LITERAL,
                        "field": _PROGRAMMER_LITERAL,
                        "offset": _PROGRAMMER_OFFSET,
                        "fieldWidth": _PROGRAMMER_FIELD_WIDTH,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "value", "field", "offset", "fieldWidth"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["align_up", "align_down"]},
                        "value": _PROGRAMMER_LITERAL,
                        "alignment": _PROGRAMMER_LITERAL,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "value", "alignment"),
                ),
                _object(
                    {
                        "action": {
                            "type": "string",
                            "enum": [
                                "shift_left",
                                "logical_shift_right",
                                "arithmetic_shift_right",
                                "rotate_left",
                                "rotate_right",
                            ],
                        },
                        "value": _PROGRAMMER_LITERAL,
                        "count": _PROGRAMMER_COUNT,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                    },
                    ("action", "value"),
                ),
            ]
        },
        examples=(
            {"action": "and", "left": "0xF0", "right": "0b10101010", "bitWidth": 8, "inputMode": "bits"},
            {"action": "rotate_left", "value": "0x81", "count": 1, "bitWidth": 8, "inputMode": "bits"},
            {"action": "reverse_words", "value": "0xABCD1234", "bitWidth": 32, "inputMode": "bits"},
        ),
        handler=programmer.bitwise,
        keywords=("bitwise", "AND", "OR", "XOR", "NOR", "NOT", "shift", "rotate", "popcount", "leading zeros", "trailing zeros", "bit field", "alignment", "byte flip", "word flip", "位运算", "移位", "循环移位", "位域", "内存对齐", "字节翻转"),
    ),
    OperationSpec(
        id="integer.machine_arithmetic",
        category="integer",
        summary="Simulate checked, wrapping, or saturating fixed-width machine arithmetic.",
        description="Apply explicit width, signedness, input interpretation, overflow behavior, and division convention while keeping the unbounded mathematical result separate from the machine result.",
        input_schema={
            "oneOf": [
                _object(
                    {
                        "action": {"type": "string", "enum": ["add", "subtract", "multiply"]},
                        "left": _PROGRAMMER_LITERAL,
                        "right": _PROGRAMMER_LITERAL,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                        "overflowBehavior": {
                            "type": "string",
                            "enum": ["checked", "wrapping", "saturating"],
                            "default": "checked",
                        },
                    },
                    ("action", "left", "right"),
                ),
                _object(
                    {
                        "action": {"type": "string", "enum": ["divide", "remainder"]},
                        "left": _PROGRAMMER_LITERAL,
                        "right": _PROGRAMMER_LITERAL,
                        "bitWidth": _PROGRAMMER_BIT_WIDTH,
                        "signedness": _PROGRAMMER_SIGNEDNESS,
                        "inputMode": _PROGRAMMER_INPUT_MODE,
                        "overflowBehavior": {
                            "type": "string",
                            "enum": ["checked", "wrapping", "saturating"],
                            "default": "checked",
                        },
                        "divisionMode": {
                            "type": "string",
                            "enum": ["truncating", "floor", "euclidean"],
                            "default": "truncating",
                        },
                    },
                    ("action", "left", "right"),
                ),
            ]
        },
        examples=(
            {"action": "add", "left": "127", "right": "1", "bitWidth": 8, "signedness": "twos_complement", "overflowBehavior": "checked"},
            {"action": "multiply", "left": "200", "right": "2", "bitWidth": 8, "overflowBehavior": "saturating"},
            {"action": "divide", "left": "-99", "right": "10", "bitWidth": 16, "signedness": "twos_complement", "divisionMode": "euclidean"},
        ),
        handler=programmer.machine_arithmetic,
        keywords=("machine integer", "checked arithmetic", "wrapping", "saturating", "fixed width add", "overflow", "机器整数", "溢出", "环绕", "饱和算术"),
    ),
)

SPECS_BY_ID = {spec.id: spec for spec in SPECS}
