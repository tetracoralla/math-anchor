from __future__ import annotations

from typing import Any

from .errors import CalculatorError, require


def string_arg(
    arguments: dict[str, Any],
    name: str,
    *,
    default: str | None = None,
    max_length: int = 4096,
) -> str:
    value = arguments.get(name, default)
    require(isinstance(value, str), "E_INPUT", f"{name} must be a string")
    value = value.strip()
    require(bool(value), "E_INPUT", f"{name} must not be empty")
    require(len(value) <= max_length, "E_LIMIT", f"{name} is too long")
    return value


def integer_arg(
    arguments: dict[str, Any],
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(name, default)
    require(
        isinstance(value, int) and not isinstance(value, bool),
        "E_INPUT",
        f"{name} must be an integer",
    )
    require(minimum <= value <= maximum, "E_LIMIT", f"{name} must be between {minimum} and {maximum}")
    return value


def exact_integer_arg(
    arguments: dict[str, Any],
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(name)
    require(
        (isinstance(value, int) and not isinstance(value, bool))
        or (isinstance(value, str) and value.strip().lstrip("+-").isdigit()),
        "E_INPUT",
        f"{name} must be an integer or integer text",
    )
    parsed = int(value)
    require(minimum <= parsed <= maximum, "E_LIMIT", f"{name} must be between {minimum} and {maximum}")
    return parsed


def list_arg(
    arguments: dict[str, Any],
    name: str,
    *,
    minimum: int = 1,
    maximum: int = 100_000,
) -> list[Any]:
    value = arguments.get(name)
    require(isinstance(value, list), "E_INPUT", f"{name} must be an array")
    require(minimum <= len(value) <= maximum, "E_LIMIT", f"{name} must contain {minimum} to {maximum} items")
    return value


def variables_arg(arguments: dict[str, Any], *, maximum: int = 16) -> list[str]:
    values = list_arg(arguments, "variables", maximum=maximum)
    require(all(isinstance(value, str) for value in values), "E_INPUT", "variables must contain strings")
    normalized = [value.strip() for value in values]
    require(all(value.isidentifier() for value in normalized), "E_INPUT", "variables must be valid identifiers")
    require(len(set(normalized)) == len(normalized), "E_INPUT", "variables must not contain duplicates")
    return normalized


def enum_arg(
    arguments: dict[str, Any],
    name: str,
    choices: tuple[str, ...],
    *,
    default: str,
) -> str:
    value = arguments.get(name, default)
    if value not in choices:
        raise CalculatorError("E_INPUT", f"{name} must be one of: {', '.join(choices)}")
    return value
