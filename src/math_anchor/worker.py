from __future__ import annotations

import json
import math
import os
import resource
import sys
import threading
import time
from typing import Any

from .output_policy import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_RESULT_MODE,
    apply_output_policy,
)


UNIT_REGISTRY_WARM_IDLE_SECONDS = 0.5


class _RequestActivity:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.active = False
        self.last_activity_at = time.monotonic()

    def begin(self) -> None:
        with self.condition:
            self.active = True
            self.last_activity_at = time.monotonic()
            self.condition.notify_all()

    def end(self) -> None:
        with self.condition:
            self.active = False
            self.last_activity_at = time.monotonic()
            self.condition.notify_all()

    def wait_until_idle_for(self, idle_seconds: float) -> None:
        with self.condition:
            while True:
                elapsed = time.monotonic() - self.last_activity_at
                if not self.active and elapsed >= idle_seconds:
                    return
                timeout = None if self.active else max(0.0, idle_seconds - elapsed)
                self.condition.wait(timeout=timeout)


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
                "error": {"code": "E_RUNTIME", "message": f"worker failed: {error}"},
            },
        )
        return {"ok": False, "error": error_result["error"]}
    finally:
        _clear_cpu_limit()


def _write_response(response: dict[str, Any]) -> None:
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _warm_unit_registries_in_background(
    request_activity: _RequestActivity,
) -> None:
    # Pint registry construction (~150 ms each) stays lazy so readiness is
    # cheap. Wait for a real idle interval before building both registries so
    # a startup burst of cheap expressions never competes with ~300 ms of
    # background parsing. Any request restarts the idle interval; a unit call
    # arriving sooner simply uses the same locked lazy constructors itself.
    from .operations.data import warm_unit_registries

    def warm_after_idle() -> None:
        request_activity.wait_until_idle_for(UNIT_REGISTRY_WARM_IDLE_SECONDS)
        warm_unit_registries()

    threading.Thread(
        target=warm_after_idle,
        name="calculator-worker-unit-warm",
        daemon=True,
    ).start()


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
        request_activity = _RequestActivity()
        _warm_unit_registries_in_background(request_activity)
        for line in sys.stdin:
            request_activity.begin()
            try:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    _write_response(
                        {
                            "ok": False,
                            "error": {
                                "code": "E_INPUT",
                                "message": "worker request must be JSON",
                            },
                        }
                    )
                    continue
                _write_response(_execute_payload(payload, execute_direct, CalculatorError))
            finally:
                request_activity.end()
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
