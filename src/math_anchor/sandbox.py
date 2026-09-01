from __future__ import annotations

from copy import deepcopy
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .runtime_control import (
    AdmissionController,
    CircuitBreaker,
    CombinedCancelEvent,
    batch_worker_count as _batch_worker_count,
)
from .runtime_telemetry import RUNTIME_TELEMETRY
from .sandbox_errors import _error
from .transport_budget import (
    MAX_BATCH_REQUEST_BYTES,
    MAX_BATCH_REQUEST_NODES,
    MAX_REQUEST_BYTES,
    MAX_REQUEST_NODES,
    TransportBudgetError,
    encode_json_line,
)
from .worker_pool import (
    DEFAULT_MEMORY_MB,
    DEFAULT_TIMEOUT_MS,
    MAX_REQUESTS_PER_WORKER,
    MAX_REUSABLE_WORKERS,
    WORKER_PREWARM_BUDGET_SECONDS,
    WORKER_RECYCLE_RSS_MB,
    _WORKER_POOL,
    _WorkerPool,
    warm_worker_pool,
)
from .worker_process import (
    STARTUP_TIMEOUT_MS,
    WORKER_POLL_SECONDS,
    _STDERR_TAIL_BYTES,
    _ReusableWorker,
    _await_worker_ready,
    _execute_worker,
    _read_response_line,
    _resident_memory_bytes,
    _start_worker,
    _start_worker_impl,
    _stderr_tail,
    _stderr_tail_bytes,
    _wait_for_worker_progress,
    _worker_stderr_file,
)


_BATCH_ITEM_FIELDS = {
    "operation",
    "arguments",
    "timeoutMs",
    "memoryMb",
    "resultMode",
    "maxOutputBytes",
}
_ADMISSION = AdmissionController()
_CIRCUIT = CircuitBreaker()


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
        request_line = encode_json_line(payload)
    except TransportBudgetError as error:
        return apply_output_policy(
            _error(
                "E_LIMIT",
                str(error),
                {
                    "rule": error.rule,
                    "maxRequestBytes": MAX_REQUEST_BYTES,
                    "maxRequestNodes": MAX_REQUEST_NODES,
                },
                phase="input",
            ),
            result_mode=result_mode,
            max_output_bytes=max_output_bytes,
        )
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
    try:
        encode_json_line(
            {"items": items},
            max_bytes=MAX_BATCH_REQUEST_BYTES,
            max_nodes=MAX_BATCH_REQUEST_NODES,
        )
    except TransportBudgetError as error:
        return _error(
            "E_LIMIT",
            str(error),
            {
                "rule": error.rule,
                "maxRequestBytes": MAX_BATCH_REQUEST_BYTES,
                "maxRequestNodes": MAX_BATCH_REQUEST_NODES,
            },
            phase="input",
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        return _error(
            "E_INPUT",
            f"batch items must be JSON-serializable: {error}",
            phase="input",
        )
    if time.monotonic() >= deadline:
        return _error(
            "E_TIMEOUT",
            f"batch exceeded its cumulative {timeout_ms} ms deadline during input preflight",
            {"phase": "input", "timeoutMs": timeout_ms},
            phase="input",
        )
    worker_count = _batch_worker_count(items)
    batch_cancel = threading.Event()
    combined_cancel = CombinedCancelEvent(cancel_event, batch_cancel)
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
