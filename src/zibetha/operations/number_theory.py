from __future__ import annotations

import math
from typing import Any

import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import typed_scalar_result
from ..validation import enum_arg, exact_integer_arg, integer_arg, list_arg


_MAX_INTEGER = 9_007_199_254_740_991


def factorization(arguments: dict[str, Any]) -> dict[str, Any]:
    value = exact_integer_arg(arguments, "value", minimum=-_MAX_INTEGER, maximum=_MAX_INTEGER)
    require(value != 0, "E_DOMAIN", "zero does not have a finite prime factorization")
    magnitude = abs(value)
    factors = sp.factorint(magnitude) if magnitude > 1 else {}
    return {
        "status": "ok",
        "operation": "integer.factorization",
        "kind": "factorization",
        "value": str(value),
        "sign": -1 if value < 0 else 1,
        "isPrime": bool(value > 1 and sp.isprime(value)),
        "factors": [
            {"prime": str(prime), "exponent": int(exponent)}
            for prime, exponent in sorted(factors.items())
        ],
        "warnings": [],
    }


def gcd_lcm(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_values = list_arg(arguments, "values", maximum=128)
    values = [
        _parse_integer(value, name=f"values[{index}]")
        for index, value in enumerate(raw_values)
    ]
    gcd_value = 0
    lcm_value = 1
    for value in values:
        gcd_value = math.gcd(gcd_value, value)
        lcm_value = math.lcm(lcm_value, value)
    return {
        "status": "ok",
        "operation": "integer.gcd_lcm",
        "kind": "gcd_lcm",
        "count": len(values),
        "gcd": str(abs(gcd_value)),
        "lcm": str(abs(lcm_value)),
        "warnings": [],
    }


def modular(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", ("remainder", "power", "inverse"), default="remainder")
    value = exact_integer_arg(arguments, "value", minimum=-_MAX_INTEGER, maximum=_MAX_INTEGER)
    modulus = exact_integer_arg(arguments, "modulus", minimum=2, maximum=_MAX_INTEGER)
    if action == "remainder":
        result = value % modulus
    elif action == "power":
        exponent = integer_arg(arguments, "exponent", default=0, minimum=0, maximum=1_000_000_000)
        result = pow(value, exponent, modulus)
    else:
        try:
            result = pow(value, -1, modulus)
        except ValueError as error:
            raise CalculatorError("E_DOMAIN", "modular inverse does not exist for these inputs") from error
    return typed_scalar_result(
        "integer.modular",
        "modular",
        sp.Integer(result),
        16,
        action=action,
        modulus=str(modulus),
    )


def _parse_integer(value: Any, *, name: str) -> int:
    require(
        (isinstance(value, int) and not isinstance(value, bool))
        or (isinstance(value, str) and value.strip().lstrip("+-").isdigit()),
        "E_INPUT",
        f"{name} must be an integer or integer text",
    )
    parsed = int(value)
    require(abs(parsed) <= _MAX_INTEGER, "E_LIMIT", f"{name} is outside the supported range")
    return parsed
