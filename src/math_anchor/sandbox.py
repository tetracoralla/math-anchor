from __future__ import annotations

import atexit
import json
import os
import psutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any

from .output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_RESULT_MODE,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
    RESULT_MODES,
    apply_output_policy,
)


DEFAULT_TIMEOUT_MS = 10_000
DEFAULT_MEMORY_MB = 1024
STARTUP_TIMEOUT_MS = 5_000
MAX_REUSABLE_WORKERS = 4
WORKER_POLL_SECONDS = 0.025
WORKER_PREWARM_BUDGET_SECONDS = 10.0
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


def _error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"status": "error", "error": error}


class _ReusableWorker:
    def __init__(self, process: subprocess.Popen[str], stderr_fd: int) -> None:
        self.process = process
        self.stderr_fd = stderr_fd
        self.pool_generation: int | None = None

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
        self.close()


class _WorkerPool:
    def __init__(self, maximum: int = MAX_REUSABLE_WORKERS) -> None:
        self.maximum = maximum
        self.condition = threading.Condition()
        self.available: list[_ReusableWorker] = []
        self.total = 0
        self.generation = 0
        self.prewarm_generation: int | None = None

    def acquire(
        self,
        memory_bytes: int,
        *,
        deadline: float,
        timeout_ms: int,
        cancel_event: threading.Event | None = None,
    ) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
        while True:
            with self.condition:
                if cancel_event is not None and cancel_event.is_set():
                    return None, _error("E_CANCELLED", "operation was cancelled")
                while self.available:
                    worker = self.available.pop()
                    resident = _resident_memory_bytes(worker.process.pid)
                    if worker.is_running and (resident is None or resident <= memory_bytes):
                        return worker, None
                    self.total -= 1
                    worker.terminate()
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
            )
        if worker is None:
            with self.condition:
                self.total -= 1
                self.condition.notify()
            return None, error
        worker.pool_generation = generation
        return worker, None

    def release(self, worker: _ReusableWorker, *, reusable: bool) -> None:
        terminate = False
        with self.condition:
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
            self.condition.notify()
        if terminate:
            worker.terminate()

    def reserve_prewarm(self) -> int | None:
        """Reserve exactly one cold-pool slot for asynchronous startup."""
        with self.condition:
            if self.total != 0 or self.prewarm_generation is not None:
                return None
            generation = self.generation
            self.total += 1
            self.prewarm_generation = generation
            return generation

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
            self.condition.notify_all()
        for worker in workers:
            worker.terminate()


_WORKER_POOL = _WorkerPool()
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
    worker, startup_error = _WORKER_POOL.acquire(
        memory_bytes,
        deadline=deadline,
        timeout_ms=timeout_ms,
        cancel_event=cancel_event,
    )
    if worker is None:
        return startup_error or _error("E_RUNTIME", "worker failed to start")
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
    try:
        result, reusable = _execute_worker(
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
        # An unexpected parent-side exception between acquire and release
        # previously leaked the slot permanently; four leaks saturated the
        # pool and every later operation became a queue-phase E_TIMEOUT.
        # An unwritten worker state is never reusable, so it is destroyed.
        _WORKER_POOL.release(worker, reusable=reusable)
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
        return None, _error("E_RUNTIME", f"worker diagnostics could not be created: {error}")
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
        return None, _error("E_RUNTIME", f"worker failed to start: {error}")
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
) -> tuple[dict[str, Any], bool]:
    process = worker.process
    memory_bytes = memory_mb * 1024 * 1024
    if process.stdin is None or process.stdout is None:
        return _error("E_RUNTIME", "worker pipes were unavailable"), False
    try:
        process.stdin.write(request_line)
        process.stdin.flush()
    except (BrokenPipeError, OSError):
        return _error("E_RUNTIME", "worker input was unavailable"), False

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="calculator-worker-output") as executor:
        response_read = executor.submit(_read_response_line, process)
        limit_error: dict[str, Any] | None = None
        while not response_read.done():
            if cancel_event is not None and cancel_event.is_set():
                limit_error = _error("E_CANCELLED", "operation was cancelled")
                process.kill()
                break
            if time.monotonic() >= deadline:
                limit_error = _error("E_TIMEOUT", f"operation exceeded {timeout_ms} ms")
                process.kill()
                break
            resident_bytes = _resident_memory_bytes(process.pid)
            if resident_bytes is not None and resident_bytes > memory_bytes:
                limit_error = _error("E_MEMORY", f"operation exceeded {memory_mb} MB of resident memory")
                process.kill()
                break
            if process.poll() is not None:
                break
            _wait_for_worker_progress(response_read)

        try:
            response_line, completed_at = response_read.result()
        except Exception as error:
            # A reader-thread failure (closed pipe during teardown, decode
            # error) must surface as a structured error, never propagate.
            process.kill()
            return _error("E_RUNTIME", f"worker output reader failed: {error}"), False
        if limit_error is not None:
            return limit_error, False
        if completed_at >= deadline:
            process.kill()
            return _error("E_TIMEOUT", f"operation exceeded {timeout_ms} ms"), False

    if not response_line:
        return_code = process.poll()
        stderr = worker.stderr_tail().strip() if return_code is not None else ""
        message = stderr.splitlines()[-1] if stderr else "worker terminated"
        details = {"returnCode": return_code} if return_code is not None else None
        return _error("E_RUNTIME", message, details), False
    try:
        response = json.loads(response_line)
    except json.JSONDecodeError:
        return _error("E_RUNTIME", "worker returned an invalid response"), False
    if response.get("ok") is True:
        return response["result"], True
    error = response.get("error", {"code": "E_RUNTIME", "message": "unknown worker error"})
    return {"status": "error", "error": error}, error.get("code") != "E_RUNTIME"


def _wait_for_worker_progress(worker_future: Future[Any]) -> None:
    # Wake as soon as the worker produces output instead of adding the full
    # supervision cadence to every successful call. Long-running work still
    # samples cancellation, deadline, memory, and liveness at the poll rate.
    wait((worker_future,), timeout=WORKER_POLL_SECONDS)


def _read_response_line(
    process: subprocess.Popen[str],
) -> tuple[str, float]:
    line = process.stdout.readline() if process.stdout is not None else ""
    return line, time.monotonic()


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
        return _error("E_RUNTIME", "worker output was unavailable")
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
                return _error("E_RUNTIME", f"worker did not start within {STARTUP_TIMEOUT_MS} ms")
            resident_bytes = _resident_memory_bytes(process.pid)
            if resident_bytes is not None and resident_bytes > memory_bytes:
                process.kill()
                readiness.result()
                os.close(stderr_fd)
                return _error("E_MEMORY", "worker exceeded the memory limit during startup")
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
        return _error("E_RUNTIME", stderr.splitlines()[-1] if stderr else "worker failed to start")
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
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="calculator-batch") as executor:
        futures = [
            executor.submit(
                _run_batch_item,
                indexed_item,
                cancel_event,
                deadline,
                timeout_ms,
            )
            for indexed_item in enumerate(items)
        ]
        results = [future.result() for future in futures]
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
    return max(1, min(4, len(items), memory_bounded_workers))
