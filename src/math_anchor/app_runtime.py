from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import sys
import threading
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

# A currency conversion may wait on the ECB network feed for several seconds.
# Serving it on the stdin loop would freeze every later expression and unit
# request behind the fetch, so those requests run on a small executor while
# the loop keeps answering local operations. Responses are matched by request
# id on the client side, so completion order does not matter.
_CURRENCY_EXECUTOR = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="math-anchor-currency"
)
_STDOUT_LOCK = threading.Lock()


def _error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}


def _handle(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        return _error("E_INPUT", "request must be an object")
    request_id = request.get("id")
    if not isinstance(request_id, str) or not request_id:
        return _error("E_INPUT", "request id must be a non-empty string")
    try:
        operation = request.get("operation", "expression.evaluate")
        if operation == "currency.convert":
            # Currency work runs concurrently with the local calculation loop.
            # It uses Decimal and provider I/O only, so it must not reset the
            # process-global mpmath precision while an expression is running.
            arguments = {
                "value": request.get("value"),
                "fromCurrency": request.get("fromCurrency"),
                "toCurrency": request.get("toCurrency"),
                "precision": request.get("precision", 12),
                "forceRefresh": request.get("forceRefresh", False),
            }
            result = currency_convert(arguments, service=_CURRENCY_SERVICE)
        else:
            try:
                with in_process_evaluation_timeout(EVALUATION_TIMEOUT_SECONDS):
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
                    else:
                        raise CalculatorError(
                            "E_OPERATION", f"unsupported app operation: {operation}"
                        )
            finally:
                ensure_mpmath_default_precision()
        return {"id": request_id, **result}
    except CalculatorError as error:
        return {"id": request_id, "status": "error", "error": error.as_dict()}
    except Exception as error:
        return {
            "id": request_id,
            **_error("E_RUNTIME", f"app runtime failed: {error}"),
        }


def _write_response(response: dict[str, Any]) -> None:
    line = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    with _STDOUT_LOCK:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def _respond(request: Any) -> None:
    try:
        response = _handle(request)
    except Exception as error:
        response = _error("E_RUNTIME", f"app runtime failed: {error}")
    _write_response(response)


def _dispatch(request: Any) -> None:
    if isinstance(request, dict) and request.get("operation") == "currency.convert":
        _CURRENCY_EXECUTOR.submit(_respond, request)
        return
    _respond(request)


def main() -> None:
    with _STDOUT_LOCK:
        sys.stdout.write('{"status":"ready"}\n')
        sys.stdout.flush()
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            _write_response(_error("E_INPUT", f"invalid JSON: {error.msg}"))
            continue
        _dispatch(request)


if __name__ == "__main__":
    main()
