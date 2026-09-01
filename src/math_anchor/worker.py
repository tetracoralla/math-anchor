from __future__ import annotations

import json
import math
import os
import resource
import sys
import time
from typing import Any

from .errors import error_payload

from .output_policy import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_RESULT_MODE,
    apply_output_policy,
)
from .transport_budget import MAX_REQUEST_BYTES


def _request_timeout_ms(payload: dict[str, Any]) -> int:
    # The parent validates timeoutMs against the public 100-30000 ms range
    # before dispatch; clamp defensively so a hand-built payload cannot ask
    # for an unbounded in-process timer.
    timeout_ms = payload.get("timeoutMs", 10_000)
    if isinstance(timeout_ms, int) and not isinstance(timeout_ms, bool):
        return max(100, min(timeout_ms, 30_000))
    return 10_000


def _apply_limits(payload: dict[str, Any]) -> None:
    cpu_budget_seconds = max(1, math.ceil(_request_timeout_ms(payload) / 1000))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    consumed_seconds = usage.ru_utime + usage.ru_stime
    # RLIMIT_CPU is an absolute lifetime limit, not a relative operation
    # budget. Imports and readiness warming have already consumed CPU here.
    soft_limit = math.ceil(consumed_seconds) + cpu_budget_seconds
    _, hard_limit = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (soft_limit, hard_limit))


def _clear_cpu_limit() -> None:
    _, hard_limit = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (hard_limit, hard_limit))


def _bounded_result(
    payload: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    return apply_output_policy(
        result,
        result_mode=payload.get("resultMode", DEFAULT_RESULT_MODE),
        max_output_bytes=payload.get("maxOutputBytes", DEFAULT_MAX_OUTPUT_BYTES),
    )


def _execute_payload(
    payload: dict[str, Any],
    execute_direct: Any,
    calculator_error: type[Exception],
) -> dict[str, Any]:
    _apply_limits(payload)
    try:
        result = execute_direct(
            payload["operation"],
            payload.get("arguments", {}),
            timeout_ms=_request_timeout_ms(payload),
        )
        return {"ok": True, "result": _bounded_result(payload, result)}
    except calculator_error as error:
        error_result = _bounded_result(
            payload,
            {"status": "error", "error": error.as_dict()},
        )
        return {"ok": False, "error": error_result["error"]}
    except Exception as error:
        error_result = _bounded_result(
            payload,
            {
                "status": "error",
                "error": error_payload("E_RUNTIME", f"worker failed: {error}"),
            },
        )
        return {"ok": False, "error": error_result["error"]}
    finally:
        _clear_cpu_limit()


def _write_response(response: dict[str, Any]) -> None:
    # The supervisor and worker share the host's monotonic clock. Stamp the
    # internal envelope before writing so a descheduled supervisor can tell an
    # in-budget completion from a response that actually crossed its deadline.
    # This field never enters the public operation result.
    response["_completedAtMonotonic"] = time.monotonic()
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _read_request_line() -> bytes | None:
    line = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
    if not line:
        return None
    if len(line) > MAX_REQUEST_BYTES:
        while line and not line.endswith(b"\n"):
            line = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
        raise ValueError(
            f"worker request exceeds the cumulative {MAX_REQUEST_BYTES}-byte transport limit"
        )
    return line


def _decode_request(line: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("worker request must be JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("worker request must be a JSON object")
    return payload


def _request_error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def main() -> None:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    from .errors import CalculatorError
    from .runtime import execute_direct

    persistent = "--persistent" in sys.argv
    if persistent or not getattr(sys, "frozen", False):
        sys.stdout.write('{"ready":true}\n')
        sys.stdout.flush()
    if persistent:
        while True:
            try:
                line = _read_request_line()
            except ValueError as error:
                _write_response(
                    {
                        "ok": False,
                        "error": {
                            "code": "E_LIMIT",
                            "message": str(error),
                        },
                    }
                )
                continue
            if line is None:
                break
            try:
                payload = _decode_request(line)
            except ValueError as error:
                _write_response(_request_error("E_INPUT", str(error)))
                continue
            _write_response(_execute_payload(payload, execute_direct, CalculatorError))
        return

    try:
        line = _read_request_line()
    except ValueError as error:
        _write_response(_request_error("E_LIMIT", str(error)))
        return
    if line is None:
        raise SystemExit("worker request is unavailable")
    try:
        payload = _decode_request(line)
    except ValueError as error:
        _write_response(_request_error("E_INPUT", str(error)))
        return
    _write_response(_execute_payload(payload, execute_direct, CalculatorError))
    # This is a single-request isolation worker. Interpreter teardown is not
    # part of the mathematical operation and can take longer than a 100 ms
    # deadline on a busy machine, so leave immediately after the response has
    # been durably handed to the parent pipe.
    os._exit(0)


if __name__ == "__main__":
    main()
