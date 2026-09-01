import json
import os
from concurrent.futures import Future
import subprocess
import sys
import threading
import time

import math_anchor.sandbox as sandbox
from math_anchor import sandbox_testing
from math_anchor import worker
from math_anchor.errors import CalculatorError
from math_anchor.sandbox import run_batch, run_operation


def test_isolated_execution_and_structured_error() -> None:
    result = run_operation("expression.evaluate", {"expression": "1/3", "precision": 30})
    assert result["status"] == "ok"
    assert result["exact"] == "1/3"

    blocked = run_operation("expression.evaluate", {"expression": "__import__('os')"})
    assert blocked["status"] == "error"
    assert blocked["error"]["code"] in {"E_AST_BLOCK", "E_NAME"}

    for expression in ("1/0", "0/0"):
        undefined = run_operation("expression.evaluate", {"expression": expression})
        assert undefined["status"] == "error"
        assert undefined["error"]["code"] == "E_DOMAIN"


def test_maximum_allowed_factorial_is_serializable() -> None:
    result = run_operation("expression.evaluate", {"expression": "factorial(5000)"})
    assert result["status"] == "ok"
    assert result["exact"].isdigit()
    assert len(result["exact"]) == 16_326


def test_batch_preserves_order_and_partial_failure() -> None:
    result = run_batch(
        [
            {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
            {"operation": "missing.operation", "arguments": {}},
        ]
    )
    assert result["status"] == "partial"
    assert result["results"][0]["exact"] == "42"
    assert result["results"][1]["error"]["code"] == "E_OPERATION"


def test_batch_output_budget_aborts_once_the_response_provably_cannot_fit() -> None:
    # Negative regression: once the charged prefix of completed items already
    # exceeds the aggregate budget, the batch must stop there instead of
    # computing every remaining item and reporting the full envelope size
    # (32 ok items of ~10 KB each serialize to ~330 KB).
    items = [
        {"operation": "expression.evaluate", "arguments": {"expression": "10**10000"}}
        for _ in range(32)
    ]
    result = run_batch(items)
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_OUTPUT_LIMIT"
    assert result["error"]["details"]["bytes"] < 200_000
    assert "at least" in result["error"]["message"]


def test_timeout_is_enforced() -> None:
    result = run_operation(
        "matrix.inverse",
        {
            "matrix": [
                [f"1/{row + column + 1}" for column in range(40)]
                for row in range(40)
            ]
        },
        timeout_ms=100,
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_TIMEOUT"


def test_warm_worker_meets_a_short_complete_call_timeout() -> None:
    warm = run_operation("expression.evaluate", {"expression": "0"})
    assert warm["status"] == "ok"
    for _ in range(3):
        result = run_operation(
            "expression.evaluate",
            {"expression": "6*7"},
            # A caller choosing the minimum accepted 100 ms legitimately
            # receives E_TIMEOUT under host scheduling pressure; 500 ms stays
            # short relative to the 10 s default without turning success into
            # a machine-load assertion.
            timeout_ms=500,
        )
        assert result["status"] == "ok"
        assert result["exact"] == "42"


def test_timeout_bounds_worker_queue_wait(monkeypatch) -> None:
    sandbox._WORKER_POOL.shutdown()
    isolated_pool = sandbox._WorkerPool(maximum=1)
    sandbox_testing.bind_worker_pool(monkeypatch, isolated_pool)
    worker, error = isolated_pool.acquire(
        sandbox.DEFAULT_MEMORY_MB * 1024 * 1024,
        deadline=time.monotonic() + 5,
        timeout_ms=5_000,
    )
    assert worker is not None
    assert error is None
    try:
        started = time.monotonic()
        result = run_operation(
            "expression.evaluate",
            {"expression": "2+2"},
            timeout_ms=100,
        )
        elapsed = time.monotonic() - started
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_TIMEOUT"
        assert result["error"]["details"]["phase"] == "queue"
        assert elapsed < 0.3
    finally:
        isolated_pool.release(worker, reusable=True)
        isolated_pool.shutdown()


def test_successive_operations_reuse_a_warm_worker_and_timeout_rebuilds_it() -> None:
    sandbox._WORKER_POOL.shutdown()
    try:
        first = run_operation("expression.evaluate", {"expression": "6*7"})
        assert first["exact"] == "42"
        first_pid = sandbox._WORKER_POOL.available[-1].process.pid

        second = run_operation("expression.evaluate", {"expression": "7*8"})
        assert second["exact"] == "56"
        assert sandbox._WORKER_POOL.available[-1].process.pid == first_pid

        timed_out = run_operation(
            "matrix.inverse",
            {
                "matrix": [
                    [f"1/{row + column + 1}" for column in range(40)]
                    for row in range(40)
                ]
            },
            timeout_ms=100,
        )
        assert timed_out["error"]["code"] == "E_TIMEOUT"

        recovered = run_operation("expression.evaluate", {"expression": "9*9"})
        assert recovered["exact"] == "81"
        assert sandbox._WORKER_POOL.available[-1].process.pid != first_pid
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_large_worker_output_is_drained_while_process_runs() -> None:
    size = 30
    matrix = [
        [f"1/{row + column + 1}" for column in range(size)]
        for row in range(size)
    ]
    result = run_operation(
        "matrix.inverse",
        {"matrix": matrix, "precision": 200},
        timeout_ms=10_000,
    )
    assert result["status"] == "ok"
    assert result["exact"] is not None
    assert result["approx"] is None
    assert len(json.dumps(result)) < 64 * 1024

    both = run_operation(
        "matrix.inverse",
        {"matrix": matrix, "precision": 200},
        timeout_ms=10_000,
        result_mode="both",
        max_output_bytes=64 * 1024,
    )
    assert both["status"] == "error"
    assert both["error"]["code"] == "E_OUTPUT_LIMIT"


def test_invalid_input_error_is_concise_and_obeys_the_complete_output_budget() -> None:
    reflected_input = "x" * 200_000
    result = run_operation(
        "expression.evaluate",
        {"expression": reflected_input},
        max_output_bytes=1_024,
    )
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_LIMIT"
    assert len(encoded) <= 1_024
    assert reflected_input[:1_000] not in encoded.decode()


def test_non_validation_errors_cannot_bypass_the_output_budget(monkeypatch) -> None:
    # Negative regression in two directions: the byte budget must hold for an
    # error envelope with unbounded message text, but shrinking it must
    # preserve the real error code. Replacing the envelope wholesale with
    # E_OUTPUT_LIMIT masked the actual failure behind an unrelated
    # "increase maxOutputBytes" instruction.
    oversized_error = {
        "status": "error",
        "error": {
            "code": "E_RUNTIME",
            "message": "failure" * 10_000,
            "details": {"bytes": 60_000, "maxOutputBytes": 1_024},
        },
    }

    monkeypatch.setattr(
        sandbox,
        "_execute_worker",
        lambda *args, **kwargs: (oversized_error, True),
    )
    result = run_operation(
        "expression.evaluate",
        {"expression": "1+1"},
        max_output_bytes=1_024,
    )
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_RUNTIME"
    assert "details" not in result["error"]
    assert len(result["error"]["message"]) < len(oversized_error["error"]["message"])
    assert len(encoded) <= 1_024


def test_batch_invalid_resource_limit_is_an_indexed_partial_error() -> None:
    result = run_batch(
        [
            {
                "operation": "expression.evaluate",
                "arguments": {"expression": "2+2"},
                "timeoutMs": "bad",
            },
            {
                "operation": "expression.evaluate",
                "arguments": {"expression": "5+5"},
                "memoryMb": False,
            },
            {"operation": "expression.evaluate", "arguments": {"expression": "3+3"}},
        ]
    )
    assert result["status"] == "partial"
    assert result["results"][0]["index"] == 0
    assert result["results"][0]["error"]["code"] == "E_LIMIT"
    assert result["results"][1]["index"] == 1
    assert result["results"][1]["error"]["code"] == "E_LIMIT"
    assert result["results"][2]["index"] == 2
    assert result["results"][2]["exact"] == "6"


def test_batch_runtime_rejects_missing_arguments_and_unknown_item_fields() -> None:
    result = run_batch(
        [
            {"operation": "expression.evaluate"},
            {
                "operation": "expression.evaluate",
                "arguments": {"expression": "2+2"},
                "unexpected": True,
            },
        ]
    )

    assert result["status"] == "partial"
    assert [item["error"]["code"] for item in result["results"]] == [
        "E_INPUT",
        "E_INPUT",
    ]


def test_batch_timeout_is_cumulative_across_queued_items(monkeypatch) -> None:
    started: list[str] = []

    def slow_run(operation, arguments, *, timeout_ms, **_limits):
        started.append(arguments["value"])
        time.sleep(timeout_ms / 1000)
        return {"status": "ok", "operation": operation, "kind": "scalar", "exact": arguments["value"]}

    monkeypatch.setattr(sandbox, "run_operation", slow_run)
    monkeypatch.setattr(sandbox, "_batch_worker_count", lambda _items: 1)
    result = run_batch(
        [
            {"operation": "test.echo", "arguments": {"value": str(index)}}
            for index in range(3)
        ],
        timeout_ms=250,
    )

    assert started == ["0"]
    assert result["status"] == "partial"
    assert [item["error"]["code"] for item in result["results"][1:]] == [
        "E_TIMEOUT",
        "E_TIMEOUT",
    ]


def test_batch_uses_bounded_parallel_workers_and_preserves_order(monkeypatch) -> None:
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    def fake_run(operation, arguments, *, timeout_ms, memory_mb, **_output_policy):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return {"status": "ok", "operation": operation, "kind": "scalar", "exact": arguments["value"]}

    monkeypatch.setattr(sandbox, "run_operation", fake_run)
    result = run_batch(
        [
            {"operation": "test.echo", "arguments": {"value": str(index)}}
            for index in range(6)
        ]
    )

    # Batches deliberately use only three of four worker lanes so a normal
    # math.run can still be admitted during sustained batch traffic.
    assert maximum_active == 3
    assert [item["exact"] for item in result["results"]] == [str(index) for index in range(6)]


def test_worker_reader_failure_returns_a_structured_error(monkeypatch) -> None:
    # Negative regression: a reader-thread exception must surface as an
    # E_RUNTIME error object, never propagate out of run_operation.
    from math_anchor import sandbox

    def broken_reader(process):
        raise ValueError("simulated reader failure")

    monkeypatch.setattr(sandbox_testing.process_runtime(), "_read_response_line", broken_reader)
    result = sandbox.run_operation("expression.evaluate", {"expression": "1+1"})
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_RUNTIME"
    assert "reader failed" in result["error"]["message"]


def test_worker_payload_forwards_the_request_budget_to_the_in_process_bound() -> None:
    # Negative regression: the worker used to hand only RLIMIT_CPU the
    # payload's timeoutMs; the in-process SIGALRM stayed at the fixed
    # ten-second default, so any budget above ten seconds was silently cut.
    forwarded: list[int | None] = []

    def recording_execute(operation, arguments, *, timeout_ms=None):
        forwarded.append(timeout_ms)
        return {"status": "ok", "operation": operation, "kind": "scalar", "exact": "42"}

    response = worker._execute_payload(
        {
            "operation": "expression.evaluate",
            "arguments": {"expression": "6*7"},
            "timeoutMs": 30_000,
        },
        recording_execute,
        CalculatorError,
    )

    assert forwarded == [30_000]
    assert response["ok"] is True
    assert response["result"]["exact"] == "42"


def test_worker_applies_output_budget_before_writing_its_response() -> None:
    # A huge valid result must be reduced inside the supervised worker instead
    # of crossing the stdout pipe in full and being rejected only by the parent.
    def oversized_execute(operation, arguments, *, timeout_ms=None):
        return {
            "status": "ok",
            "operation": operation,
            "kind": "scalar",
            "exact": "9" * 200_000,
        }

    response = worker._execute_payload(
        {
            "operation": "expression.evaluate",
            "arguments": {"expression": "factorial(50000)"},
            "timeoutMs": 2_000,
            "resultMode": "auto",
            "maxOutputBytes": 1_024,
        },
        oversized_execute,
        CalculatorError,
    )

    assert response["ok"] is True
    assert response["result"]["status"] == "error"
    assert response["result"]["error"]["code"] == "E_OUTPUT_LIMIT"
    assert len(json.dumps(response, separators=(",", ":")).encode()) < 1_200


def test_completed_response_is_not_rejudged_against_the_deadline(monkeypatch) -> None:
    # Negative regression: the reader thread used to stamp the response with
    # time.monotonic() taken after readline() returned; a worker that answered
    # in budget was killed and its result discarded whenever the reader was
    # descheduled between those two lines. Skewing only the reader thread's
    # clock reproduces that race deterministically.
    class _ReaderSkewedClock:
        @staticmethod
        def monotonic() -> float:
            if threading.current_thread().name.startswith("calculator-worker-output"):
                return time.monotonic() + 30.0
            return time.monotonic()

    sandbox._WORKER_POOL.shutdown()
    try:
        monkeypatch.setattr(sandbox_testing.process_runtime(), "time", _ReaderSkewedClock)
        warm = run_operation("expression.evaluate", {"expression": "6*7"}, timeout_ms=2_000)
        assert warm["exact"] == "42"
        prewarmed_pid = sandbox._WORKER_POOL.available[-1].process.pid

        result = run_operation("expression.evaluate", {"expression": "7*8"}, timeout_ms=2_000)

        assert result["status"] == "ok"
        assert result["exact"] == "56"
        # The answered worker survived: the next call reuses it, not a respawn.
        assert sandbox._WORKER_POOL.available[-1].process.pid == prewarmed_pid
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_response_arriving_after_the_deadline_is_rejected(monkeypatch) -> None:
    # Negative regression: a long polling wait used to leave a race where the
    # future became done after the deadline but before the loop condition was
    # rechecked, so an over-budget response was accepted as success.
    monkeypatch.setattr(sandbox_testing.process_runtime(), "WORKER_POLL_SECONDS", 1.0)
    stderr_fd = sandbox._worker_stderr_file()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import json,sys,time; sys.stdin.readline(); time.sleep(0.15); "
                "json.dump({'ok':True,'_completedAtMonotonic':time.monotonic(),"
                "'result':{'status':'ok','operation':'expression.evaluate',"
                "'kind':'scalar','exact':'42'}},sys.stdout,separators=(',',':')); "
                "sys.stdout.write('\\n'); sys.stdout.flush()"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_fd,
        text=True,
        bufsize=1,
    )
    reusable_worker = sandbox._ReusableWorker(process, stderr_fd)
    try:
        result, reusable, output_policy_applied = sandbox._execute_worker(
            reusable_worker,
            "{}\n",
            deadline=time.monotonic() + 0.1,
            timeout_ms=100,
            memory_mb=sandbox.DEFAULT_MEMORY_MB,
            cancel_event=None,
        )
        assert reusable is False
        assert output_policy_applied is False
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_TIMEOUT"
    finally:
        reusable_worker.terminate()


def test_reusable_worker_keeps_one_output_reader_across_calls() -> None:
    # A warm high-frequency call must not create and join a new reader thread.
    sandbox._WORKER_POOL.shutdown()
    try:
        first = run_operation("expression.evaluate", {"expression": "6*7"})
        assert first["exact"] == "42"
        pooled = sandbox._WORKER_POOL.available[-1]
        reader_ident = pooled.output_reader.ident
        assert reader_ident is not None

        second = run_operation("expression.evaluate", {"expression": "7*8"})
        assert second["exact"] == "56"
        reused = sandbox._WORKER_POOL.available[-1]
        assert reused.process.pid == pooled.process.pid
        assert reused.output_reader.ident == reader_ident
        assert reused.output_reader.is_alive()
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_persistent_worker_serves_the_first_units_call_within_a_short_budget() -> None:
    # Negative regression: both Pint registries build lazily (~150 ms each),
    # so the first units.convert spent its own deadline parsing the unit
    # definition file. Persistent workers now build them on a background
    # thread right after readiness.
    sandbox._WORKER_POOL.shutdown()
    try:
        worker_process, startup_error = sandbox._start_worker(
            sandbox.DEFAULT_MEMORY_MB * 1024 * 1024,
            deadline=time.monotonic() + 5,
            timeout_ms=5_000,
            cancel_event=None,
        )
        assert worker_process is not None, startup_error
        try:
            time.sleep(1.0)  # allow the background registry warm to finish
            result, reusable, output_policy_applied = sandbox._execute_worker(
                worker_process,
                json.dumps(
                    {
                        "operation": "units.convert",
                        "arguments": {"value": 1, "fromUnit": "m", "toUnit": "cm"},
                        # 100 ms is the minimum accepted caller budget, not a
                        # host-load SLA. Keep this success regression short
                        # while leaving scheduling margin after warmup.
                        "timeoutMs": 500,
                        "memoryMb": sandbox.DEFAULT_MEMORY_MB,
                    },
                    separators=(",", ":"),
                )
                + "\n",
                deadline=time.monotonic() + 2,
                timeout_ms=500,
                memory_mb=sandbox.DEFAULT_MEMORY_MB,
                cancel_event=None,
            )
            assert reusable is True
            assert output_policy_applied is True
            assert result["status"] == "ok"
            assert result["exact"] == "100"
        finally:
            worker_process.terminate()
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_cancellation_terminates_the_active_worker_and_the_pool_recovers() -> None:
    cancel_event = threading.Event()
    outcome: list[dict] = []

    request = threading.Thread(
        target=lambda: outcome.append(
            run_operation(
                "expression.evaluate",
                {"expression": "floor(gamma(exp(7)))", "precision": 16},
                timeout_ms=30_000,
                cancel_event=cancel_event,
            )
        )
    )
    request.start()
    time.sleep(0.1)
    cancel_event.set()
    request.join(timeout=3)

    assert not request.is_alive()
    assert outcome[0]["status"] == "error"
    assert outcome[0]["error"]["code"] == "E_CANCELLED"
    recovered = run_operation("expression.evaluate", {"expression": "6*7"})
    assert recovered["status"] == "ok"
    assert recovered["exact"] == "42"


def test_completed_worker_output_does_not_wait_out_the_supervision_cadence(
    monkeypatch,
) -> None:
    completed: Future[None] = Future()
    completed.set_result(None)
    monkeypatch.setattr(sandbox_testing.process_runtime(), "WORKER_POLL_SECONDS", 1.0)

    started = time.monotonic()
    sandbox._wait_for_worker_progress(completed)

    assert time.monotonic() - started < 0.1


def test_unserializable_arguments_do_not_leak_pool_slots() -> None:
    # Negative regression: a parent-side failure between acquire and release
    # previously leaked the reserved slot. MAX_REUSABLE_WORKERS rejections
    # therefore saturated the pool, and every later operation became a
    # queue-phase E_TIMEOUT for the rest of the process.
    sandbox._WORKER_POOL.shutdown()
    try:
        for _ in range(sandbox.MAX_REUSABLE_WORKERS):
            result = run_operation(
                "expression.evaluate",
                {"expression": "1+1", "variables": {"x": object()}},
                timeout_ms=1_000,
            )
            assert result["status"] == "error"
            assert result["error"]["code"] == "E_INPUT"
            assert "JSON-serializable" in result["error"]["message"]

        recovered = run_operation(
            "expression.evaluate",
            {"expression": "6*7"},
            timeout_ms=2_000,
        )
        assert recovered["status"] == "ok"
        assert recovered["exact"] == "42"
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_worker_stderr_cannot_block_and_is_reset_between_requests() -> None:
    # Worker stderr goes to an unlinked file, not a pipe: a pipe fills at
    # the OS buffer size and then blocks the worker mid-operation. The spill
    # file is cleared between requests so a long-lived session also cannot
    # accumulate diagnostics without bound.
    sandbox._WORKER_POOL.shutdown()
    try:
        worker, startup_error = sandbox._start_worker(
            sandbox.DEFAULT_MEMORY_MB * 1024 * 1024,
            deadline=time.monotonic() + 5,
            timeout_ms=5_000,
            cancel_event=None,
        )
        assert worker is not None, startup_error
        try:
            os.write(worker.stderr_fd, b"w" * 200_000 + b"\nworker-diagnostics-line\n")
            tail = worker.stderr_tail()
            assert len(tail) <= sandbox._STDERR_TAIL_BYTES
            assert tail.endswith("worker-diagnostics-line\n")

            result, reusable, output_policy_applied = sandbox._execute_worker(
                worker,
                json.dumps(
                    {
                        "operation": "expression.evaluate",
                        "arguments": {"expression": "6*7"},
                        "timeoutMs": 2_000,
                        "memoryMb": sandbox.DEFAULT_MEMORY_MB,
                    },
                    separators=(",", ":"),
                )
                + "\n",
                deadline=time.monotonic() + 2,
                timeout_ms=2_000,
                memory_mb=sandbox.DEFAULT_MEMORY_MB,
                cancel_event=None,
            )
            assert reusable is True
            assert output_policy_applied is True
            assert result["status"] == "ok"
            assert result["exact"] == "42"

            worker.reset_stderr()
            assert os.fstat(worker.stderr_fd).st_size == 0
        finally:
            worker.terminate()
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_warm_worker_pool_prestarts_one_reusable_worker() -> None:
    sandbox._WORKER_POOL.shutdown()
    try:
        sandbox.warm_worker_pool()
        deadline = time.monotonic() + sandbox.WORKER_PREWARM_BUDGET_SECONDS + 5
        while not sandbox._WORKER_POOL.available and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sandbox._WORKER_POOL.total == 1
        assert len(sandbox._WORKER_POOL.available) == 1
        prewarmed_pid = sandbox._WORKER_POOL.available[0].process.pid

        result = run_operation("expression.evaluate", {"expression": "6*7"})
        assert result["exact"] == "42"
        # The warmed worker was reused, not replaced by a fresh spawn.
        assert sandbox._WORKER_POOL.available[-1].process.pid == prewarmed_pid
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_warm_worker_pool_is_idempotent() -> None:
    sandbox._WORKER_POOL.shutdown()
    try:
        for _ in range(sandbox.MAX_REUSABLE_WORKERS + 2):
            sandbox.warm_worker_pool()
        deadline = time.monotonic() + sandbox.WORKER_PREWARM_BUDGET_SECONDS + 5
        while not sandbox._WORKER_POOL.available and time.monotonic() < deadline:
            time.sleep(0.02)

        assert sandbox._WORKER_POOL.total == 1
        assert len(sandbox._WORKER_POOL.available) == 1
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_shutdown_invalidates_an_inflight_prewarm(monkeypatch) -> None:
    isolated_pool = sandbox._WorkerPool(maximum=1)
    sandbox_testing.bind_worker_pool(monkeypatch, isolated_pool)
    startup_entered = threading.Event()
    worker_terminated = threading.Event()

    class FakeWorker:
        pool_generation: int | None = None

        @property
        def is_running(self) -> bool:
            return not worker_terminated.is_set()

        def reset_stderr(self) -> None:
            pass

        def terminate(self) -> None:
            worker_terminated.set()

    def delayed_start(*_args, cancel_event, **_kwargs):
        startup_entered.set()
        assert cancel_event is not None
        assert cancel_event.wait(timeout=2)
        return FakeWorker(), None

    monkeypatch.setattr(sandbox_testing.pool_runtime(), "_start_worker", delayed_start)
    sandbox.warm_worker_pool()
    assert startup_entered.wait(timeout=1)

    isolated_pool.shutdown()
    assert worker_terminated.is_set()
    with isolated_pool.condition:
        assert isolated_pool.total == 0
        assert isolated_pool.available == []
        assert isolated_pool.prewarm_generation is None
        assert isolated_pool.prewarm_cancel is None
        assert isolated_pool.prewarm_thread is None


def test_unserializable_error_obeys_the_output_budget() -> None:
    # The json TypeError message embeds the 200 000-character class name, so
    # the E_INPUT envelope exceeds the budget. The real cause survives with a
    # truncated message instead of being masked as E_OUTPUT_LIMIT.
    oversized_type = type("X" * 200_000, (), {})
    result = run_operation(
        "expression.evaluate",
        {"expression": "1+1", "variables": {"x": oversized_type()}},
        max_output_bytes=1_024,
    )
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_INPUT"
    assert len(result["error"]["message"]) < 200_000
    assert len(encoded) <= 1_024


def test_worker_startup_exception_does_not_leak_a_pool_slot(monkeypatch) -> None:
    isolated_pool = sandbox._WorkerPool(maximum=1)
    sandbox_testing.bind_worker_pool(monkeypatch, isolated_pool)
    monkeypatch.setattr(
        sandbox_testing.pool_runtime(),
        "_start_worker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated")),
    )

    result = run_operation(
        "expression.evaluate",
        {"expression": "1+1"},
        timeout_ms=1_000,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_RUNTIME"
    assert result["error"]["message"] == "worker startup failed: RuntimeError"
    assert result["error"]["retryable"] is True
    assert result["error"]["suggestedAction"] == "retry"
    assert isolated_pool.total == 0


def test_worker_supervision_exception_is_structured_and_releases_the_slot(
    monkeypatch,
) -> None:
    isolated_pool = sandbox._WorkerPool(maximum=1)
    sandbox_testing.bind_worker_pool(monkeypatch, isolated_pool)
    try:
        real_execute = sandbox._execute_worker
        monkeypatch.setattr(
            sandbox,
            "_execute_worker",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated")),
        )

        result = run_operation(
            "expression.evaluate",
            {"expression": "1+1"},
            timeout_ms=2_000,
        )

        assert result["status"] == "error"
        assert result["error"]["code"] == "E_RUNTIME"
        assert result["error"]["message"] == "worker supervision failed: RuntimeError"
        assert result["error"]["retryable"] is True
        assert result["error"]["suggestedAction"] == "retry"
        # The failed slot is released. The adaptive warmer may already have
        # reserved exactly one replacement, but capacity cannot leak past the
        # pool's configured maximum.
        assert isolated_pool.total <= isolated_pool.maximum

        monkeypatch.setattr(sandbox, "_execute_worker", real_execute)
        recovered = run_operation(
            "expression.evaluate",
            {"expression": "6*7"},
            timeout_ms=2_000,
        )
        assert recovered["status"] == "ok"
        assert recovered["exact"] == "42"
    finally:
        isolated_pool.shutdown()
