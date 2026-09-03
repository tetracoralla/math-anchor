from __future__ import annotations

from typing import Any

from .catalog_search import (
    MAX_CATEGORY_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    search_operations,
)
from .errors import CalculatorError
from .operation_specs import ALL_SPECS
from .operation_specs.shared import MAX_OPERATION_ID_LENGTH


OPERATIONS = {spec.id: spec for spec in ALL_SPECS}


def describe_operation(operation: str) -> dict[str, Any]:
    if not isinstance(operation, str) or not operation:
        raise CalculatorError("E_INPUT", "operation must be a non-empty string")
    if len(operation) > MAX_OPERATION_ID_LENGTH:
        raise CalculatorError(
            "E_LIMIT",
            f"operation must contain at most {MAX_OPERATION_ID_LENGTH} characters",
        )
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError(
            "E_OPERATION",
            "unknown operation id",
            {"available": sorted(OPERATIONS)},
        )
    return {"status": "ok", "operation": spec.describe()}


def operation_schemas() -> list[tuple[str, dict[str, Any]]]:
    return [(spec.id, spec.input_schema) for spec in ALL_SPECS]
