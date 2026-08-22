"""In-process evaluation bound (finding F-5, fixed).

Sandboxed routes (MCP math.run/math.batch and the CLI) already run every
operation in a worker with a parent-side wall-clock deadline and RLIMIT_CPU.
The gap was direct in-process execution: runtime.execute_direct (used by
tests and any direct consumer) and app_runtime._handle (the JSON-lines app
protocol) evaluated handlers with no bound, so a pathological expression
could hang the process forever. Both sites now evaluate under a SIGALRM
interval timer that raises E_TIMEOUT.

Tests assert OUTCOMES (E_TIMEOUT returned, guard skipped off the main
thread, alarm state restored), never elapsed milliseconds. The Unix caveat
is real and documented: SIGALRM can only be armed on the process main
thread; in other threads the guard is skipped and evaluation runs without
this in-process bound (still bounded by RLIMIT_CPU in worker processes).
"""

from __future__ import annotations

import signal
import threading
import time

import pytest

from math_anchor import app_runtime
from math_anchor import runtime
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct, in_process_evaluation_timeout
from math_anchor.sandbox import DEFAULT_TIMEOUT_MS


def test_in_process_bound_matches_the_sandbox_default() -> None:
    assert runtime.EVALUATION_TIMEOUT_SECONDS == DEFAULT_TIMEOUT_MS / 1000


def test_pathological_in_process_evaluation_returns_e_timeout(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "EVALUATION_TIMEOUT_SECONDS", 0.5)
    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "expression.evaluate",
            {"expression": "floor(gamma(exp(7)))", "precision": 16},
        )
    assert raised.value.code == "E_TIMEOUT"
    assert raised.value.details == {"timeoutMs": 500}


def test_app_runtime_handle_is_bounded_too(monkeypatch) -> None:
    # app_runtime binds the constant into its own namespace at import time.
    monkeypatch.setattr(app_runtime, "EVALUATION_TIMEOUT_SECONDS", 0.5)
    response = app_runtime._handle({"id": "t1", "operation": "expression.evaluate",
                                    "expression": "floor(gamma(exp(7)))", "precision": 16})
    assert response["id"] == "t1"
    assert response["status"] == "error"
    assert response["error"]["code"] == "E_TIMEOUT"


def test_normal_operations_still_succeed_under_the_guard(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "EVALUATION_TIMEOUT_SECONDS", 0.5)
    result = execute_direct("expression.evaluate", {"expression": "6 * 7", "precision": 16})
    assert result["exact"] == "42"
    response = app_runtime._handle({"id": "t2", "expression": "1 + 1"})
    assert response["exact"] == "2"


def test_guard_restores_previous_alarm_state() -> None:
    def marker(signum, frame):  # pragma: no cover - never fires
        raise AssertionError("restored timer must not fire during the test")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, marker)
    signal.setitimer(signal.ITIMER_REAL, 60.0)
    try:
        execute_direct("expression.evaluate", {"expression": "2 + 2", "precision": 16})
        assert signal.getsignal(signal.SIGALRM) is marker
        remaining = signal.getitimer(signal.ITIMER_REAL)[0]
        assert 0.0 < remaining <= 60.0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


def test_guard_is_skipped_off_the_main_thread() -> None:
    outcomes: list[str] = []

    def work() -> None:
        with in_process_evaluation_timeout(0.2):
            outcomes.append("ran")

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert outcomes == ["ran"]


def test_guard_reports_the_budget_it_actually_armed() -> None:
    # Negative regression: the timeout handler used a process-global default,
    # so direct context-manager callers received a false 10000 ms detail even
    # when they had armed a much smaller bound.
    with pytest.raises(CalculatorError) as raised:
        with in_process_evaluation_timeout(0.02):
            time.sleep(0.1)
    assert raised.value.code == "E_TIMEOUT"
    assert raised.value.details == {"timeoutMs": 20}


def test_nested_guard_does_not_postpone_or_replace_an_outer_deadline() -> None:
    class OuterDeadline(Exception):
        pass

    def outer_handler(signum, frame):
        raise OuterDeadline

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, outer_handler)
    signal.setitimer(signal.ITIMER_REAL, 0.05)
    try:
        with pytest.raises(OuterDeadline):
            with in_process_evaluation_timeout(0.5):
                time.sleep(0.2)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_execute_direct_honors_an_explicit_caller_budget() -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "expression.evaluate",
            {"expression": "floor(gamma(exp(7)))", "precision": 16},
            timeout_ms=200,
        )
    assert raised.value.code == "E_TIMEOUT"
    assert raised.value.details == {"timeoutMs": 200}


@pytest.mark.parametrize("timeout_ms", [True, 99, 30_001, "1000"])
def test_execute_direct_rejects_invalid_explicit_budgets(timeout_ms) -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "expression.evaluate",
            {"expression": "6*7"},
            timeout_ms=timeout_ms,
        )
    assert raised.value.code == "E_LIMIT"


def test_explicit_caller_budget_replaces_the_default_constant(monkeypatch) -> None:
    # Negative regression: the sandboxed worker forwards each request's
    # timeoutMs here. If the explicit budget stopped overriding the default
    # constant, every budget above ten seconds would be silently cut at it.
    monkeypatch.setattr(runtime, "EVALUATION_TIMEOUT_SECONDS", 0.2)
    result = execute_direct(
        "expression.evaluate",
        {"expression": "floor(gamma(exp(7)))", "precision": 16},
        timeout_ms=30_000,
    )
    assert result["status"] == "ok"
