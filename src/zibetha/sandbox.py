from __future__ import annotations

import atexit
import json
import os
import psutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .output_policy import (
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


def _error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"status": "error", "error": error}


class _ReusableWorker:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.process = process

    @property
    def is_running(self) -> bool:
        return self.process.poll() is None

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


class _WorkerPool:
    def __init__(self, maximum: int = MAX_REUSABLE_WORKERS) -> None:
        self.maximum = maximum
        self.condition = threading.Condition()
        self.available: list[_ReusableWorker] = []
        self.total = 0

    def acquire(
        self,
        memory_bytes: int,
        *,
        deadline: float,
        timeout_ms: int,
    ) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
        while True:
            with self.condition:
                while self.available:
                    worker = self.available.pop()
                    resident = _resident_memory_bytes(worker.process.pid)
                    if worker.is_running and (resident is None or resident <= memory_bytes):
                        return worker, None
                    self.total -= 1
                    worker.terminate()
                if self.total < self.maximum:
                    self.total += 1
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None, _error(
                        "E_TIMEOUT",
                        f"operation exceeded {timeout_ms} ms while waiting for a worker",
                        {"phase": "queue", "timeoutMs": timeout_ms},
                    )
                self.condition.wait(timeout=remaining)

        worker, error = _start_worker(
            memory_bytes,
            deadline=deadline,
            timeout_ms=timeout_ms,
        )
        if worker is None:
            with self.condition:
                self.total -= 1
                self.condition.notify()
            return None, error
        return worker, None

    def release(self, worker: _ReusableWorker, *, reusable: bool) -> None:
        with self.condition:
            if reusable and worker.is_running:
                self.available.append(worker)
            else:
                self.total -= 1
                worker.terminate()
            self.condition.notify()

    def shutdown(self) -> None:
        with self.condition:
            workers = self.available
            self.available = []
            self.total -= len(workers)
            self.condition.notify_all()
        for worker in workers:
            worker.terminate()


_WORKER_POOL = _WorkerPool()
atexit.register(_WORKER_POOL.shutdown)


def run_operation(
    operation: str,
    arguments: dict[str, Any],
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    memory_mb: int = DEFAULT_MEMORY_MB,
    result_mode: str = DEFAULT_RESULT_MODE,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
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
    memory_bytes = memory_mb * 1024 * 1024
    worker, startup_error = _WORKER_POOL.acquire(
        memory_bytes,
        deadline=deadline,
        timeout_ms=timeout_ms,
    )
    if worker is None:
        return startup_error or _error("E_RUNTIME", "worker failed to start")
    if time.monotonic() >= deadline:
        _WORKER_POOL.release(worker, reusable=True)
        return _error(
            "E_TIMEOUT",
            f"operation exceeded {timeout_ms} ms before execution began",
            {"phase": "startup", "timeoutMs": timeout_ms},
        )
    result, reusable = _execute_worker(
        worker,
        payload,
        deadline=deadline,
        timeout_ms=timeout_ms,
        memory_mb=memory_mb,
    )
    _WORKER_POOL.release(worker, reusable=reusable)
    if result.get("status") == "error":
        return result
    return apply_output_policy(
        result,
        result_mode=result_mode,
        max_output_bytes=max_output_bytes,
    )


def _start_worker(
    memory_bytes: int,
    *,
    deadline: float,
    timeout_ms: int,
) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
    environment = os.environ.copy()
    environment.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    command = (
        [sys.executable, "worker", "--persistent"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "zibetha.worker", "--persistent"]
    )
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=environment,
        )
    except OSError as error:
        return None, _error("E_RUNTIME", f"worker failed to start: {error}")
    startup_error = _await_worker_ready(
        process,
        memory_bytes,
        deadline=deadline,
        timeout_ms=timeout_ms,
    )
    if startup_error is not None:
        return None, startup_error
    return _ReusableWorker(process), None


def _execute_worker(
    worker: _ReusableWorker,
    payload: dict[str, Any],
    *,
    deadline: float,
    timeout_ms: int,
    memory_mb: int,
) -> tuple[dict[str, Any], bool]:
    process = worker.process
    memory_bytes = memory_mb * 1024 * 1024
    if process.stdin is None or process.stdout is None:
        return _error("E_RUNTIME", "worker pipes were unavailable"), False
    try:
        process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        process.stdin.flush()
    except (BrokenPipeError, OSError):
        return _error("E_RUNTIME", "worker input was unavailable"), False

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="calculator-worker-output") as executor:
        response_read = executor.submit(_read_response_line, process)
        limit_error: dict[str, Any] | None = None
        while not response_read.done():
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
            time.sleep(0.025)

        response_line, completed_at = response_read.result()
        if limit_error is not None:
            return limit_error, False
        if completed_at >= deadline:
            process.kill()
            return _error("E_TIMEOUT", f"operation exceeded {timeout_ms} ms"), False

    if not response_line:
        return_code = process.poll()
        stderr = process.stderr.read().strip() if process.stderr is not None and return_code is not None else ""
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


def _read_response_line(
    process: subprocess.Popen[str],
) -> tuple[str, float]:
    line = process.stdout.readline() if process.stdout is not None else ""
    return line, time.monotonic()


def _await_worker_ready(
    process: subprocess.Popen[str],
    memory_bytes: int,
    *,
    deadline: float,
    timeout_ms: int,
) -> dict[str, Any] | None:
    if process.stdout is None:
        process.kill()
        return _error("E_RUNTIME", "worker output was unavailable")
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="calculator-worker-startup") as executor:
        readiness = executor.submit(process.stdout.readline)
        startup_deadline = min(deadline, time.monotonic() + STARTUP_TIMEOUT_MS / 1000)
        while not readiness.done():
            if time.monotonic() >= startup_deadline:
                process.kill()
                readiness.result()
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
                return _error("E_MEMORY", "worker exceeded the memory limit during startup")
            if process.poll() is not None:
                break
            time.sleep(0.025)
        line = readiness.result()
    try:
        ready = json.loads(line)
    except json.JSONDecodeError:
        ready = None
    if ready != {"ready": True}:
        stderr = process.stderr.read().strip() if process.stderr is not None else ""
        process.kill()
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
    max_output_bytes: int = 256 * 1024,
) -> dict[str, Any]:
    if not isinstance(items, list) or not 1 <= len(items) <= 32:
        return _error("E_LIMIT", "items must contain 1 to 32 operations")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool):
        return _error("E_LIMIT", f"maxOutputBytes must be an integer between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")
    if not MIN_OUTPUT_BYTES <= max_output_bytes <= MAX_OUTPUT_BYTES:
        return _error("E_LIMIT", f"maxOutputBytes must be between {MIN_OUTPUT_BYTES} and {MAX_OUTPUT_BYTES}")
    worker_count = _batch_worker_count(items)
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="calculator-batch") as executor:
        results = list(executor.map(_run_batch_item, enumerate(items)))
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


def _run_batch_item(indexed_item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    index, item = indexed_item
    if not isinstance(item, dict) or not isinstance(item.get("operation"), str):
        return {
            "index": index,
            **_error("E_INPUT", "each item requires an operation string and optional arguments object"),
        }
    result = run_operation(
        item["operation"],
        item.get("arguments", {}),
        timeout_ms=item.get("timeoutMs", DEFAULT_TIMEOUT_MS),
        memory_mb=item.get("memoryMb", DEFAULT_MEMORY_MB),
        result_mode=item.get("resultMode", DEFAULT_RESULT_MODE),
        max_output_bytes=item.get("maxOutputBytes", DEFAULT_MAX_OUTPUT_BYTES),
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
