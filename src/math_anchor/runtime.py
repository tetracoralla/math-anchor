from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import Any, Iterator

import mpmath

from .catalog import OPERATIONS
from .contracts import validate_operation_arguments, validate_result
from .errors import CalculatorError

# Mirrors sandbox.DEFAULT_TIMEOUT_MS (10_000 ms) so direct in-process callers
# observe the same bound as the sandboxed worker pool. Kept as a literal here
# to avoid importing the sandbox (and its psutil dependency) into every worker
# and app-runtime process; tests pin the two constants together.
EVALUATION_TIMEOUT_SECONDS = 10.0


def _raise_evaluation_timeout(signum: int, frame: Any) -> None:
    raise CalculatorError(
        "E_TIMEOUT",
        "operation exceeded the in-process evaluation limit",
        {"timeoutMs": int(EVALUATION_TIMEOUT_SECONDS * 1000)},
    )


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
    try:
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _raise_evaluation_timeout)
        previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    except (ValueError, OSError, AttributeError):
        yield
        return
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        if previous_timer is not None and previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def execute_direct(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise CalculatorError("E_OPERATION", f"unknown operation: {operation}")
    if not isinstance(arguments, dict):
        raise CalculatorError("E_INPUT", "arguments must be an object")
    validate_operation_arguments(operation, spec.input_schema, arguments)
    with in_process_evaluation_timeout(EVALUATION_TIMEOUT_SECONDS):
        try:
            result = spec.handler(arguments)
            validate_result(result)
            return result
        except CalculatorError:
            raise
        except Exception as error:
            raise CalculatorError("E_RUNTIME", f"operation failed: {error}") from error
        finally:
            ensure_mpmath_default_precision()
