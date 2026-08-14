from __future__ import annotations

import json
import math
import os
import resource
import sys
from typing import Any


def _apply_limits(payload: dict[str, Any]) -> None:
    cpu_budget_seconds = max(
        1,
        math.ceil(int(payload.get("timeoutMs", 10_000)) / 1000),
    )
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


def _execute_payload(payload: dict[str, Any], execute_direct: Any, calculator_error: type[Exception]) -> dict[str, Any]:
    _apply_limits(payload)
    try:
        result = execute_direct(payload["operation"], payload.get("arguments", {}))
        return {"ok": True, "result": result}
    except calculator_error as error:
        return {"ok": False, "error": error.as_dict()}
    except Exception as error:
        return {
            "ok": False,
            "error": {"code": "E_RUNTIME", "message": f"worker failed: {error}"},
        }
    finally:
        _clear_cpu_limit()


def _write_response(response: dict[str, Any]) -> None:
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stdout.flush()


def main() -> None:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    from .errors import CalculatorError
    from .runtime import execute_direct

    # Readiness means the common expression path is actually warm. SymPy keeps
    # a small amount of first-use initialization behind its imports; leaving
    # that work until after the ready signal made a 100 ms operation deadline
    # intermittently measure startup rather than calculation.
    execute_direct("expression.evaluate", {"expression": "0"})

    persistent = "--persistent" in sys.argv
    if persistent or not getattr(sys, "frozen", False):
        sys.stdout.write('{"ready":true}\n')
        sys.stdout.flush()
    if persistent:
        for line in sys.stdin:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                _write_response(
                    {"ok": False, "error": {"code": "E_INPUT", "message": "worker request must be JSON"}}
                )
                continue
            _write_response(_execute_payload(payload, execute_direct, CalculatorError))
        return

    payload = json.load(sys.stdin)
    _write_response(_execute_payload(payload, execute_direct, CalculatorError))
    # This is a single-request isolation worker. Interpreter teardown is not
    # part of the mathematical operation and can take longer than a 100 ms
    # deadline on a busy machine, so leave immediately after the response has
    # been durably handed to the parent pipe.
    os._exit(0)


if __name__ == "__main__":
    main()
