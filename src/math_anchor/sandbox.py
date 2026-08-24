from __future__ import annotations

import atexit
from copy import deepcopy
import json
import os
import psutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed, wait
from queue import Empty, Queue
from typing import Any

from .errors import error_payload

from .output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_RESULT_MODE,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
    RESULT_MODES,
    apply_output_policy,
)
from .runtime_control import AdmissionController, CircuitBreaker
from .runtime_telemetry import RUNTIME_TELEMETRY


DEFAULT_TIMEOUT_MS = 10_000
DEFAULT_MEMORY_MB = 1024
STARTUP_TIMEOUT_MS = 5_000
MAX_REUSABLE_WORKERS = 4
WORKER_POLL_SECONDS = 0.025
WORKER_PREWARM_BUDGET_SECONDS = 10.0
MAX_REQUESTS_PER_WORKER = 1_000
WORKER_RECYCLE_RSS_MB = 768
# Worker stderr is redirected to an unlinked file, not a pipe: an undrained
# pipe can fill (~64 KiB) over a long-lived session and silently block the
# worker mid-operation. The file has no such bound, and diagnostics read
# only this bounded tail.
_STDERR_TAIL_BYTES = 8_192
_BATCH_ITEM_FIELDS = {
    "operation",
    "arguments",
    "timeoutMs",
    "memoryMb",
    "resultMode",
    "maxOutputBytes",
}


def _error(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    phase: str | None = None,
    retry_after_ms: int | None = None,
    suggested_action: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "error": error_payload(
            code,
            message,
            details,
            phase=phase,
            retry_after_ms=retry_after_ms,
            suggested_action=suggested_action,
        ),
    }


class _CombinedCancelEvent:
    def __init__(self, *events: threading.Event | None) -> None:
        self.events = tuple(event for event in events if event is not None)

    def is_set(self) -> bool:
        return any(event.is_set() for event in self.events)


class _ReusableWorker:
    def __init__(self, process: subprocess.Popen[str], stderr_fd: int) -> None:
        self.process = process
        self.stderr_fd = stderr_fd
        self.pool_generation: int | None = None
        self.created_at = time.monotonic()
        self.requests_completed = 0
        # One daemon reader lives with each persistent worker. The previous
        # implementation created and joined a new ThreadPoolExecutor for every
        # operation, which made a cheap warm expression pay thread lifecycle
        # overhead on every high-frequency call.
        self._read_requests: Queue[bool] = Queue()
        self._responses: Queue[tuple[str, BaseException | None]] = Queue()
        self.output_reader = threading.Thread(
            target=self._read_output,
            name=f"calculator-worker-output-{process.pid}",
            daemon=True,
        )
        self.output_reader.start()

    def _read_output(self) -> None:
        while self._read_requests.get():
            try:
                line = _read_response_line(self.process)
            except BaseException as error:
                self._responses.put(("", error))
                return
            self._responses.put((line, None))
            if not line:
                return

    def expect_response(self) -> None:
        self._read_requests.put(True)

    def take_response(
        self,
        *,
        timeout: float | None = None,
    ) -> tuple[str, BaseException | None]:
        if timeout is None:
            return self._responses.get_nowait()
        return self._responses.get(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self.process.poll() is None

    def stderr_tail(self) -> str:
        return _stderr_tail(self.stderr_fd)

    def reset_stderr(self) -> None:
        """Discard completed-request diagnostics before the next lease."""
        if self.stderr_fd == -1:
            return
        try:
            # The worker is idle when it is returned to the pool. Its stderr
            # descriptor shares this file offset, so truncation plus seek
            # starts the next request from a clean diagnostic record. Keeping
            # an old tail could misreport a prior warning as a later crash.
            os.ftruncate(self.stderr_fd, 0)
            os.lseek(self.stderr_fd, 0, os.SEEK_SET)
        except OSError:
            # Diagnostic cleanup must not turn a completed calculation into
            # a failure. A later terminate still closes the descriptor.
            pass

    def close(self) -> None:
        if self.stderr_fd != -1:
            os.close(self.stderr_fd)
            self.stderr_fd = -1

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        self._read_requests.put(False)
        self.output_reader.join(timeout=1)
        self.close()


class _WorkerPool:
    def __init__(self, maximum: int = MAX_REUSABLE_WORKERS) -> None:
        self.maximum = maximum
        self.condition = threading.Condition()
        self.available: list[_ReusableWorker] = []
        self.total = 0
        self.generation = 0
        self.prewarm_generation: int | None = None
        # Start conservatively with one warm process. Real concurrent demand
        # raises this target, so later recycling restores observed capacity
        # without prestarting four heavyweight symbolic runtimes for a client
        # that only ever makes serial calls.
        self.desired_warm = 1

    def acquire(
        self,
        memory_bytes: int,
        *,
        deadline: float,
        timeout_ms: int,
        cancel_event: threading.Event | None = None,
    ) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
        while True:
            # Evicted workers terminate outside the pool lock: terminate()
            # blocks in kill/wait/join for up to ~2 s per worker, and holding
            # the condition during that stalls every other acquire/release.
            discarded: list[_ReusableWorker] = []
            selected: _ReusableWorker | None = None
            under_warm = False
            try:
                with self.condition:
                    if cancel_event is not None and cancel_event.is_set():
                        return None, _error("E_CANCELLED", "operation was cancelled")
                    while self.available:
                        worker = self.available.pop()
                        resident = _resident_memory_bytes(worker.process.pid)
                        if worker.is_running and (resident is None or resident <= memory_bytes):
                            selected = worker
                            # Handing out a pooled worker is often the last
                            # observation of the pool before it goes quiet;
                            # re-check the warm target here so capacity lost
                            # to earlier evictions is replaced instead of
                            # silently decaying until the next busy spell.
                            under_warm = self._should_replenish(self.generation)
                            break
                        self.total -= 1
                        discarded.append(worker)
                    if selected is None:
                        if self.prewarm_generation == self.generation:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                return None, _error(
                                    "E_TIMEOUT",
                                    f"operation exceeded {timeout_ms} ms while waiting for a worker",
                                    {"phase": "queue", "timeoutMs": timeout_ms},
                                )
                            self.condition.wait(timeout=min(remaining, WORKER_POLL_SECONDS))
                            continue
                        if self.total < self.maximum:
                            self.total += 1
                            self.desired_warm = max(self.desired_warm, self.total)
                            generation = self.generation
                            break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return None, _error(
                                "E_TIMEOUT",
                                f"operation exceeded {timeout_ms} ms while waiting for a worker",
                                {"phase": "queue", "timeoutMs": timeout_ms},
                            )
                        self.condition.wait(timeout=min(remaining, WORKER_POLL_SECONDS))
            finally:
                for victim in discarded:
                    victim.terminate()
            if selected is not None:
                if under_warm:
                    self._prewarm_one()
                return selected, None

        try:
            worker, error = _start_worker(
                memory_bytes,
                deadline=deadline,
                timeout_ms=timeout_ms,
                cancel_event=cancel_event,
            )
        except Exception as startup_exception:
            worker = None
            error = _error(
                "E_RUNTIME",
                f"worker startup failed: {type(startup_exception).__name__}",
                phase="startup",
            )
        if worker is None:
            with self.condition:
                self.total -= 1
                self.condition.notify()
            return None, error
        worker.pool_generation = generation
        return worker, None

    def _should_replenish(self, generation: int | None) -> bool:
        with self.condition:
            return (
                generation == self.generation
                and self.total < self.desired_warm
                and self.prewarm_generation is None
            )

    def _prewarm_one(self) -> None:
        RUNTIME_TELEMETRY.increment("workers.adaptivePrewarm")
        warm_worker_pool()

    def release(self, worker: _ReusableWorker, *, reusable: bool) -> None:
        terminate = False
        replenish = False
        with self.condition:
            if reusable:
                worker.requests_completed += 1
                resident = _resident_memory_bytes(worker.process.pid)
                if (
                    worker.requests_completed >= MAX_REQUESTS_PER_WORKER
                    or (
                        resident is not None
                        and resident > WORKER_RECYCLE_RSS_MB * 1024 * 1024
                    )
                ):
                    reusable = False
                    RUNTIME_TELEMETRY.increment("workers.recycled")
            if (
                reusable
                and worker.is_running
                and worker.pool_generation == self.generation
            ):
                worker.reset_stderr()
                self.available.append(worker)
            else:
                self.total -= 1
                terminate = True
                replenish = self._should_replenish(worker.pool_generation)
            self.condition.notify()
        if terminate:
            worker.terminate()
        if replenish:
            self._prewarm_one()

    def reserve_prewarm(self) -> int | None:
        """Reserve one missing observed-capacity slot for async startup."""
        with self.condition:
            if (
                self.total >= self.desired_warm
                or self.prewarm_generation is not None
            ):
                return None
            generation = self.generation
            self.total += 1
            self.prewarm_generation = generation
            return generation

    def owns_prewarm(self, generation: int) -> bool:
        with self.condition:
            return self.prewarm_generation == generation

    def finish_prewarm(
        self,
        worker: _ReusableWorker | None,
        *,
        generation: int,
    ) -> None:
        terminate = worker is not None
        with self.condition:
            owns_reservation = self.prewarm_generation == generation
            if owns_reservation:
                self.prewarm_generation = None
            if (
                owns_reservation
                and generation == self.generation
                and worker is not None
                and worker.is_running
            ):
                worker.pool_generation = generation
                worker.reset_stderr()
                self.available.append(worker)
                terminate = False
            elif owns_reservation:
                self.total -= 1
            self.condition.notify_all()
        if terminate and worker is not None:
            worker.terminate()

    def shutdown(self) -> None:
        with self.condition:
            self.generation += 1
            workers = self.available
            self.available = []
            self.total -= len(workers)
            if self.prewarm_generation is not None:
                self.total -= 1
                self.prewarm_generation = None
            self.desired_warm = 1
            self.condition.notify_all()
        for worker in workers:
            worker.terminate()


_WORKER_POOL = _WorkerPool()
_ADMISSION = AdmissionController()
_CIRCUIT = CircuitBreaker()
atexit.register(_WORKER_POOL.shutdown)


def warm_worker_pool() -> None:
    """Pre-start one reusable worker on a background thread.

    A session's first math.run or math.batch call otherwise pays the full
    worker startup (~200 ms warm-cache, more on a cold cache) after the
    client is already interactive. Warming overlaps that startup with MCP
    initialization. Best effort: any failure leaves the pool empty and the
    first call starts a worker normally.
    """

    generation = _WORKER_POOL.reserve_prewarm()
    if generation is None:
        return

    def warm() -> None:
        worker: _ReusableWorker | None = None
        try:
            # A shutdown can land between reserving the slot and reaching
            # this thread; spawning then would create a child nobody owns.
            if _WORKER_POOL.owns_prewarm(generation):
                worker, _unused = _start_worker(
                    DEFAULT_MEMORY_MB * 1024 * 1024,
                    deadline=time.monotonic() + WORKER_PREWARM_BUDGET_SECONDS,
                    timeout_ms=DEFAULT_TIMEOUT_MS,
                    cancel_event=None,
                )
        except Exception:
            pass
        finally:
            _WORKER_POOL.finish_prewarm(worker, generation=generation)

    threading.Thread(target=warm, name="calculator-worker-prewarm", daemon=True).start()


def run_operation(
    operation: str,
    arguments: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    memory_mb: int = DEFAULT_MEMORY_MB,
    result_mode: str = DEFAULT_RESULT_MODE,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    cancel_event: threading.Event | None = None,
    _request_class: str = "single",
) -> dict[str, Any]:
    started = time.monotonic()
    result = _run_operation_impl(
        operation,
        arguments,
        timeout_ms=timeout_ms,
        memory_mb=memory_mb,
        result_mode=result_mode,
        max_output_bytes=max_output_bytes,
        cancel_event=cancel_event,
        request_class=_request_class,
    )
    RUNTIME_TELEMETRY.increment("requests.total")
    RUNTIME_TELEMETRY.increment(f"requests.{_request_class}")
    if result.get("status") == "error":
        code = str(result.get("error", {}).get("code", "E_RUNTIME"))
        RUNTIME_TELEMETRY.increment(f"errors.{code}")
    RUNTIME_TELEMETRY.observe("requests.totalMs", (time.monotonic() - started) * 1000)
    return result


def _run_operation_impl(
    operation: str,
    arguments: dict[str, Any],
    *,
    timeout_ms: int,
    memory_mb: int,
    result_mode: str,
    max_output_bytes: int,
    cancel_event: threading.Event | None,
    request_class: str,
) -> dict[str, Any]:
    if cancel_event is not None and cancel_event.is_set():
        return _error("E_CANCELLED", "operation was cancelled")
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool):
        return _error("E_LIMIT", "timeoutMs must be an integer between 100 and 30000")
    if not 100 <= timeout_ms <= 30_000:
        return _error("E_LIMIT", "timeoutMs must be between 100 and 30000")
    if not isinstance(memory_mb, int) or isinstance(memory_mb, bool):
        return _error("E_LIMIT", "memoryMb must be an integer between 256 and 4096")
    if not 256 <= memory_mb <= 4096:
        return _error("E_LIMIT", "memoryMb must be between 256 and 4096")
    if not isinstance(operation, str) or not operation:
        return _error("E_INPUT", "operation must be a non-empty string")
    if not isinstance(arguments, dict):
        return _error("E_INPUT", "arguments must be an object")
    if result_mode not in RESULT_MODES:
        return _error("E_INPUT", f"resultMode must be one of {', '.join(RESULT_MODES)}")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool):
        return _error("E_LIMIT", f"maxOutputBytes must be an integer between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")
    if not MIN_OUTPUT_BYTES <= max_output_bytes <= MAX_OUTPUT_BYTES:
        return _error("E_LIMIT", f"maxOutputBytes must be between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")

    deadline = time.monotonic() + timeout_ms / 1000
    payload = {
        "operation": operation,
        "arguments": arguments,
        "timeoutMs": timeout_ms,
        "memoryMb": memory_mb,
        # Apply the public result projection and byte ceiling inside the
        # supervised worker before it writes to stdout. The parent applies the
        # policy again to its own supervision errors, but no successful worker
        # response needs to cross the pipe at its original unbounded size.
        "resultMode": result_mode,
        "maxOutputBytes": max_output_bytes,
    }
    try:
        request_line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        # Transport payloads are JSON by construction, but direct library
        # callers can hand over values json cannot encode. Reject before a
        # worker is acquired so no pool slot is ever tied to a request that
        # cannot be sent.
        return apply_output_policy(
            _error("E_INPUT", f"arguments must be JSON-serializable: {error}"),
            result_mode=result_mode,
            max_output_bytes=max_output_bytes,
        )
    memory_bytes = memory_mb * 1024 * 1024
    allowed, retry_after_ms = _CIRCUIT.allow()
    if not allowed:
        return _error(
            "E_UNAVAILABLE",
            "calculation workers are temporarily unavailable after repeated provider failures",
            phase="admission",
            retry_after_ms=retry_after_ms,
        )
    lease, admission_error = _ADMISSION.acquire(
        memory_mb,
        request_class=request_class,
        deadline=deadline,
        cancel_event=cancel_event,
        poll_seconds=WORKER_POLL_SECONDS,
    )
    if lease is None:
        # The half-open probe reserved by allow() was never consumed by an
        # execution; returning it keeps one admission-phase failure from
        # stranding the breaker in a state that refuses every later call.
        _CIRCUIT.abandon_probe()
        if admission_error == "overloaded":
            return _error(
                "E_OVERLOADED",
                "calculation queue is full; retry after the current burst",
                {"queueLimit": _ADMISSION.maximum_queued},
                phase="admission",
                retry_after_ms=100,
            )
        if admission_error == "cancelled":
            return _error("E_CANCELLED", "operation was cancelled")
        return _error(
            "E_TIMEOUT",
            f"operation exceeded {timeout_ms} ms while waiting for admission",
            {"phase": "admission", "timeoutMs": timeout_ms},
            phase="admission",
        )
    RUNTIME_TELEMETRY.observe("requests.queueMs", lease.queue_ms)
    try:
        result = _execute_admitted_operation(
            request_line,
            memory_bytes=memory_bytes,
            deadline=deadline,
            timeout_ms=timeout_ms,
            memory_mb=memory_mb,
            result_mode=result_mode,
            max_output_bytes=max_output_bytes,
            cancel_event=cancel_event,
        )
    except BaseException:
        # _execute_admitted_operation converts its own failures, so this is
        # a parent-side supervision bug; it is provider fault evidence and
        # the probe must still be accounted before the exception escapes.
        _CIRCUIT.record(outcome="infrastructure_failure")
        raise
    finally:
        _ADMISSION.release(lease)
    if result.get("status") == "error":
        outcome = (
            "infrastructure_failure"
            if result.get("error", {}).get("code") == "E_RUNTIME"
            else "error"
        )
    else:
        outcome = "success"
    if _CIRCUIT.record(outcome=outcome):
        RUNTIME_TELEMETRY.increment("circuit.opened")
    return result


def _execute_admitted_operation(
    request_line: str,
    *,
    memory_bytes: int,
    deadline: float,
    timeout_ms: int,
    memory_mb: int,
    result_mode: str,
    max_output_bytes: int,
    cancel_event: threading.Event | None,
) -> dict[str, Any]:
    worker, startup_error = _WORKER_POOL.acquire(
        memory_bytes,
        deadline=deadline,
        timeout_ms=timeout_ms,
        cancel_event=cancel_event,
    )
    if worker is None:
        return startup_error or _error(
            "E_RUNTIME", "worker failed to start", phase="startup"
        )
    if cancel_event is not None and cancel_event.is_set():
        _WORKER_POOL.release(worker, reusable=True)
        return _error("E_CANCELLED", "operation was cancelled")
    if time.monotonic() >= deadline:
        _WORKER_POOL.release(worker, reusable=True)
        return _error(
            "E_TIMEOUT",
            f"operation exceeded {timeout_ms} ms before execution began",
            {"phase": "startup", "timeoutMs": timeout_ms},
        )
    reusable = False
    output_policy_applied = False
    execution_started = time.monotonic()
    try:
        result, reusable, output_policy_applied = _execute_worker(
            worker,
            request_line,
            deadline=deadline,
            timeout_ms=timeout_ms,
            memory_mb=memory_mb,
            cancel_event=cancel_event,
        )
    except Exception as execution_error:
        result = _error(
            "E_RUNTIME",
            f"worker supervision failed: {type(execution_error).__name__}",
        )
    finally:
        RUNTIME_TELEMETRY.observe(
            "requests.executionMs",
            (time.monotonic() - execution_started) * 1000,
        )
        # An unexpected parent-side exception between acquire and release
        # previously leaked the slot permanently; four leaks saturated the
        # pool and every later operation became a queue-phase E_TIMEOUT.
        # An unwritten worker state is never reusable, so it is destroyed.
        _WORKER_POOL.release(worker, reusable=reusable)
    if output_policy_applied:
        return result
    return apply_output_policy(
        result,
        result_mode=result_mode,
        max_output_bytes=max_output_bytes,
    )


def _worker_stderr_file() -> int:
    descriptor, path = tempfile.mkstemp(prefix="math-anchor-worker-", suffix=".err")
    # Unlink immediately: the tail log needs no path, and the space is
    # reclaimed as soon as the last descriptor closes.
    try:
        os.unlink(path)
    except OSError:
        os.close(descriptor)
        raise
    return descriptor


def _stderr_tail(descriptor: int) -> str:
    # os.pread leaves the shared file offset untouched, so the worker keeps
    # appending while diagnostics read a stable bounded tail.
    return _stderr_tail_bytes(descriptor).decode("utf-8", "replace")


def _stderr_tail_bytes(descriptor: int) -> bytes:
    try:
        size = os.fstat(descriptor).st_size
        return os.pread(
            descriptor,
            min(size, _STDERR_TAIL_BYTES),
            max(0, size - _STDERR_TAIL_BYTES),
        )
    except OSError:
        return b""


def _start_worker(
    memory_bytes: int,
    *,
    deadline: float,
    timeout_ms: int,
    cancel_event: threading.Event | None,
) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
    started = time.monotonic()
    try:
        worker, error = _start_worker_impl(
            memory_bytes,
            deadline=deadline,
            timeout_ms=timeout_ms,
            cancel_event=cancel_event,
        )
        RUNTIME_TELEMETRY.increment(
            "workers.started" if worker is not None else "workers.startFailed"
        )
        return worker, error
    finally:
        RUNTIME_TELEMETRY.observe("workers.startupMs", (time.monotonic() - started) * 1000)


def _start_worker_impl(
    memory_bytes: int,
    *,
    deadline: float,
    timeout_ms: int,
    cancel_event: threading.Event | None,
) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
    if cancel_event is not None and cancel_event.is_set():
        return None, _error("E_CANCELLED", "operation was cancelled")
    environment = os.environ.copy()
    environment.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    command = (
        [sys.executable, "worker", "--persistent"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "math_anchor.worker", "--persistent"]
    )
    try:
        stderr_fd = _worker_stderr_file()
    except OSError as error:
        return None, _error(
            "E_RUNTIME",
            f"worker diagnostics could not be created: {error}",
            phase="startup",
        )
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_fd,
            text=True,
            bufsize=1,
            env=environment,
        )
    except OSError as error:
        os.close(stderr_fd)
        return None, _error(
            "E_RUNTIME", f"worker failed to start: {error}", phase="startup"
        )
    startup_error = _await_worker_ready(
        process,
        memory_bytes,
        stderr_fd=stderr_fd,
        deadline=deadline,
        timeout_ms=timeout_ms,
        cancel_event=cancel_event,
    )
    if startup_error is not None:
        # _await_worker_ready consumed the descriptor on every failure path.
        return None, startup_error
    return _ReusableWorker(process, stderr_fd), None


def _execute_worker(
    worker: _ReusableWorker,
    request_line: str,
    *,
    deadline: float,
    timeout_ms: int,
    memory_mb: int,
    cancel_event: threading.Event | None,
) -> tuple[dict[str, Any], bool, bool]:
    process = worker.process
    memory_bytes = memory_mb * 1024 * 1024
    if process.stdin is None or process.stdout is None:
        return _error("E_RUNTIME", "worker pipes were unavailable"), False, False
    worker.expect_response()
    try:
        process.stdin.write(request_line)
        process.stdin.flush()
    except (BrokenPipeError, OSError):
        return _error("E_RUNTIME", "worker input was unavailable"), False, False

    response_line = ""
    reader_error: BaseException | None = None
    limit_error: dict[str, Any] | None = None
    while True:
        try:
            response_line, reader_error = worker.take_response()
            break
        except Empty:
            pass
        if cancel_event is not None and cancel_event.is_set():
            limit_error = _error("E_CANCELLED", "operation was cancelled")
            process.kill()
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # A response already handed to the supervisor is complete even if
            # this thread resumes slightly after the deadline. If no response
            # is queued, enforce the deadline instead of accepting a future
            # that happens to finish after a long polling wait.
            try:
                response_line, reader_error = worker.take_response()
                break
            except Empty:
                limit_error = _error("E_TIMEOUT", f"operation exceeded {timeout_ms} ms")
                process.kill()
                break
        resident_bytes = _resident_memory_bytes(process.pid)
        if resident_bytes is not None and resident_bytes > memory_bytes:
            limit_error = _error("E_MEMORY", f"operation exceeded {memory_mb} MB of resident memory")
            process.kill()
            break
        # The reader thread turns process EOF or a decode failure into the
        # queued response too, so every path gets the same bounded wait.
        wait_seconds = min(remaining, WORKER_POLL_SECONDS)
        try:
            response_line, reader_error = worker.take_response(timeout=wait_seconds)
            break
        except Empty:
            continue

    if limit_error is not None:
        return limit_error, False, False
    if reader_error is not None:
        # A reader-thread failure (closed pipe during teardown, decode error)
        # must surface as a structured error, never propagate.
        process.kill()
        return _error("E_RUNTIME", f"worker output reader failed: {reader_error}"), False, False

    if not response_line:
        return_code = process.poll()
        stderr = worker.stderr_tail().strip() if return_code is not None else ""
        message = stderr.splitlines()[-1] if stderr else "worker terminated"
        details = {"returnCode": return_code} if return_code is not None else None
        return _error("E_RUNTIME", message, details), False, False
    try:
        response = json.loads(response_line)
    except json.JSONDecodeError:
        return _error("E_RUNTIME", "worker returned an invalid response"), False, False
    if response.get("ok") is True:
        return response["result"], True, True
    error = response.get("error")
    if not isinstance(error, dict):
        error = error_payload("E_RUNTIME", "unknown worker error")
    return (
        {"status": "error", "error": error},
        error.get("code") != "E_RUNTIME",
        True,
    )


def _wait_for_worker_progress(worker_future: Future[Any]) -> None:
    # Wake as soon as the worker produces output instead of adding the full
    # supervision cadence to every successful call. Long-running work still
    # samples cancellation, deadline, memory, and liveness at the poll rate.
    wait((worker_future,), timeout=WORKER_POLL_SECONDS)


def _read_response_line(process: subprocess.Popen[str]) -> str:
    return process.stdout.readline() if process.stdout is not None else ""


def _await_worker_ready(
    process: subprocess.Popen[str],
    memory_bytes: int,
    *,
    stderr_fd: int,
    deadline: float,
    timeout_ms: int,
    cancel_event: threading.Event | None,
) -> dict[str, Any] | None:
    if process.stdout is None:
        process.kill()
        os.close(stderr_fd)
        return _error("E_RUNTIME", "worker output was unavailable", phase="startup")
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="calculator-worker-startup") as executor:
        readiness = executor.submit(process.stdout.readline)
        startup_deadline = min(deadline, time.monotonic() + STARTUP_TIMEOUT_MS / 1000)
        while not readiness.done():
            if cancel_event is not None and cancel_event.is_set():
                process.kill()
                readiness.result()
                os.close(stderr_fd)
                return _error("E_CANCELLED", "operation was cancelled")
            if time.monotonic() >= startup_deadline:
                process.kill()
                readiness.result()
                os.close(stderr_fd)
                if startup_deadline == deadline:
                    return _error(
                        "E_TIMEOUT",
                        f"operation exceeded {timeout_ms} ms while starting a worker",
                        {"phase": "startup", "timeoutMs": timeout_ms},
                    )
                return _error(
                    "E_RUNTIME",
                    f"worker did not start within {STARTUP_TIMEOUT_MS} ms",
                    phase="startup",
                )
            resident_bytes = _resident_memory_bytes(process.pid)
            if resident_bytes is not None and resident_bytes > memory_bytes:
                process.kill()
                readiness.result()
                os.close(stderr_fd)
                return _error(
                    "E_MEMORY",
                    "worker exceeded the memory limit during startup",
                    phase="startup",
                )
            if process.poll() is not None:
                break
            _wait_for_worker_progress(readiness)
        line = readiness.result()
    try:
        ready = json.loads(line)
    except json.JSONDecodeError:
        ready = None
    if ready != {"ready": True}:
        stderr = _stderr_tail(stderr_fd).strip()
        process.kill()
        os.close(stderr_fd)
        return _error(
            "E_RUNTIME",
            stderr.splitlines()[-1] if stderr else "worker failed to start",
            phase="startup",
        )
    return None


def _resident_memory_bytes(process_id: int) -> int | None:
    try:
        return psutil.Process(process_id).memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def run_batch(
    items: list[dict[str, Any]],
    *,
    timeout_ms: int = 30_000,
    max_output_bytes: int = DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    if cancel_event is not None and cancel_event.is_set():
        return _error("E_CANCELLED", "batch was cancelled")
    if not isinstance(items, list) or not 1 <= len(items) <= 32:
        return _error("E_LIMIT", "items must contain 1 to 32 operations")
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool):
        return _error("E_LIMIT", "timeoutMs must be an integer between 100 and 30000")
    if not 100 <= timeout_ms <= 30_000:
        return _error("E_LIMIT", "timeoutMs must be between 100 and 30000")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool):
        return _error("E_LIMIT", f"maxOutputBytes must be an integer between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")
    if not MIN_OUTPUT_BYTES <= max_output_bytes <= MAX_OUTPUT_BYTES:
        return _error("E_LIMIT", f"maxOutputBytes must be between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")
    deadline = time.monotonic() + timeout_ms / 1000
    worker_count = _batch_worker_count(items)
    batch_cancel = threading.Event()
    combined_cancel = _CombinedCancelEvent(cancel_event, batch_cancel)
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, item in enumerate(items):
        try:
            key = json.dumps(item, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError, OverflowError, RecursionError):
            key = f"unserializable:{index}"
        grouped.setdefault(key, []).append((index, item))
    coalesced = len(items) - len(grouped)
    if coalesced:
        RUNTIME_TELEMETRY.increment("batch.itemsCoalesced", coalesced)

    results_by_index: dict[int, dict[str, Any]] = {}
    encoded_bytes = 0
    aborted: dict[str, Any] | None = None
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="calculator-batch") as executor:
        futures = {
            executor.submit(
                _run_batch_item,
                entries[0],
                combined_cancel,
                deadline,
                timeout_ms,
            ): entries
            for entries in grouped.values()
        }
        for future in as_completed(futures):
            try:
                representative = future.result()
            except Exception as item_error:
                # A supervision failure inside one item's thread must not
                # convert the rest of a valid batch into a whole-call
                # transport failure; it is that item's error envelope.
                representative = _error(
                    "E_RUNTIME",
                    f"batch item supervision failed: {type(item_error).__name__}",
                )
            for index, _item in futures[future]:
                indexed_result = deepcopy(representative)
                indexed_result["index"] = index
                results_by_index[index] = indexed_result
                # Charge every logical result, including coalesced duplicates.
                # Once item payloads alone exceed the limit, the final envelope
                # is mathematically unable to fit.
                encoded_bytes += len(
                    json.dumps(indexed_result, ensure_ascii=False, separators=(",", ":")).encode()
                )
                if encoded_bytes > max_output_bytes:
                    batch_cancel.set()
                    for pending in futures:
                        if pending is not future:
                            pending.cancel()
                    RUNTIME_TELEMETRY.increment("batch.outputAborts")
                    aborted = _error(
                        "E_OUTPUT_LIMIT",
                        f"batch result requires at least {encoded_bytes} bytes; "
                        "reduce the batch or increase maxOutputBytes",
                        {"bytes": encoded_bytes, "maxOutputBytes": max_output_bytes},
                        phase="output",
                    )
                    break
            if aborted is not None:
                break
    if aborted is not None:
        return aborted
    if cancel_event is not None and cancel_event.is_set():
        return _error("E_CANCELLED", "batch was cancelled")
    results = [results_by_index[index] for index in range(len(items))]
    result = {
        "status": "ok" if all(result.get("status") == "ok" for result in results) else "partial",
        "count": len(results),
        "results": results,
    }
    size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode())
    if size > max_output_bytes:
        return _error(
            "E_OUTPUT_LIMIT",
            f"batch result requires {size} bytes; reduce the batch or increase maxOutputBytes",
            {"bytes": size, "maxOutputBytes": max_output_bytes},
        )
    return result


def _run_batch_item(
    indexed_item: tuple[int, dict[str, Any]],
    cancel_event: threading.Event | None = None,
    batch_deadline: float | None = None,
    batch_timeout_ms: int = 30_000,
) -> dict[str, Any]:
    index, item = indexed_item
    if (
        not isinstance(item, dict)
        or not isinstance(item.get("operation"), str)
        or not isinstance(item.get("arguments"), dict)
    ):
        return {
            "index": index,
            **_error("E_INPUT", "each item requires an operation string and arguments object"),
        }
    unexpected_fields = set(item) - _BATCH_ITEM_FIELDS
    if unexpected_fields:
        return {
            "index": index,
            **_error(
                "E_INPUT",
                "batch item contains unsupported fields",
                {"fieldCount": len(unexpected_fields)},
            ),
        }
    item_timeout_ms = item.get("timeoutMs", DEFAULT_TIMEOUT_MS)
    if batch_deadline is not None:
        remaining_ms = int((batch_deadline - time.monotonic()) * 1000)
        if remaining_ms < 100:
            return {
                "index": index,
                **_error(
                    "E_TIMEOUT",
                    f"batch exceeded its cumulative {batch_timeout_ms} ms deadline",
                    {"phase": "batch", "timeoutMs": batch_timeout_ms},
                ),
            }
        if isinstance(item_timeout_ms, int) and not isinstance(item_timeout_ms, bool):
            item_timeout_ms = min(item_timeout_ms, remaining_ms)
    result = run_operation(
        item["operation"],
        item["arguments"],
        timeout_ms=item_timeout_ms,
        memory_mb=item.get("memoryMb", DEFAULT_MEMORY_MB),
        result_mode=item.get("resultMode", DEFAULT_RESULT_MODE),
        max_output_bytes=item.get("maxOutputBytes", DEFAULT_MAX_OUTPUT_BYTES),
        cancel_event=cancel_event,
        _request_class="batch",
    )
    return {"index": index, **result}


def _batch_worker_count(items: list[dict[str, Any]]) -> int:
    requested_limits = [
        item.get("memoryMb", DEFAULT_MEMORY_MB)
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("memoryMb", DEFAULT_MEMORY_MB), int)
        and not isinstance(item.get("memoryMb", DEFAULT_MEMORY_MB), bool)
    ]
    largest_limit = max(requested_limits, default=DEFAULT_MEMORY_MB)
    memory_bounded_workers = max(1, 4096 // max(DEFAULT_MEMORY_MB, largest_limit))
    # A batch never owns the fourth worker. Admission gives that lane to an
    # interactive math.run even under a sustained 32-item batch workload.
    return max(1, min(3, len(items), memory_bounded_workers))
