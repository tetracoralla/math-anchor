#!/usr/bin/env python3
"""Execute one structured Math Anchor invocation for the direct-host evaluator."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from math_anchor.sandbox import run_operation  # noqa: E402


MAX_REQUEST_BYTES = 256 * 1024


def _runtime(request: dict[str, Any]) -> dict[str, Any]:
    runtime = {
        "driver": request["driverRef"],
        "provider": request["providerRef"],
        "target": request["target"],
    }
    if "targetCapability" in request:
        runtime["capability"] = request["targetCapability"]
    if "targetProcedure" in request:
        runtime["procedure"] = request["targetProcedure"]
    return runtime


def _response(
    request: dict[str, Any],
    *,
    status: str,
    answer: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "schemaVersion": "openadam.agent-tool-eval.direct-driver-result.v0.1",
        "executionMode": "direct-host",
        "runId": request["runId"],
        "taskId": request["task"]["id"],
        "repeat": request["repeat"],
        "status": status,
        "runtime": _runtime(request),
    }
    if status == "success":
        response["answer"] = answer
    else:
        response["error"] = error
    return response


def _provider_error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {"code": code, "message": message[:2000], "retryable": retryable}


def main() -> int:
    request_bytes = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(request_bytes) > MAX_REQUEST_BYTES:
        print("direct request exceeded the driver ceiling", file=sys.stderr)
        return 2
    try:
        request = json.loads(request_bytes)
        invocation = request["task"]["invocation"]
        operation_id = invocation["operationId"]
        invocation_input = invocation["input"]
        if operation_id != "math.run" or not isinstance(invocation_input, dict):
            response = _response(
                request,
                status="error",
                error=_provider_error("E_INPUT", f"unsupported direct operation: {operation_id!r}"),
            )
        else:
            operation = invocation_input.get("operation")
            arguments = invocation_input.get("arguments")
            if not isinstance(operation, str) or not isinstance(arguments, dict):
                response = _response(
                    request,
                    status="error",
                    error=_provider_error("E_INPUT", "math.run requires operation and arguments"),
                )
            else:
                result = run_operation(
                    operation,
                    arguments,
                    timeout_ms=request["budget"]["timeoutMs"],
                )
                if result.get("status") == "error":
                    provider = result.get("error", {})
                    response = _response(
                        request,
                        status="error",
                        error=_provider_error(
                            str(provider.get("code", "E_RUNTIME")),
                            str(provider.get("message", "Math Anchor rejected the invocation")),
                            retryable=bool(provider.get("retryable", False)),
                        ),
                    )
                else:
                    response = _response(request, status="success", answer=result)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"invalid direct driver request: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # pragma: no cover - evaluator records the stderr digest
        print(f"unexpected direct driver failure: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
