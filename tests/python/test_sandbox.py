import json
from concurrent.futures import Future
import threading
import time

import math_anchor.sandbox as sandbox
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
            timeout_ms=100,
        )
        assert result["status"] == "ok"
        assert result["exact"] == "42"


def test_timeout_bounds_worker_queue_wait(monkeypatch) -> None:
    sandbox._WORKER_POOL.shutdown()
    isolated_pool = sandbox._WorkerPool(maximum=1)
    monkeypatch.setattr(sandbox, "_WORKER_POOL", isolated_pool)
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
    oversized_error = {
        "status": "error",
        "error": {"code": "E_RUNTIME", "message": "failure" * 10_000},
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
    assert result["error"]["code"] == "E_OUTPUT_LIMIT"
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

    assert maximum_active == 4
    assert [item["exact"] for item in result["results"]] == [str(index) for index in range(6)]


def test_worker_reader_failure_returns_a_structured_error(monkeypatch) -> None:
    # Negative regression: a reader-thread exception must surface as an
    # E_RUNTIME error object, never propagate out of run_operation.
    from math_anchor import sandbox

    def broken_reader(process):
        raise ValueError("simulated reader failure")

    monkeypatch.setattr(sandbox, "_read_response_line", broken_reader)
    result = sandbox.run_operation("expression.evaluate", {"expression": "1+1"})
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_RUNTIME"
    assert "reader failed" in result["error"]["message"]


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
    monkeypatch.setattr(sandbox, "WORKER_POLL_SECONDS", 1.0)

    started = time.monotonic()
    sandbox._wait_for_worker_progress(completed)

    assert time.monotonic() - started < 0.1
