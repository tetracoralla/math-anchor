from __future__ import annotations

from decimal import Decimal
from typing import Any


def _exact_integer_text(value: int) -> str:
    try:
        return str(value)
    except ValueError:
        # Python 3.11 limits decimal int-to-string conversion process-wide.
        # Decimal renders the already-bounded computed integer without
        # weakening that interpreter safety limit for later request parsing.
        return format(Decimal(value), "f")


def _approximate_integer_text(value: int, exact: str, precision: int) -> str:
    digits = len(exact.lstrip("-"))
    if digits <= precision:
        return f"{exact}.{'0' * (precision - digits)}"
    return format(Decimal(value), f".{precision - 1}E").replace("E", "e")


def approximate_integer(value: int, precision: int) -> str:
    """Render the same significant-digit lane without importing SymPy."""
    if value == 0:
        return "0"
    return _approximate_integer_text(value, _exact_integer_text(value), precision)


def exact_integer_result(
    operation: str,
    kind: str,
    value: int,
    precision: int = 16,
    **metadata: Any,
) -> dict[str, Any]:
    exact = _exact_integer_text(value)
    return {
        "status": "ok",
        "operation": operation,
        "kind": kind,
        "exact": exact,
        "approx": "0" if value == 0 else _approximate_integer_text(value, exact, precision),
        "precision": precision,
        "warnings": [],
        **metadata,
    }
