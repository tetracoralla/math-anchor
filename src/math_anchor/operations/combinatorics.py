from __future__ import annotations

import math
from typing import Any

import sympy as sp

from ..errors import require
from ..formatting import typed_scalar_result
from ..validation import enum_arg, integer_arg, list_arg


_MAX_COUNT = 5_000


def count(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(arguments, "action", ("binomial", "permutations", "multinomial"), default="binomial")
    if action == "multinomial":
        raw_counts = list_arg(arguments, "counts", minimum=1, maximum=128)
        require(
            all(isinstance(value, int) and not isinstance(value, bool) for value in raw_counts),
            "E_INPUT",
            "counts must contain integers",
        )
        require(all(value >= 0 for value in raw_counts), "E_INPUT", "counts must be nonnegative")
        total = sum(raw_counts)
        require(total <= _MAX_COUNT, "E_LIMIT", f"counts must sum to at most {_MAX_COUNT}")
        result = math.factorial(total)
        for value in raw_counts:
            result //= math.factorial(value)
    else:
        n = integer_arg(arguments, "n", default=0, minimum=0, maximum=_MAX_COUNT)
        k = integer_arg(arguments, "k", default=0, minimum=0, maximum=_MAX_COUNT)
        require(k <= n, "E_DOMAIN", "k must not exceed n")
        result = math.comb(n, k) if action == "binomial" else math.perm(n, k)
    return typed_scalar_result(
        "combinatorics.count",
        "integer_count",
        sp.Integer(result),
        16,
        action=action,
    )
