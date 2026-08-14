from __future__ import annotations

from typing import Any

from .catalog import OPERATIONS
from .contracts import validate_operation_arguments, validate_result
from .errors import CalculatorError


def execute_direct(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError("E_OPERATION", f"unknown operation: {operation}")
    if not isinstance(arguments, dict):
        raise CalculatorError("E_INPUT", "arguments must be an object")
    validate_operation_arguments(operation, spec.input_schema, arguments)
    try:
        result = spec.handler(arguments)
        validate_result(result)
        return result
    except CalculatorError:
        raise
    except Exception as error:
        raise CalculatorError("E_RUNTIME", f"operation failed: {error}") from error
