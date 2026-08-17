from __future__ import annotations

import json
import sys
from typing import Any

from .currency import ECBRateService, currency_convert
from .errors import CalculatorError
from .runtime import (
    EVALUATION_TIMEOUT_SECONDS,
    ensure_mpmath_default_precision,
    in_process_evaluation_timeout,
)
from .operations.data import units_convert
from .operations.expression import evaluate


_CURRENCY_SERVICE = ECBRateService()


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}


def _handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        return _error("E_INPUT", "request must be an object")
    request_id = request.get("id")
    if not isinstance(request_id, str) or not request_id:
        return _error("E_INPUT", "request id must be a non-empty string")
    try:
        with in_process_evaluation_timeout(EVALUATION_TIMEOUT_SECONDS):
            operation = request.get("operation", "expression.evaluate")
            if operation == "expression.evaluate":
                arguments = {
                    "expression": request.get("expression"),
                    "precision": request.get("precision", 16),
                }
                result = evaluate(arguments)
            elif operation == "units.convert":
                arguments = {
                    "value": request.get("value"),
                    "fromUnit": request.get("fromUnit"),
                    "toUnit": request.get("toUnit"),
                    "precision": request.get("precision", 12),
                }
                result = units_convert(arguments)
            elif operation == "currency.convert":
                arguments = {
                    "value": request.get("value"),
                    "fromCurrency": request.get("fromCurrency"),
                    "toCurrency": request.get("toCurrency"),
                    "precision": request.get("precision", 12),
                    "forceRefresh": request.get("forceRefresh", False),
                }
                result = currency_convert(arguments, service=_CURRENCY_SERVICE)
            else:
                raise CalculatorError("E_OPERATION", f"unsupported app operation: {operation}")
            return {"id": request_id, **result}
    except CalculatorError as error:
        return {"id": request_id, "status": "error", "error": error.as_dict()}
    except Exception as error:
        return {
            "id": request_id,
            **_error("E_RUNTIME", f"app runtime failed: {error}"),
        }
    finally:
        ensure_mpmath_default_precision()


def main() -> None:
    sys.stdout.write('{"status":"ready"}\n')
    sys.stdout.flush()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = _handle(request)
        except json.JSONDecodeError as error:
            response = _error("E_INPUT", f"invalid JSON: {error.msg}")
        except Exception as error:
            response = _error("E_RUNTIME", f"app runtime failed: {error}")
        json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
