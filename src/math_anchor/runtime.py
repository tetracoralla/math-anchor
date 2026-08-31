from __future__ import annotations

import signal
import time
from contextlib import contextmanager
from typing import Any, Iterator

import mpmath

from .catalog import OPERATIONS
from .contracts import validate_operation_arguments, validate_result
from .errors import CalculatorError
from .research_contract import apply_research_contract

# Mirrors sandbox.DEFAULT_TIMEOUT_MS (10_000 ms) so direct in-process callers
# observe the same bound as the sandboxed worker pool. Kept as a literal here
# to avoid importing the sandbox (and its psutil dependency) into every worker
# and app-runtime process; tests pin the two constants together. Sandboxed
# workers pass each request's own timeoutMs to execute_direct, so a budget
# above the default is honored instead of silently cut at ten seconds.
EVALUATION_TIMEOUT_SECONDS = 10.0

# Math Anchor only changes mpmath precision inside workdps/workprec contexts
# (src/math_anchor/operations/*), so the global value between operations is always
# the mpmath default. An aborted astronomical evaluation can instead leave it
# at an unrepresentable huge value (SymPy raises OverflowError inside
# workprec's own restore logic), which then poisons every later evaluation in
# the process with "int too large to convert to float". 10_000 bits is far
# above the largest precision any operation can legitimately request.
_MPMATH_PRECISION_CEILING = 10_000
_DEFAULT_MPMATH_PRECISION = 53


def ensure_mpmath_default_precision() -> None:
    if mpmath.mp.prec > _MPMATH_PRECISION_CEILING:
        mpmath.mp.prec = _DEFAULT_MPMATH_PRECISION


@contextmanager
def in_process_evaluation_timeout(timeout_seconds: float) -> Iterator[None]:
    """Bound in-process evaluation wall time with an interval timer.

    Sandboxed worker paths already enforce a parent-side wall-clock deadline
    plus RLIMIT_CPU in the child. This guard covers direct in-process callers
    (the app runtime protocol, tests, and any direct execute_direct consumer)
    so a pathological evaluation returns E_TIMEOUT instead of hanging the
    process. Unix signal restrictions apply: SIGALRM can only be armed on the
    process main thread; in other threads, or on platforms without SIGALRM,
    arming is skipped and the call runs without this in-process bound.
    """
    timeout_ms = int(round(timeout_seconds * 1000))

    def raise_evaluation_timeout(signum: int, frame: Any) -> None:
        raise CalculatorError(
            "E_TIMEOUT",
            "operation exceeded the in-process evaluation limit",
            {"timeoutMs": timeout_ms},
        )

    try:
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
    except (ValueError, OSError, AttributeError):
        yield
        return
    # Never postpone an already-armed outer deadline. When it is the earlier
    # timer, preserve its handler as well as its remaining duration so nested
    # evaluation guards do not turn the caller's timeout into our E_TIMEOUT.
    previous_remaining = previous_timer[0]
    outer_deadline_is_earlier = (
        previous_remaining > 0 and previous_remaining <= timeout_seconds
    )
    armed_seconds = (
        previous_remaining if outer_deadline_is_earlier else timeout_seconds
    )
    armed_handler = previous_handler if outer_deadline_is_earlier else raise_evaluation_timeout
    started_at = time.monotonic()
    try:
        signal.signal(signal.SIGALRM, armed_handler)
        signal.setitimer(
            signal.ITIMER_REAL,
            armed_seconds,
            previous_timer[1] if outer_deadline_is_earlier else 0.0,
        )
    except (ValueError, OSError, AttributeError):
        # signal.signal can succeed before setitimer fails. Restore the handler
        # before falling back to an unguarded call.
        try:
            signal.signal(signal.SIGALRM, previous_handler)
        except (ValueError, OSError, AttributeError):
            pass
        yield
        return
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_remaining > 0:
            elapsed = max(0.0, time.monotonic() - started_at)
            if elapsed < previous_remaining:
                remaining = previous_remaining - elapsed
            elif previous_timer[1] > 0:
                elapsed_after_first = elapsed - previous_remaining
                remainder = elapsed_after_first % previous_timer[1]
                remaining = previous_timer[1] - remainder
            else:
                remaining = 0.0
            if remaining > 0:
                signal.setitimer(
                    signal.ITIMER_REAL,
                    remaining,
                    previous_timer[1],
                )


def execute_direct(
    operation: str,
    arguments: dict[str, Any],
    *,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError("E_OPERATION", f"unknown operation: {operation}")
    if not isinstance(arguments, dict):
        raise CalculatorError("E_INPUT", "arguments must be an object")
    validate_operation_arguments(operation, spec.input_schema, arguments)
    if timeout_ms is None:
        timeout_seconds = EVALUATION_TIMEOUT_SECONDS
    else:
        # Mirror the public timeoutMs range (sandbox.run_operation) so the
        # in-process bound matches the caller's budget.
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool):
            raise CalculatorError(
                "E_LIMIT",
                "timeoutMs must be an integer between 100 and 30000",
            )
        if not 100 <= timeout_ms <= 30_000:
            raise CalculatorError(
                "E_LIMIT",
                "timeoutMs must be between 100 and 30000",
            )
        timeout_seconds = timeout_ms / 1000
    with in_process_evaluation_timeout(timeout_seconds):
        try:
            result = apply_research_contract(spec, spec.handler(arguments))
            validate_result(result)
            return result
        except CalculatorError:
            raise
        except Exception as error:
            raise CalculatorError("E_RUNTIME", f"operation failed: {error}") from error
        finally:
            ensure_mpmath_default_precision()
