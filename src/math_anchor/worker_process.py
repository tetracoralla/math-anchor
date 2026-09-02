from __future__ import annotations

import json
import os
import psutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from queue import Empty, Queue
from typing import Any

from .errors import error_payload
from .runtime_telemetry import RUNTIME_TELEMETRY
from .sandbox_errors import _error


STARTUP_TIMEOUT_MS = 5_000
WORKER_POLL_SECONDS = 0.025
_STDERR_TAIL_BYTES = 8_192


class _ReusableWorker:
    def __init__(self, process: subprocess.Popen[str], stderr_fd: int) -> None:
        self.process = process
        self.stderr_fd = stderr_fd
        self.pool_generation: int | None = None
        self.created_at = time.monotonic()
        self.requests_completed = 0
        self.unit_registry_loaded = False
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
        if worker is not None:
            counter = "workers.started"
        elif error is not None and error.get("error", {}).get("code") == "E_CANCELLED":
            counter = "workers.startCancelled"
        else:
            counter = "workers.startFailed"
        RUNTIME_TELEMETRY.increment(counter)
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
    completed_at = response.pop("_completedAtMonotonic", None)
    if (
        isinstance(completed_at, bool)
        or not isinstance(completed_at, (int, float))
    ):
        process.kill()
        return _error("E_RUNTIME", "worker response omitted completion timing"), False, False
    if completed_at >= deadline:
        process.kill()
        return _error("E_TIMEOUT", f"operation exceeded {timeout_ms} ms"), False, False
    if response.get("ok") is True:
        return response["result"], True, True
    error = response.get("error")
    if not isinstance(error, dict):
        error = error_payload("E_RUNTIME", "unknown worker error")
    error_code = error.get("code")
    return (
        {"status": "error", "error": error},
        # A worker-side deadline can win the race with the supervisor's
        # matching wall-clock deadline. Recycle in either case: timed-out
        # symbolic work may have crossed mutable-library state, and recovery
        # must not depend on which process observed the deadline first.
        error_code not in {"E_RUNTIME", "E_TIMEOUT"},
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
